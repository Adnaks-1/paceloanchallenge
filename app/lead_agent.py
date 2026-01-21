"""Lead Qualification Agent - AI-powered analysis for C-PACE leads."""

from typing import TypedDict, Optional
from openai import OpenAI
from pathlib import Path

from app.config import get_settings


def load_lead_qualification_skills() -> str:
    """Load the lead qualification skills/instructions from markdown file."""
    skills_path = Path("lead_qualification_skills.md")
    
    if not skills_path.exists():
        return "You are a lead qualification specialist for C-PACE financing."
    
    return skills_path.read_text()


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
    strengths: list[str]
    concerns: list[str]
    recommended_actions: list[str]
    talking_points: list[str]
    events_attended: list[dict]
    sustainability_events_count: int
    raw_analysis: str


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
    user_prompt = f"""Analyze this lead for C-PACE financing qualification:

{contact_prompt}

Based on the C-PACE qualification criteria, provide your analysis in the following format:

**QUALIFICATION SCORE**: [1-10]
**QUALIFICATION LEVEL**: [Strong/Moderate/Weak]

**SUMMARY**: [2-3 sentence executive summary]

**LOCATION INELIGIBILITY**: [Location ineligibility reason]

**COMPANY INDICATORS INELIGIBILITY**: [Company indicators ineligibility reason]

**KEY STRENGTHS**:
- [Strength 1]
- [Strength 2]
- [etc.]

**KEY CONCERNS**:
- [Concern 1]
- [Concern 2]
- [etc.]

**RECOMMENDED ACTIONS**:
- [Action 1]
- [Action 2]
- [etc.]

**TALKING POINTS FOR SALES**:
- [Talking point 1]
- [Talking point 2]
- [etc.]

Be specific and reference the actual data provided. Focus on actionable insights for the sales team."""

    # Call the LLM
    response = client.chat.completions.create(
        model=settings.hf_model,
        messages=[
            {"role": "system", "content": skills},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=1024,
        temperature=0.3,  # Lower temperature for more consistent analysis
    )
    
    raw_analysis = response.choices[0].message.content.strip()
    
    # Parse the response and add events data
    analysis = parse_analysis_response(raw_analysis)
    analysis['events_attended'] = events or []
    analysis['sustainability_events_count'] = len(sustainability_events)
    
    return analysis


def parse_analysis_response(raw_text: str) -> LeadAnalysis:
    """Parse the AI response into structured data."""
    
    # Default values
    score = 5
    level = "Moderate"
    summary = ""
    strengths = []
    concerns = []
    recommended_actions = []
    talking_points = []
    
    lines = raw_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Parse score
        if 'QUALIFICATION SCORE' in line.upper():
            try:
                # Extract number from line
                import re
                numbers = re.findall(r'\d+', line)
                if numbers:
                    score = min(10, max(1, int(numbers[0])))
            except:
                pass
                
        # Parse level
        elif 'QUALIFICATION LEVEL' in line.upper():
            if 'STRONG' in line.upper():
                level = "Strong"
            elif 'WEAK' in line.upper():
                level = "Weak"
            else:
                level = "Moderate"
                
        # Parse summary
        elif 'SUMMARY' in line.upper() and ':' in line:
            summary = line.split(':', 1)[1].strip()
            current_section = 'summary'
            
        # Detect sections
        elif 'KEY STRENGTHS' in line.upper():
            current_section = 'strengths'
        elif 'KEY CONCERNS' in line.upper():
            current_section = 'concerns'
        elif 'RECOMMENDED ACTIONS' in line.upper():
            current_section = 'actions'
        elif 'TALKING POINTS' in line.upper():
            current_section = 'talking'
            
        # Parse bullet points
        elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
            item = line.lstrip('-•* ').strip()
            if item:
                if current_section == 'strengths':
                    strengths.append(item)
                elif current_section == 'concerns':
                    concerns.append(item)
                elif current_section == 'actions':
                    recommended_actions.append(item)
                elif current_section == 'talking':
                    talking_points.append(item)
                    
        # Continue summary if on that section
        elif current_section == 'summary' and not any(x in line.upper() for x in ['STRENGTHS', 'CONCERNS', 'ACTIONS', 'TALKING']):
            if summary:
                summary += ' ' + line
            else:
                summary = line
    
    # If summary is still empty, try to extract from raw text
    if not summary and raw_text:
        # Take first meaningful paragraph
        paragraphs = [p.strip() for p in raw_text.split('\n\n') if p.strip() and not p.strip().startswith('**')]
        if paragraphs:
            summary = paragraphs[0][:500]
    
    return LeadAnalysis(
        score=score,
        level=level,
        summary=summary or "Analysis completed. See details below.",
        strengths=strengths or ["Data analysis in progress"],
        concerns=concerns or ["No specific concerns identified"],
        recommended_actions=recommended_actions or ["Review lead details"],
        talking_points=talking_points or ["Discuss C-PACE financing options"],
        events_attended=[],  # Will be populated by analyze_lead
        sustainability_events_count=0,  # Will be populated by analyze_lead
    )

