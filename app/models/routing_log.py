"""
Routing Log ORM Model

Represents intelligent routing records, relevance scores, and webhook delivery status.
Aligned with Supabase PostgreSQL schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database.connection import Base


class RoutingLog(Base):
    __tablename__ = "routing_logs"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    post_id = Column(
        UUID(as_uuid=False),
        ForeignKey("posts.id"),
        nullable=True,
        index=True,
    )
    target_agent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("agents.id"),
        nullable=True,
    )
    vector_score = Column(Float, nullable=False)
    rerank_score = Column(Float, nullable=False)
    status = Column(String(50), nullable=True, default="PENDING")
    delivery_attempts = Column(Integer, nullable=True, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<RoutingLog {self.id} post={self.post_id} target={self.target_agent_id} status={self.status}>"
