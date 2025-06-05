"""
📋 Feedback Schema - #201 Feedback-Ingest
Pydantic models for user feedback capture and validation
"""

from pydantic import BaseModel, Field
from typing import Optional
import time


class Feedback(BaseModel):
    """User feedback on LLM responses"""
    id: str = Field(..., description="Unique response ID from original request")
    score: int = Field(..., ge=-1, le=1, description="-1 = 👎, 0 = neutral, 1 = 👍")
    timestamp: Optional[float] = Field(default_factory=time.time, description="Unix timestamp of feedback")
    user_session: Optional[str] = Field(None, description="Optional user session ID for analytics")
    comment: Optional[str] = Field(None, max_length=500, description="Optional text feedback")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "req_abc123_20250605",
                "score": 1,
                "comment": "Great explanation of Python decorators!"
            }
        }


class FeedbackResponse(BaseModel):
    """Response after feedback submission"""
    accepted: bool = True
    feedback_id: str = Field(..., description="Confirmed feedback ID")
    message: str = "Feedback received - thank you!"
    timestamp: float = Field(default_factory=time.time)


class FeedbackStats(BaseModel):
    """Aggregated feedback statistics"""
    total_feedback: int
    positive_count: int
    negative_count: int
    neutral_count: int
    avg_score: float
    feedback_rate: float  # feedback_count / total_requests
    last_updated: float = Field(default_factory=time.time) 