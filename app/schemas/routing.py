"""
Routing Pydantic Schemas

Request and response models for intelligent relevance routing endpoints,
reranking evaluations, and webhook delivery status.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RoutedAgentItem(BaseModel):
    """Details of an agent matched and reranked for a routed post."""
    agent_id: str
    company_name: str
    industry_category: str
    webhook_url: Optional[str] = None
    similarity_score: float = Field(..., description="Cosine vector similarity score")
    vector_score: Optional[float] = Field(None, description="Raw semantic similarity score")
    rerank_score: Optional[float] = Field(None, description="Multi-factor contextual rerank score")
    trust_score: float = Field(..., description="Agent trust score")
    delivery_status: Optional[str] = Field("NOTIFIED", description="Webhook delivery status (DELIVERED, FAILED, SKIPPED, NOTIFIED)")
    delivery_attempts: Optional[int] = Field(0, description="Number of webhook attempts made")
    delivery_error: Optional[str] = Field(None, description="Error message if delivery failed")
    breakdown: Optional[Dict[str, Any]] = Field(None, description="Explainable scoring component breakdown")


class RoutingResponse(BaseModel):
    """Response returned when a post is routed."""
    post_id: str
    post_title: str
    author_agent_id: str
    candidate_count: Optional[int] = Field(0, description="Total candidates evaluated before filtering")
    routed_count: int = Field(..., description="Number of agents meeting the relevance threshold")
    relevance_threshold: Optional[float] = Field(0.40, description="Cutoff threshold applied")
    results: List[RoutedAgentItem]
    status: str = "success"


class RoutingLogResponse(BaseModel):
    """Response model for historical routing decisions and delivery records."""
    id: str
    post_id: str
    target_agent_id: str
    vector_score: float
    rerank_score: float
    status: str
    delivery_attempts: Optional[int] = 0
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
