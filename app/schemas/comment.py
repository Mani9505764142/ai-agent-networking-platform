"""
Comment Pydantic Schemas

Request and response models for agent comments on posts.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    """Payload to publish a comment on an agent post."""
    post_id: str = Field(..., description="UUID of the post being commented on")
    author_agent_id: str = Field(..., description="UUID of the author agent posting the comment")
    content: str = Field(..., min_length=1, max_length=5000, description="Comment body content")


class CommentCreateForPost(BaseModel):
    """Payload to publish a comment when post_id is provided in the URL path."""
    author_agent_id: str = Field(..., description="UUID of the author agent posting the comment")
    content: str = Field(..., min_length=1, max_length=5000, description="Comment body content")


class CommentResponse(BaseModel):
    """Standard comment representation."""
    id: str
    post_id: str
    author_agent_id: str
    content: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
