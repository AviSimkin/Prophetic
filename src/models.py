"""
Pydantic models for agentic flow data contracts.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class EventFilterDecision(BaseModel):
    """Decision on whether an event should be processed or ignored."""
    should_ignore: bool = Field(..., description="True if event should be ignored")
    reason: str = Field(..., description="Explanation for the decision")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in decision (0-1)")
    event_category: Optional[str] = Field(None, description="Category: holiday, task, reminder, meeting, etc.")


class IssueFinding(BaseModel):
    """A single issue/hiccup detected for an event."""
    message: str = Field(..., description="Short alert message for the user")
    details: Optional[str] = Field(None, description="Additional context or explanation")
    severity: Literal['info', 'warning', 'critical'] = Field(..., description="Issue severity level")
    source: str = Field(..., description="Where this issue came from: weather, traffic, etc.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this finding")


class AlertValidation(BaseModel):
    """Validation result for a set of issue findings."""
    is_valid: bool = Field(..., description="True if alerts are relevant and not hallucinated")
    validation_notes: str = Field(..., description="Explanation of validation decision")
    priority: Literal['low', 'medium', 'high'] = Field(..., description="Overall alert priority")
    filtered_issues: list[IssueFinding] = Field(default_factory=list, description="Validated/filtered issues")
    removed_count: int = Field(0, description="Number of issues removed as invalid")
    llm_guidance: Optional[str] = Field(None, description="Feedback for future hiccup LLM calls to avoid similar mistakes")


class EventInput(BaseModel):
    """Structured event data for agent processing."""
    name: str
    start: datetime
    end: Optional[datetime] = None
    location: Optional[str] = None
    description: Optional[str] = None
    
    # User-provided details
    arrival_time: Optional[str] = None
    event_end_time: Optional[str] = None
    departure_location: Optional[str] = None
    transportation_method: Optional[str] = None


class InteractionMetrics(BaseModel):
    """Track notification/interaction frequency for rate limiting."""
    hourly_count: int = 0
    daily_count: int = 0
    last_notification: Optional[datetime] = None
    suppressed_count: int = 0
