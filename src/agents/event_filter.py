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
        self._cache = {}  # Cache decisions by event identifier
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None
    
    def _get_cache_key(self, event: dict) -> str:
        """Generate cache key from event name and date."""
        return f"{event.get('name', '')}_{event.get('start', '')}"
    
    def should_process_event(self, event: dict) -> EventFilterDecision:
        """Analyze an event and decide if it should be processed or ignored.
        
        Uses cache to avoid duplicate LLM calls for the same event.
        
        Args:
            event: Event dict with name, start, location, description, etc.
        
        Returns:
            EventFilterDecision with ignore decision, reason, and confidence.
        """
        # Check cache first
        cache_key = self._get_cache_key(event)
        if cache_key in self._cache:
            return self._cache[cache_key]
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
        
        # All-day events: check if they're obvious reminders/holidays first
        is_all_day = event.get('start').hour == 0 if event.get('start') else False
        
        if is_all_day:
            # Check for obvious non-actionable all-day events
            obvious_ignore_keywords = ['holiday', 'observance', 'birthday', 'anniversary', 
                                      'payroll', 'payday', 'invoice', 'bill', 'homework', 
                                      'assignment', 'reminder', 'note to self']
            if any(keyword in name for keyword in obvious_ignore_keywords):
                return EventFilterDecision(
                    should_ignore=True,
                    reason="All-day generic event (holiday/reminder/task) - no action needed",
                    confidence=0.90,
                    event_category="generic_all_day"
                )
            
            # For other all-day events without location: ask for time and location
            if not location:
                return EventFilterDecision(
                    should_ignore=False,
                    reason="All-day event without clear time/location - asking user for details",
                    confidence=0.75,
                    event_category="ambiguous_all_day"
                )
        
        # All-day events with location - process them (likely meetings/events)
        
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

Few-shot examples:
1. Event: "Holiday - Independence Day", Location: None → IGNORE (generic holiday)
2. Event: "Dentist appointment", Location: "Rabin Clinic, Tel Aviv", Time: "14:00" → PROCESS (medical appointment with location)
3. Event: "Call with Mom", Location: None → IGNORE (task/reminder without location)
4. Event: "Business lunch", Location: "Azrieli Mall Haifa" → PROCESS (business meeting with location, even if missing time)
5. Event: "Sammy Ofer Game" (all-day), Location: "Sammy Ofer Stadium" → PROCESS (sports event with location)
6. Event: "Homework due" (all-day), Location: None → IGNORE (obvious assignment)
7. Event: "Team conference" (all-day), Location: None → PROCESS (ask user for time/location)

Event to analyze:
- Name: {event.get('name', 'N/A')}
- Start: {event.get('start', 'N/A')}
- Location: {event.get('location', 'N/A')}
- Description: {event.get('description', 'N/A')}

IGNORE events that are:
- Generic holidays or observances (New Year, Christmas, Independence Day, etc.)
- Tasks without physical location (homework, reminders, calls, emails, assignments)
- Generic recurring items everyone has (birthdays, anniversaries, payroll dates without venue)

PROCESS events that are:
- Meetings/appointments with specific location/address (even without time)
- All-day events with location (business events, conferences, sports)
- Appointments (doctor, dentist, lawyer, etc.)
- Social events at venues (dinners, parties, celebrations)
- Sports/entertainment events
- Travel or transportation

For ambiguous all-day events (no location):
- If contains: holiday, birthday, homework, reminder, assignment, payroll → IGNORE
- Otherwise (e.g., "Team meeting", "Conference", business terms) → PROCESS (ask for time/location)

Respond in JSON format:
{{
    "should_ignore": true/false,
    "reason": "brief explanation",
    "confidence": 0.0-1.0,
    "event_category": "holiday|task|reminder|meeting|appointment|social|sports|other"
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
            decision = EventFilterDecision(**data)
            # Cache the decision
            self._cache[cache_key] = decision
            return decision
        
        except Exception as e:
            log_error(f"Event filter LLM error: {e}")
            # Fallback on error
            decision = EventFilterDecision(
                should_ignore=False,
                reason=f"LLM error, defaulting to process: {str(e)[:100]}",
                confidence=0.5,
                event_category="unknown"
            )
            self._cache[cache_key] = decision
            return decision
