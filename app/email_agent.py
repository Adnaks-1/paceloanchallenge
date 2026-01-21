"""Email Generation Agent - AI-powered personalized email writing for C-PACE outreach."""

from typing import TypedDict, Optional, Literal
from openai import OpenAI
from pathlib import Path

from app.config import get_settings


# Email focus types
EmailFocusType = Literal["industry", "location", "events", "social"]


def load_email_generation_skills() -> str:
    """Load the email generation skills/instructions from markdown file."""
    skills_path = Path("email_generation_skills.md")
    
    if not skills_path.exists():
        return "You are an email copywriter for C-PACE financing outreach."
    
    return skills_path.read_text()


def create_llm() -> OpenAI:
    """Create the OpenAI-compatible client for Hugging Face."""
    settings = get_settings()
    
    return OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=settings.huggingface_api_token,
    )


class GeneratedEmail(TypedDict):
    """Structure for generated email results."""
    subject_line: str
    email_body: str
    sales_notes: str
    focus_type: str
    raw_response: str


def format_contact_for_email(
    contact: dict,
    focus_type: EmailFocusType,
    events: Optional[list] = None,
    messages: Optional[list] = None
) -> str:
    """Format contact data into a structured prompt for email generation."""
    
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    first_name = contact.get('first_name', 'there')
    
    prompt = f"""
## Contact Information
- **Name**: {name}
- **First Name**: {first_name}
- **Title**: {contact.get('title', 'Unknown')}
- **Email**: {contact.get('email', 'Unknown')}
- **Company**: {contact.get('company', 'Unknown')}
- **Industry**: {contact.get('industry', 'Unknown')}
- **Location**: {contact.get('location', 'Unknown')}
- **State**: {contact.get('state', 'Unknown')}
- **Company Size**: {contact.get('company_size', 'Unknown')}
- **Employee Count**: {contact.get('employee_count', 'Unknown')}
- **Revenue**: ${contact.get('revenue', 'Unknown')}
"""

    # Add focus-specific data
    if focus_type == "industry":
        prompt += f"""
## Email Focus: INDUSTRY
Write an email focused on how C-PACE financing benefits the **{contact.get('industry', 'their')}** industry specifically.
Highlight industry-specific use cases, ROI, and operational benefits.
"""

    elif focus_type == "location":
        state = contact.get('state', 'their state')
        prompt += f"""
## Email Focus: LOCATION & C-PACE DEVELOPMENTS
Write an email focused on C-PACE opportunities in **{state}**.
Reference the state's C-PACE program status, recent developments, and local success stories.
Make it feel relevant to their geographic market.
"""

    elif focus_type == "events":
        prompt += """
## Email Focus: EVENTS ATTENDED
Write an email that references events they have attended and connects those interests to C-PACE.
"""
        if events and len(events) > 0:
            prompt += "\n### Events Attended:\n"
            for event in events[:5]:
                event_name = event.get('name', 'Unnamed Event')
                event_date = event.get('date', event.get('event_date', ''))
                event_location = event.get('location', '')
                event_type = event.get('type', '')
                prompt += f"- **{event_name}** ({event_date})"
                if event_location:
                    prompt += f" at {event_location}"
                if event_type:
                    prompt += f" - Type: {event_type}"
                prompt += "\n"
        else:
            prompt += "\n*No specific events data available. Write a general networking-style email.*\n"

    elif focus_type == "social":
        prompt += """
## Email Focus: SOCIAL MEDIA ACTIVITY
Write an email that references their recent social media posts or blog content.
Show genuine engagement with their thought leadership and connect it to C-PACE opportunities.
"""
        if messages and len(messages) > 0:
            # Separate social posts and blog posts
            social_posts = [m for m in messages if m.get('type') == 'social_post']
            blog_posts = [m for m in messages if m.get('type') == 'blog_post']
            
            if social_posts:
                prompt += "\n### Recent Social Posts:\n"
                for post in social_posts[:3]:
                    content = post.get('content', post.get('excerpt', ''))[:200]
                    post_date = post.get('date', post.get('posted_at', ''))
                    prompt += f"- \"{content}...\" ({post_date})\n"
            
            if blog_posts:
                prompt += "\n### Recent Blog Posts:\n"
                for post in blog_posts[:3]:
                    title = post.get('title', 'Untitled')
                    excerpt = post.get('excerpt', post.get('content', ''))[:150]
                    prompt += f"- **{title}**: \"{excerpt}...\"\n"
        else:
            prompt += "\n*No specific social media data available. Write an email that invites them to connect and share insights.*\n"

    return prompt


