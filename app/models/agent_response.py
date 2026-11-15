"""
Agent Response ORM Model

Represents responses/replies received from agents following a routed post/notification.
Aligned with Supabase PostgreSQL schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database.connection import Base


class AgentResponseRecord(Base):
    __tablename__ = "agent_responses"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    post_id = Column(
        UUID(as_uuid=False),
        ForeignKey("posts.id"),
        nullable=False,
        index=True,
    )
    responding_agent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("agents.id"),
        nullable=False,
        index=True,
    )
    routing_log_id = Column(
        UUID(as_uuid=False),
        ForeignKey("routing_logs.id"),
        nullable=True,
    )
    response_type = Column(String(50), nullable=False, default="INTERESTED")
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AgentResponse {self.id} from agent={self.responding_agent_id} on post={self.post_id}>"
