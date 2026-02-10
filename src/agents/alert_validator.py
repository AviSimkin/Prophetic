"""
Alert Validation Agent: Validates issue findings and assigns priority.
"""
from typing import Optional, List
import google.generativeai as genai
from src.models import IssueFinding, AlertValidation
from src.prophetic_logger import log_llm_call, log_error, log_info


class AlertValidatorAgent:
    """
    Agent that validates LLM-generated alerts for:
    1. Relevance and accuracy (no hallucinations)
    2. Priority assignment (low/medium/high) based on severity and event importance
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash-lite"):
        self.api_key = api_key
        self.model_name = model_name
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None
    
    def validate_alerts(
        self, 
        event: dict, 
        issues: List[dict],
        event_importance: str = "medium",
        nudges_today: int = 0,
        nudges_this_week: int = 0,
        days_until_event: int = 7
    ) -> AlertValidation:
        """
        Validate a list of issue findings and assign overall priority.
        
        Args:
            event: Event dict with name, location, date, etc.
            issues: List of issue dicts from web scraper (message, severity, details)
            event_importance: User's importance rating (if available)
            nudges_today: Number of alerts already shown today
            nudges_this_week: Number of alerts already shown this week
            days_until_event: Days until event (for urgency calculation)
        
        Returns:
            AlertValidation with filtered issues and priority assignment.
            If suppressed due to nudge limits, returns empty filtered_issues.
            Events closer in time are less likely to be suppressed.
        """
        if not issues:
            log_info(f"Alert validator: no issues for {event.get('name', 'Unknown')} (skipping LLM)")
            # Even with no issues, provide contextual validation notes
            event_date = event.get('start', '')
            event_location = event.get('location', 'unknown')
            validation_notes = f"No issues detected for {event.get('name', 'event')} on {event_date}. Location: {event_location} appears clear."
            
            log_info(f"Alert validator: suppressing notification (no issues found)")
            return AlertValidation(
                is_valid=True,
                validation_notes=validation_notes,
                priority="low",
                filtered_issues=[],
                removed_count=0,
                llm_guidance="No issues were found. Maintain current standards for issue detection."
            )
        
        # Convert to Pydantic models
        issue_findings = []
        for issue in issues:
            try:
                finding = IssueFinding(
                    message=issue.get('message', ''),
                    details=issue.get('details'),
                    severity=issue.get('severity', 'info'),
                    source=issue.get('source', 'unknown'),
                    confidence=0.8  # Default confidence
                )
                issue_findings.append(finding)
            except Exception as e:
                # Skip malformed issues
                continue
        
        if not issue_findings:
            return AlertValidation(
                is_valid=False,
                validation_notes="All issues were malformed",
                priority="low",
                filtered_issues=[],
                removed_count=len(issues)
            )
        
        # If no LLM, use heuristic validation
        if not self.model:
            log_info(f"Alert validator: using heuristic for {event.get('name', 'Unknown')} (no LLM configured)")
            result = self._heuristic_validation(event, issue_findings, event_importance)
        else:
            # Use LLM for deep validation
            log_info(f"Alert validator: invoking LLM for {event.get('name', 'Unknown')} with {len(issue_findings)} issues")
            result = self._llm_validation(event, issue_findings, event_importance)
        
        # Apply nudge suppression logic with urgency scaling (Goal Gradient Effect)
        # Closer events are less likely to be suppressed (urgency increases with proximity)
        # Suppress if: low priority AND high nudge count AND event is not imminent
        
        # Calculate urgency threshold: events within 2 days are "urgent" and harder to suppress
        is_urgent = days_until_event <= 2
        suppression_threshold = 5 if is_urgent else 3  # Higher threshold for urgent events
        
        if result.priority == "low" and nudges_today >= suppression_threshold:
            log_info(f"Alert validator: suppressing low-priority alert (already {nudges_today} alerts today, {days_until_event} days until event)")
            result.filtered_issues = []
            result.removed_count = len(issue_findings)
            result.llm_guidance = f"Alert suppressed due to notification fatigue ({nudges_today} alerts today, event in {days_until_event} days)"
        
        return result
    
    def _heuristic_validation(
        self, 
        event: dict, 
        issues: List[IssueFinding],
        event_importance: str
    ) -> AlertValidation:
        """Simple rule-based validation without LLM."""
        # Filter out low-confidence issues
        valid_issues = [issue for issue in issues if issue.confidence >= 0.6]
        removed = len(issues) - len(valid_issues)
        
        # Priority scoring
        severity_weights = {'info': 1, 'warning': 2, 'critical': 3}
        importance_weights = {'low': 1, 'medium': 2, 'high': 3}
        
        max_severity = max([severity_weights[i.severity] for i in valid_issues], default=0)
        importance_score = importance_weights.get(event_importance, 2)
        
        total_score = max_severity * importance_score
        
        if total_score >= 7:  # critical * high
            priority = "high"
        elif total_score >= 4:  # warning * medium or higher
            priority = "medium"
        else:
            priority = "low"
        
        return AlertValidation(
            is_valid=len(valid_issues) > 0,
            validation_notes=f"Heuristic: {len(valid_issues)} valid issues, max severity: {max_severity}",
            priority=priority,
            filtered_issues=valid_issues,
            removed_count=removed,
            llm_guidance=None  # Heuristic mode doesn't provide LLM guidance
        )
    
    def _llm_validation(
        self, 
        event: dict, 
        issues: List[IssueFinding],
        event_importance: str
    ) -> AlertValidation:
        """Use LLM to validate alerts and assign priority."""
        issues_text = "\n".join([
            f"- [{i.severity.upper()}] {i.message} (Source: {i.source})"
            + (f"\n  Details: {i.details}" if i.details else "")
            for i in issues
        ])
        
        prompt = f"""You are an alert validation agent. Review these alerts for a calendar event and:
1. First, infer the event's importance (low/medium/high) based on the event type, name, and context
2. Check if alerts are relevant and accurate (no hallucinations or obvious mistakes)
3. Assign an overall priority: low, medium, or high

Event Importance Guidelines:
- HIGH importance: Medical appointments, work meetings, flights, legal appointments, job interviews, important presentations
- MEDIUM importance: Regular meetings, social gatherings with plans, classes, sports practice, routine appointments
- LOW importance: Casual coffee chats, informal hangouts, optional social events, errands

Few-shot examples:
1. Event: "Doctor appointment", Date: "2026-02-15 09:00", Location: "Medical Center"
   Inferred importance: high (medical appointment)
   Alert: "Heavy rain expected" (severity: warning)
   → {{"is_valid": true, "priority": "high", "event_importance": "high", "issues_to_keep": ["Heavy rain expected"], "validation_notes": "Weather risk relevant for health appointment", "llm_guidance": "Good - weather impacts medical travel"}}

2. Event: "Coffee chat", Date: "2026-02-20 15:00", Location: "Cafe Downtown"
   Inferred importance: low (casual social)
   Alert: "Light drizzle possible" (severity: info)
   → {{"is_valid": false, "priority": "low", "event_importance": "low", "issues_to_keep": [], "removed_count": 1, "validation_notes": "Minor weather for casual event", "llm_guidance": "Don't report routine weather for informal meetings"}}

3. Event: "Business meeting", Date: "2026-03-01 10:00", Location: "Office Park"
   Inferred importance: high (work meeting)
   Alert: "Major soccer game at nearby stadium causing traffic delays" (severity: critical)
   → {{"is_valid": true, "priority": "high", "event_importance": "high", "issues_to_keep": ["Major soccer game at nearby stadium causing traffic delays"], "validation_notes": "Verified event-specific traffic impact", "llm_guidance": "Good - specific local event with travel impact"}}

Event to analyze:
- Name: {event.get('name', 'N/A')}
- Date: {event.get('start', 'N/A')}
- Location: {event.get('location', 'N/A')}
- Description: {event.get('description', 'N/A')}

Alerts to validate:
{issues_text}

Validation criteria:
- REJECT alerts that are: generic/obvious, not specific to this event, contradictory, or likely hallucinated
- KEEP alerts that are: specific, actionable, verifiable, and relevant to travel/attendance

Priority guidelines (combine inferred importance + alert severity):
- HIGH: Critical severity + high importance event, OR warning severity + high importance with multiple issues
- MEDIUM: Warning severity + medium importance, OR info severity + high importance event
- LOW: Info severity + low/medium importance, OR single minor warning for routine events

Respond in JSON:
{{
    "event_importance": "low|medium|high",
    "is_valid": true/false,
    "validation_notes": "brief explanation of importance inference and what you kept/removed",
    "priority": "low|medium|high",
    "issues_to_keep": ["message text of valid alerts"],
    "removed_count": 0,
    "llm_guidance": "specific feedback for the hiccup-checking LLM to avoid similar mistakes (e.g., 'No soccer game at Sammy Ofer on this date - avoid hallucinating sports events', or 'Weather is normal - don't report routine conditions')"
}}"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Log the LLM call
            log_llm_call(
                model=self.model_name,
                prompt=prompt,
                response=response_text,
                input_tokens=getattr(getattr(response, 'usage_metadata', None), 'prompt_token_count', None),
                output_tokens=getattr(getattr(response, 'usage_metadata', None), 'candidates_token_count', None),
                metadata={'agent': 'alert_validator', 'event_name': event.get('name', 'Unknown'), 'issue_count': len(issues)}
            )
            
            import json
            text = response_text
            
            # Extract JSON
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            data = json.loads(text)
            
            # Filter issues based on LLM's decision
            kept_messages = set(data.get('issues_to_keep', []))
            filtered_issues = [
                issue for issue in issues 
                if issue.message in kept_messages
            ]
            
            return AlertValidation(
                is_valid=data.get('is_valid', True),
                validation_notes=data.get('validation_notes', 'LLM validation complete'),
                priority=data.get('priority', 'medium'),
                filtered_issues=filtered_issues,
                removed_count=data.get('removed_count', len(issues) - len(filtered_issues)),
                llm_guidance=data.get('llm_guidance')
            )
        
        except Exception as e:
            log_error(f"Alert validator LLM error: {e}")
            # Fallback to heuristic on error
            return self._heuristic_validation(event, issues, event_importance)