def generate_email(
    contact: dict,
    focus_type: EmailFocusType,
    events: Optional[list] = None,
    messages: Optional[list] = None
) -> GeneratedEmail:
    """
    Generate a personalized email for a contact.
    
    Args:
        contact: Contact data from CRM
        focus_type: Type of email focus (industry, location, events, social)
        events: Optional list of events attended
        messages: Optional list of social/blog posts
        
    Returns:
        GeneratedEmail with subject, body, and sales notes
    """
    client = create_llm()
    settings = get_settings()
    skills = load_email_generation_skills()
    
    # Format the contact data with focus type
    contact_prompt = format_contact_for_email(contact, focus_type, events, messages)
    
    # Build the generation prompt
    user_prompt = f"""Generate a personalized outreach email for this contact:

{contact_prompt}

Write the email in this exact format:

**SUBJECT LINE:** [Your subject line here]

**EMAIL BODY:**
[Complete email here]

**NOTES FOR SALES REP:** [Any helpful context or follow-up suggestions]

Remember:
- Keep the email under 150 words
- Make it personal and specific to their situation
- Use a warm, consultative tone
- Include one clear, low-pressure call-to-action
- Reference specific details from their profile"""

    # Call the LLM
    response = client.chat.completions.create(
        model=settings.hf_model,
        messages=[
            {"role": "system", "content": skills},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=800,
        temperature=0.7,  # Slightly higher for creative writing
    )
    
    raw_response = response.choices[0].message.content.strip()
    
    # Parse the response
    return parse_email_response(raw_response, focus_type)


def parse_email_response(raw_text: str, focus_type: str) -> GeneratedEmail:
    """Parse the AI response into structured email data."""
    
    subject_line = ""
    email_body = ""
    sales_notes = ""
    
    lines = raw_text.split('\n')
    current_section = None
    
    for line in lines:
        # Detect sections
        if 'SUBJECT LINE' in line.upper() and ':' in line:
            # Extract subject from same line or mark for next lines
            parts = line.split(':', 1)
            if len(parts) > 1 and parts[1].strip():
                subject_line = parts[1].strip().strip('*').strip()
            current_section = 'subject'
            continue
            
        elif 'EMAIL BODY' in line.upper():
            current_section = 'body'
            continue
            
        elif 'NOTES FOR SALES' in line.upper() or 'SALES REP' in line.upper():
            current_section = 'notes'
            # Check if notes are on same line
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    sales_notes = parts[1].strip()
            continue
        
        # Skip empty lines at section starts
        if not line.strip():
            continue
            
        # Accumulate content based on current section
        if current_section == 'subject' and not subject_line:
            subject_line = line.strip().strip('*').strip()
            current_section = None  # Subject is single line
            
        elif current_section == 'body':
            if email_body:
                email_body += '\n' + line
            else:
                email_body = line
                
        elif current_section == 'notes':
            if sales_notes:
                sales_notes += ' ' + line.strip()
            else:
                sales_notes = line.strip()
    
    # Clean up the email body
    email_body = email_body.strip()
    
    # If parsing failed, try to extract from raw text
    if not subject_line:
        subject_line = "C-PACE Financing Opportunity"
    if not email_body:
        email_body = raw_text
    if not sales_notes:
        sales_notes = "Review the email and personalize further before sending."
    
    return GeneratedEmail(
        subject_line=subject_line,
        email_body=email_body,
        sales_notes=sales_notes,
        focus_type=focus_type,
        raw_response=raw_text
    )

