"""Lead Qualification Agent - AI-powered analysis for C-PACE leads."""

from typing import TypedDict, Optional
from openai import OpenAI
from pathlib import Path
import json
import logging
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)


def load_lead_qualification_skills(include_sections: list[str] | None = None) -> str:
    """Load lead qualification skills from JSON (preferred) or markdown.

    JSON allows context management: pass include_sections to inject only
    the sections you need (e.g. omit "state_eligibility" or "examples" when
    near token limits). Default order: persona, what_is_cpace, qualification_criteria,
    state_eligibility, output_format, guidelines, examples.
    """
    json_path = Path("lead_qualification_skills.json")
    md_path = Path("lead_qualification_skills.md")

    if json_path.exists():
        try:
            data = json.loads(json_path.read_text())
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            # Default: all sections in fixed order
            section_order = [
                "persona", "what_is_cpace", "qualification_criteria",
                "state_eligibility", "output_format", "guidelines", "examples"
            ]
            keys = include_sections if include_sections is not None else section_order
            parts = []
            for k in keys:
                if k in data and data[k]:
                    parts.append(data[k].strip())
            return "\n\n---\n\n".join(parts) if parts else _fallback_skills()
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to load lead_qualification_skills.json: %s; falling back to .md", e)

    if md_path.exists():
        return md_path.read_text()
    return _fallback_skills()


def _fallback_skills() -> str:
    """Minimal system prompt when no skills file is present."""
    return "You are a lead qualification specialist for C-PACE financing."


def create_llm() -> OpenAI:
    """Create the OpenAI-compatible client for Hugging Face."""
    settings = get_settings()
    
    return OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=settings.huggingface_api_token,
    )


class LeadAnalysis(TypedDict):
    """Structure for lead analysis results."""
    score: int
    level: str  # Strong / Moderate / Weak
    summary: str
    location_ineligibility: str
    company_indicators_ineligibility: str
    strengths: list[str]
    concerns: list[str]
    recommended_actions: list[str]
    talking_points: list[str]
    events_attended: list[dict]
    sustainability_events_count: int
    raw_analysis: str


class LeadAnalysisOutput(BaseModel):
    """Validated JSON structure for lead analysis outputs."""
    score: int
    level: str  # Strong / Moderate / Weak
    summary: str
    location_ineligibility: str
    company_indicators_ineligibility: str
    strengths: list[str]
    concerns: list[str]
    recommended_actions: list[str]
    talking_points: list[str]


# Keywords that indicate sustainability-focused events
SUSTAINABILITY_KEYWORDS = [
    'sustainability', 'sustainable', 'green', 'energy', 'renewable', 
    'solar', 'wind', 'efficiency', 'carbon', 'climate', 'environmental',
    'esg', 'clean', 'eco', 'conservation', 'net zero', 'decarbonization',
    'leed', 'pace', 'c-pace', 'building performance', 'retrofit',
    'hvac', 'lighting', 'insulation', 'smart building'
]


def is_sustainability_event(event: dict) -> bool:
    """Check if an event is sustainability-focused based on keywords."""
    event_name = (event.get('name', '') or '').lower()
    event_description = (event.get('description', '') or '').lower()
    event_type = (event.get('type', '') or '').lower()
    
    combined_text = f"{event_name} {event_description} {event_type}"
    
    return any(keyword in combined_text for keyword in SUSTAINABILITY_KEYWORDS)


def format_contact_for_analysis(contact: dict, counts: Optional[dict] = None, events: Optional[list] = None) -> str:
    """Format contact data into a structured prompt for the AI."""
    
    # Extract key fields
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    
    prompt = f"""
## Contact Information
- **Name**: {name}
- **Title**: {contact.get('title', 'Unknown')}
- **Email**: {contact.get('email', 'Unknown')}
- **Phone**: {contact.get('phone', 'Unknown')}
- **Location**: {contact.get('location', 'Unknown')}
- **State**: {contact.get('state', 'Unknown')}

## Company Information
- **Company**: {contact.get('company', 'Unknown')}
- **Industry**: {contact.get('industry', 'Unknown')}
- **Company Size**: {contact.get('company_size', 'Unknown')}
- **Employee Count**: {contact.get('employee_count', 'Unknown')}
- **Revenue**: ${contact.get('revenue', 'Unknown')}

## Current CRM Score
- **Existing C-PACE Fit Score**: {contact.get('c_pace_fit_score', 'Not set')}/10
"""

    # Add engagement data if available
    if counts:
        prompt += f"""
## Engagement Metrics
- **Social Posts**: {counts.get('social_posts', 0)}
- **Blog Posts**: {counts.get('blog_posts', 0)}
- **Events Attended**: {counts.get('events', 0)}
"""

    # Add events data if available
    if events and len(events) > 0:
        sustainability_events = [e for e in events if is_sustainability_event(e)]
        other_events = [e for e in events if not is_sustainability_event(e)]
        
        prompt += f"""
## Events Attended ({len(events)} total)
"""
        if sustainability_events:
            prompt += f"""
### Sustainability-Focused Events ({len(sustainability_events)}) - HIGH VALUE FOR C-PACE
"""
            for event in sustainability_events[:10]:  # Limit to 10
                event_name = event.get('name', 'Unnamed Event')
                event_date = event.get('date', event.get('event_date', 'Unknown date'))
                event_location = event.get('location', '')
                prompt += f"- **{event_name}** ({event_date}){f' - {event_location}' if event_location else ''}\n"
        
        if other_events:
            prompt += f"""
### Other Events ({len(other_events)})
"""
            for event in other_events[:5]:  # Limit to 5
                event_name = event.get('name', 'Unnamed Event')
                event_date = event.get('date', event.get('event_date', 'Unknown date'))
                prompt += f"- {event_name} ({event_date})\n"
        
        prompt += f"""
**Note**: This contact has attended {len(sustainability_events)} sustainability-focused events, which indicates strong alignment with C-PACE financing interests. Consider adding +1 to the qualification score for sustainability engagement.
"""

    return prompt


