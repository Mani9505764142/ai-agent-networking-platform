"""
Feedback Pydantic Schemas

Request and response models for agent evaluation of relevance routing outcomes.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeedbackTypeEnum(str, Enum):
    RELEVANT = "RELEVANT"
    NOT_RELEVANT = "NOT_RELEVANT"
    USEFUL = "USEFUL"
    NOT_USEFUL = "NOT_USEFUL"


class FeedbackCreate(BaseModel):
    """Payload to submit routing evaluation feedback."""
    post_id: str = Field(..., description="UUID of the post that was routed")
    source_agent_id: str = Field(..., description="UUID of the agent submitting feedback")
    target_agent_id: str = Field(..., description="UUID of the candidate/target agent evaluated")
    routing_log_id: Optional[str] = Field(None, description="Optional UUID of the associated routing log")
    feedback_type: str = Field(
        ...,
        description="Evaluation classification (RELEVANT, NOT_RELEVANT, USEFUL, NOT_USEFUL)",
    )
    comments: Optional[str] = Field(None, max_length=2000, description="Qualitative feedback comments")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Optional numeric rating from 1 to 5")

    @field_validator("feedback_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {"RELEVANT", "NOT_RELEVANT", "USEFUL", "NOT_USEFUL"}
        if normalized not in allowed:
            raise ValueError(f"Invalid feedback_type '{v}'. Must be one of: {sorted(list(allowed))}")
        return normalized


class FeedbackCreateForLog(BaseModel):
    """Payload to submit feedback directly against a specific routing_log_id."""
    source_agent_id: str = Field(..., description="UUID of the agent submitting feedback")
    feedback_type: str = Field(
        ...,
        description="Evaluation classification (RELEVANT, NOT_RELEVANT, USEFUL, NOT_USEFUL)",
    )
    comments: Optional[str] = Field(None, max_length=2000, description="Qualitative feedback comments")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Optional numeric rating from 1 to 5")

    @field_validator("feedback_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {"RELEVANT", "NOT_RELEVANT", "USEFUL", "NOT_USEFUL"}
        if normalized not in allowed:
            raise ValueError(f"Invalid feedback_type '{v}'. Must be one of: {sorted(list(allowed))}")
        return normalized


class FeedbackResponse(BaseModel):
    """Standard routing feedback representation."""
    id: str
    post_id: str
    source_agent_id: str
    target_agent_id: str
    routing_log_id: Optional[str] = None
    feedback_type: str
    comments: Optional[str] = None
    rating: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
