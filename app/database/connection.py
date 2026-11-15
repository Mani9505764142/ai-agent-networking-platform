"""
Database Connection & Session Management

Supabase PostgreSQL (+ pgvector) engine for the AI Agent Networking Platform.
Configured dynamically via settings.DATABASE_URL.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

# ── Supabase PostgreSQL Database URL ─────────────────────────────────────────
# Ensure standard psycopg2 driver dialect prefix
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def get_db():
    """FastAPI dependency – yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Verify database connectivity safely for existing tables.

    Safe for pre-existing Supabase tables without dropping or recreating them.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
