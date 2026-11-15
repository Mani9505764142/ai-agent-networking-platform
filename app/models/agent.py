"""
Agent ORM Model

Represents an AI agent registered on the platform.
UUID primary keys and pgvector Vector(1536) embedding column
aligned with the Supabase PostgreSQL schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from app.database.connection import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    company_name = Column(String(255), unique=True, nullable=False, index=True)
    industry_category = Column(String(255), nullable=False)
    webhook_url = Column(Text, nullable=False, default="")
    interest_manifesto = Column(Text, nullable=False)
    interest_embedding = Column(Vector(1536), nullable=True)
    trust_score = Column(Float, nullable=True, default=1.0)
    is_active = Column(Boolean, nullable=True, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Agent {self.company_name} ({self.id})>"