def analyze_lead(contact: dict, counts: Optional[dict] = None, events: Optional[list] = None) -> LeadAnalysis:
    """
    Analyze a lead using AI to determine C-PACE qualification.
    
    Args:
        contact: Contact data from CRM
        counts: Optional engagement counts (social_posts, blog_posts, events)
        events: Optional list of events attended by the contact
        
    Returns:
        LeadAnalysis with score, level, and detailed analysis
    """
    client = create_llm()
    settings = get_settings()
    skills = load_lead_qualification_skills()
    
    # Calculate sustainability events
    sustainability_events = []
    if events:
        sustainability_events = [e for e in events if is_sustainability_event(e)]
    
    # Format the contact data
    contact_prompt = format_contact_for_analysis(contact, counts, events)
    
    # Build the analysis prompt
    user_prompt = _build_analysis_prompt(contact_prompt)

    # Call the LLM
    response = client.chat.completions.create(
        model=settings.hf_model,
        messages=[
            {"role": "system", "content": skills},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=1024,
        temperature=0.2,
    )
    
    raw_analysis = response.choices[0].message.content.strip()
    
    try:
        parsed = parse_analysis_json(raw_analysis)
    except ValueError:
        retry_prompt = _build_analysis_retry_prompt(contact_prompt)
        retry = client.chat.completions.create(
            model=settings.hf_model,
            messages=[
                {"role": "system", "content": skills},
                {"role": "user", "content": retry_prompt}
            ],
            max_tokens=1024,
            temperature=0.0,
        )
        raw_analysis = retry.choices[0].message.content.strip()
        parsed = parse_analysis_json(raw_analysis)
    analysis: LeadAnalysis = {
        "score": parsed.score,
        "level": parsed.level,
        "summary": parsed.summary,
        "location_ineligibility": parsed.location_ineligibility,
        "company_indicators_ineligibility": parsed.company_indicators_ineligibility,
        "strengths": parsed.strengths,
        "concerns": parsed.concerns,
        "recommended_actions": parsed.recommended_actions,
        "talking_points": parsed.talking_points,
        "events_attended": events or [],
        "sustainability_events_count": len(sustainability_events),
        "raw_analysis": raw_analysis,
    }
    
    return analysis


def parse_analysis_json(raw_text: str) -> LeadAnalysisOutput:
    """Parse the AI response into validated JSON analysis data."""
    if not raw_text:
        raise ValueError("AI response was empty.")
    cleaned_text = _extract_json_text(raw_text)
    try:
        payload = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        logger.warning("AI analysis JSON parse failed. Response: %s", raw_text[:2000])
        raise ValueError("AI response was not valid JSON.") from exc

    try:
        return LeadAnalysisOutput.model_validate(payload)
    except ValidationError as exc:
        logger.warning("AI analysis JSON validation failed. Response: %s", raw_text[:2000])
        raise ValueError("AI response JSON did not match the expected schema.") from exc


def _extract_json_text(raw_text: str) -> str:
    """Extract a JSON object from a raw LLM response."""
    text = raw_text.strip()
    if text.startswith("```"):
        # Strip Markdown code fences like ```json ... ```
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        return "\n".join(lines).strip()
    left = text.find("{")
    right = text.rfind("}")
    if left != -1 and right != -1 and right > left:
        return text[left:right + 1]
    return text


def _build_analysis_prompt(contact_prompt: str) -> str:
    """Build the analysis prompt with strict JSON requirements."""
    return f"""Analyze this lead for C-PACE financing qualification:

{contact_prompt}

Return ONLY a single RFC8259-compliant JSON object with the following keys:
{{
  "score": number (1-10),
  "level": "Strong" | "Moderate" | "Weak",
  "summary": string,
  "location_ineligibility": string,
  "company_indicators_ineligibility": string,
  "strengths": [string, ...],
  "concerns": [string, ...],
  "recommended_actions": [string, ...],
  "talking_points": [string, ...]
}}

Rules:
- Use double quotes for all keys and strings.
- Do not include markdown, backticks, or commentary outside the JSON.
"""


def _build_analysis_retry_prompt(contact_prompt: str) -> str:
    """Build a retry prompt that corrects invalid JSON output."""
    return f"""Your previous response was invalid JSON. Return ONLY valid JSON.

{contact_prompt}

Return ONLY a single JSON object with this schema:
{{
  "score": number (1-10),
  "level": "Strong" | "Moderate" | "Weak",
  "summary": string,
  "location_ineligibility": string,
  "company_indicators_ineligibility": string,
  "strengths": [string, ...],
  "concerns": [string, ...],
  "recommended_actions": [string, ...],
  "talking_points": [string, ...]
}}

Rules:
- Use double quotes for all keys and strings.
- No markdown, no trailing text, JSON only.
"""
