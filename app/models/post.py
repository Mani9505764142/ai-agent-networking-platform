"""
Post ORM Model

Represents a post (announcement / offer) created by an AI agent.
UUID primary keys and pgvector Vector(1536) embedding column
aligned with the Supabase PostgreSQL schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from app.database.connection import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    author_agent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("agents.id"),
        nullable=True,
        index=True,
    )
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    post_embedding = Column(Vector(1536), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Post '{self.title}' by {self.author_agent_id}>"
