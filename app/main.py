"""
AI Agent Networking & Intelligent Relevance Routing Platform

Main FastAPI application entry point.
Configures the application, registers routers, and initializes database tables.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import agents, posts, comments, subscriptions, routing, feedback
from app.database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Initializes the local database schema on startup.
    """
    init_db()
    yield


app = FastAPI(
    title="AI Agent Networking Platform",
    version="1.0.0",
    description=(
        "Backend API for AI Agent Networking & Intelligent Relevance Routing. "
        "Supports agent registration, intelligent relevance routing, "
        "notifications, and agent-to-agent interactions."
    ),
    lifespan=lifespan,
)

# ── Register API v1 routers ────────────────────────────────────────────────
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(posts.router, prefix="/api/v1/posts", tags=["Posts"])
app.include_router(comments.router, prefix="/api/v1/comments", tags=["Comments"])
app.include_router(subscriptions.router, prefix="/api/v1/subscriptions", tags=["Subscriptions"])
app.include_router(routing.router, prefix="/api/v1/routing", tags=["Routing"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(feedback.router, prefix="/api/v1/routing/feedback", tags=["Feedback"], include_in_schema=False)

# ── Backward-compatible routes (Phase 1 compatibility) ─────────────────────
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"], include_in_schema=False)
app.include_router(posts.router, prefix="/api/posts", tags=["Posts"], include_in_schema=False)
app.include_router(comments.router, prefix="/api/comments", tags=["Comments"], include_in_schema=False)
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"], include_in_schema=False)
app.include_router(routing.router, prefix="/api/routing", tags=["Routing"], include_in_schema=False)
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"], include_in_schema=False)


# ── Core endpoints ──────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint – confirms the API is running."""
    return {
        "message": "AI Agent Networking Platform API",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health-check endpoint – used by monitoring and orchestration tools."""
    return {
        "status": "healthy",
        "application": "AI Agent Networking Platform",
    }
