"""
Agent Response Pydantic Schemas

Request and response models for agent responses/replies to routed posts.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentResponseCreate(BaseModel):
    """Payload for POST /api/v1/routing/responses."""
    post_id: str = Field(..., min_length=1, description="UUID of the post being responded to")
    responding_agent_id: str = Field(..., min_length=1, description="UUID of the responding agent")
    response_type: str = Field(default="INTERESTED", max_length=50, description="Type: INTERESTED, OFFER, PROPOSAL, DECLINED")
    content: str = Field(..., min_length=1, description="Response proposal or message content")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured metadata")


class AgentResponseDetail(BaseModel):
    """Detailed response model returned for agent responses."""
    id: str
    post_id: str
    responding_agent_id: str
    routing_log_id: Optional[str] = None
    response_type: str
    content: str
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}
