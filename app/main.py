from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import uuid

from app.agent import chat
from app.session_store import session_store
from app.crm_client import crm_client
from app.lead_agent import analyze_lead
from app.email_agent import generate_email, EmailFocusType
from app.analysis_cache import get_cached_analysis, cache_analysis


# FastAPI app
app = FastAPI(
    title="PLG AI Tools",
    description="C-PACE chatbot and Lead Qualification dashboard",
    version="1.0.0",
)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request payload."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response payload."""
    response: str
    session_id: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    message: str


class EmailGenerationRequest(BaseModel):
    """Email generation request payload."""
    focus_type: str  # industry, location, events, social


# ==================== #
# Health & Chat Routes #
# ==================== #

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    import os
    return HealthResponse(
        status="healthy",
        message=f"Chatbot is running (Vercel: {os.getenv('VERCEL', 'false')})"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat with the C-PACE agent."""
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        response = chat(request.message, session_id)
        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a session's conversation history."""
    session_store.clear_session(session_id)
    return {"message": f"Session {session_id} cleared"}


@app.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    return {"sessions": session_store.list_sessions()}


# ==================== #
# CRM API Routes       #
# ==================== #

@app.get("/api/contacts")
async def get_contacts(
    company: Optional[str] = Query(None, description="Filter by company name"),
    state: Optional[str] = Query(None, description="Filter by state code (e.g., CA, NY)"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    per_page: int = Query(15, ge=1, le=100, description="Results per page"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """
    List all contacts from CRM with optional filtering.
    
    Returns paginated list of contacts with their basic information.
    """
    try:
        data = await crm_client.get_contacts(
            company=company,
            state=state,
            industry=industry,
            per_page=per_page,
            page=page,
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CRM API error: {str(e)}")


@app.get("/api/contacts/{contact_id}")
async def get_contact(contact_id: int):
    """
    Get detailed information about a specific contact.
    
    Returns contact details with aggregated counts of related data.
    """
    try:
        data = await crm_client.get_contact(contact_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CRM API error: {str(e)}")


@app.get("/api/contacts/{contact_id}/messages")
async def get_contact_messages(contact_id: int):
    """
    Get social media posts and blog posts for a specific contact.
    """
    try:
        data = await crm_client.get_contact_messages(contact_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CRM API error: {str(e)}")


@app.get("/api/contacts/{contact_id}/events")
async def get_contact_events(contact_id: int):
    """
    Get events attended by a specific contact.
    """
    try:
        data = await crm_client.get_contact_events(contact_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CRM API error: {str(e)}")


# ==================== #
# AI Lead Analysis     #
# ==================== #

@app.post("/api/contacts/{contact_id}/analyze")
async def analyze_contact(contact_id: int):
    """
    Analyze a contact using AI for C-PACE lead qualification.
    
    Returns AI-generated analysis including:
    - Qualification score (1-10)
    - Qualification level (Strong/Moderate/Weak)
    - Key strengths and concerns
    - Recommended actions for sales team
    - Talking points for outreach
    - Events attended (with sustainability event highlighting)
    
    Results are cached to avoid redundant API calls for the same contact.
    """
    try:
        # Check cache first
        cached_result = get_cached_analysis(contact_id)
        if cached_result:
            # Mark as cached for client-side display
            cached_result["cached"] = True
            return cached_result
        
        # Fetch contact details
        contact_data = await crm_client.get_contact(contact_id)
        contact = contact_data.get("data", contact_data)
        counts = contact_data.get("counts", {})
        
        # Fetch events attended by this contact
        events = []
        try:
            events_data = await crm_client.get_contact_events(contact_id)
            events = events_data.get("data", [])
        except Exception:
            # If events fetch fails, continue without events
            pass
        
        # Run AI analysis with events data
        analysis = analyze_lead(contact, counts, events)
        
        result = {
            "contact_id": contact_id,
            "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
            "analysis": analysis,
            "cached": False  # This is a new analysis, not cached
        }
        
        # Cache the result (without the cached flag for future lookups)
        cache_result = result.copy()
        cache_analysis(contact_id, cache_result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


# ==================== #
# AI Email Generation  #
# ==================== #

@app.post("/api/contacts/{contact_id}/generate-email")
async def generate_contact_email(contact_id: int, request: EmailGenerationRequest):
    """
    Generate a personalized outreach email for a contact.
    
    Focus types:
    - industry: Focus on how C-PACE benefits their specific industry
    - location: Focus on C-PACE developments in their state/region
    - events: Reference events they've attended
    - social: Reference their social media posts and content
    
    Returns:
    - Subject line
    - Email body (ready to copy)
    - Notes for sales rep
    """
    # Validate focus type
    valid_focus_types = ["industry", "location", "events", "social"]
    if request.focus_type not in valid_focus_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid focus_type. Must be one of: {valid_focus_types}"
        )
    
    try:
        # Fetch contact details
        contact_data = await crm_client.get_contact(contact_id)
        contact = contact_data.get("data", contact_data)
        counts = contact_data.get("counts", {})
        
        # Validate that the selected focus type has data available
        if request.focus_type == "events":
            events_count = contact.get("events_count", 0) or counts.get("events", 0)
            if events_count == 0:
                # Suggest alternative focus types
                suggestions = []
                if contact.get("industry"):
                    suggestions.append("industry")
                if contact.get("state") or contact.get("location"):
                    suggestions.append("location")
                if (contact.get("social_posts_count", 0) or counts.get("social_posts", 0) or 
                    contact.get("blog_posts_count", 0) or counts.get("blog_posts", 0)):
                    suggestions.append("social")
                
                suggestion_msg = f" This contact has no events data. "
                if suggestions:
                    suggestion_msg += f"Consider using: {', '.join(suggestions)} focus instead."
                else:
                    suggestion_msg += "No alternative focus types are available for this contact."
                
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot generate events-focused email.{suggestion_msg}"
                )
                
        elif request.focus_type == "social":
            social_count = contact.get("social_posts_count", 0) or counts.get("social_posts", 0)
            blog_count = contact.get("blog_posts_count", 0) or counts.get("blog_posts", 0)
            if (social_count + blog_count) == 0:
                # Suggest alternative focus types
                suggestions = []
                if contact.get("industry"):
                    suggestions.append("industry")
                if contact.get("state") or contact.get("location"):
                    suggestions.append("location")
                if (contact.get("events_count", 0) or counts.get("events", 0)):
                    suggestions.append("events")
                
                suggestion_msg = f" This contact has no social media posts. "
                if suggestions:
                    suggestion_msg += f"Consider using: {', '.join(suggestions)} focus instead."
                else:
                    suggestion_msg += "No alternative focus types are available for this contact."
                
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot generate social media-focused email.{suggestion_msg}"
                )
                
        elif request.focus_type == "industry":
            if not contact.get("industry"):
                # Suggest alternative focus types
                suggestions = []
                if contact.get("state") or contact.get("location"):
                    suggestions.append("location")
                if (contact.get("events_count", 0) or counts.get("events", 0)):
                    suggestions.append("events")
                if (contact.get("social_posts_count", 0) or counts.get("social_posts", 0) or 
                    contact.get("blog_posts_count", 0) or counts.get("blog_posts", 0)):
                    suggestions.append("social")
                
                suggestion_msg = f" This contact has no industry data. "
                if suggestions:
                    suggestion_msg += f"Consider using: {', '.join(suggestions)} focus instead."
                else:
                    suggestion_msg += "No alternative focus types are available for this contact."
                
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot generate industry-focused email.{suggestion_msg}"
                )
                
        elif request.focus_type == "location":
            if not (contact.get("state") or contact.get("location")):
                # Suggest alternative focus types
                suggestions = []
                if contact.get("industry"):
                    suggestions.append("industry")
                if (contact.get("events_count", 0) or counts.get("events", 0)):
                    suggestions.append("events")
                if (contact.get("social_posts_count", 0) or counts.get("social_posts", 0) or 
                    contact.get("blog_posts_count", 0) or counts.get("blog_posts", 0)):
                    suggestions.append("social")
                
                suggestion_msg = f" This contact has no location data. "
                if suggestions:
                    suggestion_msg += f"Consider using: {', '.join(suggestions)} focus instead."
                else:
                    suggestion_msg += "No alternative focus types are available for this contact."
                
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot generate location-focused email.{suggestion_msg}"
                )
        
        # Fetch additional data based on focus type
        events = []
        messages = []
        
        if request.focus_type == "events":
            try:
                events_data = await crm_client.get_contact_events(contact_id)
                events = events_data.get("data", [])
            except Exception:
                pass
                
        elif request.focus_type == "social":
            try:
                messages_data = await crm_client.get_contact_messages(contact_id)
                messages = messages_data.get("data", [])
            except Exception:
                pass
        
        # Generate the email
        email = generate_email(
            contact=contact,
            focus_type=request.focus_type,
            events=events,
            messages=messages
        )
        
        return {
            "contact_id": contact_id,
            "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
            "contact_email": contact.get('email', ''),
            "email": email
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email generation error: {str(e)}")


# ==================== #
# Static File Serving  #
# ==================== #

@app.get("/")
async def serve_ui():
    """Serve the main UI."""
    static_path = Path("static/index.html")
    if static_path.exists():
        return FileResponse(static_path)
    return {"message": "UI not found. Please check static file configuration."}


@app.get("/dashboard")
async def serve_dashboard():
    """Serve the lead qualification dashboard."""
    static_path = Path("static/dashboard.html")
    if static_path.exists():
        return FileResponse(static_path)
    return {"message": "Dashboard not found. Please check static file configuration."}


# Mount static files
# Note: On Vercel, static files are served directly via vercel.json routes
# This mount is kept for local development
import os
if not os.getenv("VERCEL"):
    # Only mount static files in local development
    # On Vercel, static files are served via vercel.json routes
    try:
        static_path = Path("static")
        if static_path.exists():
            app.mount("/static", StaticFiles(directory="static"), name="static")
    except Exception:
        # If static directory doesn't exist or mount fails, continue without it
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
