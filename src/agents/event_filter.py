"""
Event Filter Agent: Determines if an event should be ignored or processed.
"""
from typing import Optional
import google.generativeai as genai
from src.models import EventFilterDecision
from src.prophetic_logger import log_llm_call, log_error


class EventFilterAgent:
    """
    Agent that decides whether an event is actionable (needs hiccup checking)
    or should be ignored (holiday, generic reminder, task without location/time).
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash-lite"):
        self.api_key = api_key
        self.model_name = model_name
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None
    
    def should_process_event(self, event: dict) -> EventFilterDecision:
        """
        Analyze an event and decide if it should be processed or ignored.
        
        Args:
            event: Event dict with name, start, location, description, etc.
        
        Returns:
            EventFilterDecision with ignore decision, reason, and confidence.
        """
        # Quick heuristic checks first (no LLM needed)
        name = event.get('name', '').lower()
        location = event.get('location', '').strip()
        description = event.get('description', '').lower()
        
        # Generic holidays/observances - ignore
        holiday_keywords = ['holiday', 'bank holiday', 'national', 'independence day', 
                           'new year', 'christmas', 'hanukkah', 'ramadan', 'easter']
        if any(keyword in name for keyword in holiday_keywords):
            return EventFilterDecision(
                should_ignore=True,
                reason="Generic holiday or observance - no action needed",
                confidence=0.95,
                event_category="holiday"
            )
        
        # Tasks/reminders without location - ignore
        task_keywords = ['homework', 'call', 'email', 'remind', 'todo', 'deadline', 'submit']
        if any(keyword in name for keyword in task_keywords) and not location:
            return EventFilterDecision(
                should_ignore=True,
                reason="Task or reminder without physical location",
                confidence=0.90,
                event_category="task"
            )
        
        # All-day events without location - likely ignore
        if not location and not event.get('start').hour:  # All-day event (00:00)
            return EventFilterDecision(
                should_ignore=True,
                reason="All-day event without location - likely non-actionable",
                confidence=0.85,
                event_category="reminder"
            )
        
        # If we have an API key, use LLM for ambiguous cases
        if self.model:
            return self._llm_filter(event)
        
        # Default: process the event (conservative approach)
        return EventFilterDecision(
            should_ignore=False,
            reason="Event has location/time - processing for hiccup detection",
            confidence=0.80,
            event_category="meeting"
        )
    
    def _llm_filter(self, event: dict) -> EventFilterDecision:
        """Use LLM to make filtering decision for ambiguous cases."""
        prompt = f"""You are an event filter agent. Analyze this calendar event and decide if it should be IGNORED or PROCESSED for travel/hiccup checking.

Event Details:
- Name: {event.get('name', 'N/A')}
- Start: {event.get('start', 'N/A')}
- Location: {event.get('location', 'N/A')}
- Description: {event.get('description', 'N/A')}

IGNORE events that are:
- Generic holidays or observances (New Year, Christmas, etc.)
- Tasks without physical location (homework, reminders, calls)
- Generic recurring items everyone has (birthdays without venue)
- All-day events without specific location

PROCESS events that are:
- Meetings with specific location/address
- Appointments (doctor, dentist, etc.)
- Social events at venues
- Travel or transportation
- Sports/entertainment events

Respond in JSON format:
{{
    "should_ignore": true/false,
    "reason": "brief explanation",
    "confidence": 0.0-1.0,
    "event_category": "holiday|task|reminder|meeting|appointment|social|other"
}}"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Log the LLM call
            log_llm_call(
                model=self.model_name,
                prompt=prompt,
                response=response_text,
                input_tokens=getattr(response, 'usage_metadata', {}).get('prompt_token_count'),
                output_tokens=getattr(response, 'usage_metadata', {}).get('candidates_token_count'),
                metadata={'agent': 'event_filter', 'event_name': event.get('name', 'Unknown')}
            )
            
            # Parse JSON from response
            import json
            text = response_text
            
            # Extract JSON if wrapped in markdown
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            data = json.loads(text)
            return EventFilterDecision(**data)
        
        except Exception as e:
            log_error(f"Event filter LLM error: {e}")
            # Fallback on error
            return EventFilterDecision(
                should_ignore=False,
                reason=f"LLM error, defaulting to process: {str(e)[:100]}",
                confidence=0.5,
                event_category="unknown"
            )
