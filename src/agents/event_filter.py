"""
Event Filter Agent: Determines if an event should be ignored or processed.
"""
from typing import Optional
import google.generativeai as genai
from src.models import EventFilterDecision
from src.prophetic_logger import log_llm_call, log_error, log_info


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
            cached_decision = self._cache[cache_key]
            log_info(f"Event filter cache hit for {event.get('name', 'Unknown')}: should_ignore={cached_decision.should_ignore}")
            return cached_decision
        
        # Cache miss - make new decision and log it
        log_info(f"Event filter cache miss for {event.get('name', 'Unknown')}, calling LLM")
        
        # If we have an API key, use LLM for all decisions (minimal heuristics)
        if self.model:
            return self._llm_filter(event, cache_key)
        
        # Default: process the event (conservative approach)
        decision = EventFilterDecision(
            should_ignore=False,
            reason="Event has location/time - processing for hiccup detection",
            confidence=0.80,
            event_category="meeting"
        )
        log_info(f"Event filter (default): {event.get('name', 'Unknown')} -> PROCESS (no LLM, conservative)")
        self._cache[cache_key] = decision
        return decision
    
    def _llm_filter(self, event: dict, cache_key: str) -> EventFilterDecision:
        """Use LLM to make filtering decision for ambiguous cases."""
        prompt = f"""You are an event filter agent. Analyze this calendar event and decide if it should be IGNORED or PROCESSED for travel/hiccup checking.

Few-shot examples:
1. Event: "Holiday - Independence Day", Location: None, Time: All-day
   → {{"should_ignore": true, "reason": "Generic holiday", "confidence": 0.95, "event_category": "holiday"}}

2. Event: "Dentist appointment", Location: None, Time: "14:00"
   → {{"should_ignore": false, "reason": "Medical appointment needs location details", "confidence": 0.90, "event_category": "appointment"}}

3. Event: "Homework submission - CS101", Location: None, Time: "23:59"
   → {{"should_ignore": true, "reason": "Task without physical location, no hiccup assessment needed", "confidence": 0.95, "event_category": "task"}}

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
- Ambiguous all-day events that might be business meetings

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
            
            # Log the filtering decision (only once, not on cache hits)
            if decision.should_ignore:
                from src.prophetic_logger import log_event
                log_event('event_filtered', event.get('name', 'Unknown'), {
                    'reason': decision.reason,
                    'category': decision.event_category,
                    'confidence': decision.confidence
                })
            
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
