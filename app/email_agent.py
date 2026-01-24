"""Email Generation Agent - AI-powered personalized email writing for C-PACE outreach."""

from typing import Optional, Literal
from openai import OpenAI
from pathlib import Path
import json
from pydantic import BaseModel, ValidationError

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


class EmailOutput(BaseModel):
    """Validated JSON structure for email outputs."""
    subject_line: str
    email_body: str
    sales_notes: str
    focus_type: EmailFocusType


class GeneratedEmail(BaseModel):
    """Structure for generated email results."""
    subject_line: str
    email_body: str
    sales_notes: str
    focus_type: EmailFocusType
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
    user_prompt = _build_email_prompt(contact_prompt)

    # Call the LLM
    response = client.chat.completions.create(
        model=settings.hf_model,
        messages=[
            {"role": "system", "content": skills},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=800,
        temperature=0.3,
    )
    
    raw_response = response.choices[0].message.content.strip()
    
    try:
        parsed = parse_email_json(raw_response)
    except ValueError:
        retry_prompt = _build_email_retry_prompt(contact_prompt)
        retry = client.chat.completions.create(
            model=settings.hf_model,
            messages=[
                {"role": "system", "content": skills},
                {"role": "user", "content": retry_prompt}
            ],
            max_tokens=800,
            temperature=0.0,
        )
        raw_response = retry.choices[0].message.content.strip()
        parsed = parse_email_json(raw_response)
    return GeneratedEmail(
        subject_line=parsed.subject_line,
        email_body=parsed.email_body,
        sales_notes=parsed.sales_notes,
        focus_type=parsed.focus_type,
        raw_response=raw_response,
    )


def parse_email_json(raw_text: str) -> EmailOutput:
    """Parse the AI response into validated JSON email data."""
    if not raw_text:
        raise ValueError("AI response was empty.")
    cleaned_text = _extract_json_text(raw_text)
    try:
        payload = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response was not valid JSON.") from exc

    try:
        return EmailOutput.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("AI response JSON did not match the expected schema.") from exc


def _extract_json_text(raw_text: str) -> str:
    """Extract a JSON object from a raw LLM response."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        return "\n".join(lines).strip()
    left = text.find("{")
    right = text.rfind("}")
    if left != -1 and right != -1 and right > left:
        return text[left:right + 1]
    return text


def _build_email_prompt(contact_prompt: str) -> str:
    """Build the email prompt with strict JSON requirements."""
    return f"""Generate a personalized outreach email for this contact:

{contact_prompt}

Return ONLY a single RFC8259-compliant JSON object with the following keys:
{{
  "subject_line": string,
  "email_body": string,
  "sales_notes": string,
  "focus_type": "industry" | "location" | "events" | "social"
}}

Remember:
- Keep the email under 150 words
- Make it personal and specific to their situation
- Use a warm, consultative tone
- Include one clear, low-pressure call-to-action
- Reference specific details from their profile
- Use double quotes for all keys and strings
- Do not include markdown, backticks, or commentary outside the JSON
"""


def _build_email_retry_prompt(contact_prompt: str) -> str:
    """Build a retry prompt that corrects invalid JSON output."""
    return f"""Your previous response was invalid JSON. Return ONLY valid JSON.

{contact_prompt}

Return ONLY a single JSON object with this schema:
{{
  "subject_line": string,
  "email_body": string,
  "sales_notes": string,
  "focus_type": "industry" | "location" | "events" | "social"
}}

Rules:
- Use double quotes for all keys and strings.
- No markdown, no trailing text, JSON only.
"""
