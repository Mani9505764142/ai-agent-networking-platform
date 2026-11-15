"""
Post Pydantic Schemas

Request and response models for the Post API.
Includes input validation and serialization configs.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    """Request body for POST /api/v1/posts."""
    author_agent_id: str = Field(..., min_length=1, description="UUID of the authoring agent")
    title: str = Field(..., min_length=1, max_length=500, description="Post title")
    content: str = Field(..., min_length=1, description="Post body content")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration timestamp")


class PostResponse(BaseModel):
    """Response body returned for post endpoints."""
    id: str
    author_agent_id: str
    title: str
    content: str
    post_embedding: Optional[Any] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
