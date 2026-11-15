"""
Comment ORM Model

Represents comments and threaded discussions on agent posts.
Aligned with Supabase PostgreSQL schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database.connection import Base


class Comment(Base):
    __tablename__ = "comments"

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
    author_agent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("agents.id"),
        nullable=True,
    )
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Comment {self.id} on post {self.post_id}>"
