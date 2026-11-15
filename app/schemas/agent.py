"""
Agent Pydantic Schemas

Request and response models for the Agent API.
Includes input validation, default values, and serialization configs.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """Request body for POST /api/v1/agents/register."""
    company_name: str = Field(..., min_length=1, max_length=255, description="Unique company name for the agent")
    industry_category: str = Field(..., min_length=1, max_length=255, description="Industry sector of the agent")
    webhook_url: Optional[str] = Field(None, max_length=500, description="Optional webhook URL for agent notifications")
    interest_manifesto: str = Field(..., min_length=1, description="Description of agent interests and preferences")
    trust_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Initial trust score between 0.0 and 1.0")


class AgentUpdate(BaseModel):
    """Request body for PUT /api/v1/agents/{agent_id}."""
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry_category: Optional[str] = Field(None, min_length=1, max_length=255)
    webhook_url: Optional[str] = Field(None, max_length=500)
    interest_manifesto: Optional[str] = Field(None, min_length=1)
    trust_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class AgentResponse(BaseModel):
    """Response body returned for agent endpoints."""
    id: str
    company_name: str
    industry_category: str
    webhook_url: Optional[str] = None
    interest_manifesto: str
    interest_embedding: Optional[Any] = None
    trust_score: float
    is_active: Optional[bool] = True
    created_at: datetime

    model_config = {"from_attributes": True}
