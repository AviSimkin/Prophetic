"""
Alert Validation Agent: Validates issue findings and assigns priority.
"""
from typing import Optional, List
import google.generativeai as genai
from src.models import IssueFinding, AlertValidation
from src.prophetic_logger import log_llm_call, log_error


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
        event_importance: str = "medium"
    ) -> AlertValidation:
        """
        Validate a list of issue findings and assign overall priority.
        
        Args:
            event: Event dict with name, location, date, etc.
            issues: List of issue dicts from web scraper (message, severity, details)
            event_importance: User's importance rating (if available)
        
        Returns:
            AlertValidation with filtered issues and priority assignment.
        """
        if not issues:
            return AlertValidation(
                is_valid=True,
                validation_notes="No issues to validate",
                priority="low",
                filtered_issues=[],
                removed_count=0
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
            return self._heuristic_validation(event, issue_findings, event_importance)
        
        # Use LLM for deep validation
        return self._llm_validation(event, issue_findings, event_importance)
    
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
            removed_count=removed
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
1. Check if they are relevant and accurate (no hallucinations or obvious mistakes)
2. Assign an overall priority: low, medium, or high

Event:
- Name: {event.get('name', 'N/A')}
- Date: {event.get('start', 'N/A')}
- Location: {event.get('location', 'N/A')}
- User's importance rating: {event_importance}

Alerts to validate:
{issues_text}

Validation criteria:
- REJECT alerts that are: generic/obvious, not specific to this event, contradictory, or likely hallucinated
- KEEP alerts that are: specific, actionable, verifiable, and relevant to travel/attendance

Priority guidelines:
- HIGH: Critical severity + important event (doctor, work meeting, flight)
- MEDIUM: Warning severity OR important event with info alerts
- LOW: Info severity + routine event, or single minor warning

Respond in JSON:
{{
    "is_valid": true/false,
    "validation_notes": "brief explanation of what you kept/removed",
    "priority": "low|medium|high",
    "issues_to_keep": ["message text of valid alerts"],
    "removed_count": 0
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
                removed_count=data.get('removed_count', len(issues) - len(filtered_issues))
            )
        
        except Exception as e:
            log_error(f"Alert validator LLM error: {e}")
            # Fallback to heuristic on error
            return self._heuristic_validation(event, issues, event_importance)
