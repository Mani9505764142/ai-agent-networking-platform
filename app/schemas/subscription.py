"""
Subscription Pydantic Schemas

Request and response models for agent-to-agent subscriptions and following relationships.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SubscriptionCreate(BaseModel):
    """Payload to subscribe one agent to another."""
    subscriber_agent_id: str = Field(..., description="UUID of the agent subscribing (follower)")
    target_agent_id: str = Field(..., description="UUID of the agent being followed (target)")


class SubscriptionResponse(BaseModel):
    """Standard representation of an agent subscription."""
    id: str
    subscriber_agent_id: str
    target_agent_id: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionDeleteResponse(BaseModel):
    """Response returned upon successfully removing a subscription."""
    message: str
    subscriber_agent_id: str
    target_agent_id: str


class SubscriptionListResponse(BaseModel):
    """List of subscriptions with count."""
    total: int
    items: list[SubscriptionResponse]
