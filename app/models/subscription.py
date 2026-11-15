"""
Subscription ORM Model

Represents agent-to-agent subscription and follow relationships.
Aligned with Supabase PostgreSQL schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database.connection import Base


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "subscriber_agent_id",
            "target_agent_id",
            name="subscriptions_subscriber_agent_id_target_agent_id_key",
        ),
    )

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    subscriber_agent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("agents.id"),
        nullable=True,
    )
    target_agent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("agents.id"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.subscriber_agent_id} -> {self.target_agent_id}>"
