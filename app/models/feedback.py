"""
Routing Feedback ORM Model

Represents agent feedback on relevance routing outcomes.
Allows agents to submit structured evaluations (RELEVANT, NOT_RELEVANT, USEFUL, NOT_USEFUL)
along with optional rating and qualitative comments.
Aligned with Supabase PostgreSQL schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database.connection import Base


class RoutingFeedback(Base):
    __tablename__ = "routing_feedback"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "source_agent_id",
            "target_agent_id",
            name="uq_routing_feedback_source_target_post",
        ),
    )

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    post_id = Column(
        UUID(as_uuid=False),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_agent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_agent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    routing_log_id = Column(
        UUID(as_uuid=False),
        ForeignKey("routing_logs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feedback_type = Column(String(50), nullable=False)
    comments = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<RoutingFeedback {self.id} post={self.post_id} "
            f"source={self.source_agent_id} target={self.target_agent_id} type={self.feedback_type}>"
        )
