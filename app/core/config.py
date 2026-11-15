"""
Application Configuration

Centralised settings loaded from environment variables / .env file.
Uses Pydantic Settings for type-safe configuration management.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings.

    Values are read from environment variables (or a `.env` file).
    Secrets are never exposed in API responses.
    """

    # ── Application ─────────────────────────────────────────────────────
    APP_NAME: str = "AI Agent Networking Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database (Supabase / PostgreSQL – connected in a later phase) ───
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/ai_agent_platform"

    # ── External API keys ───────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    COHERE_API_KEY: str = ""

    # ── Redis (optional caching / pub-sub – later phase) ────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-before-production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# Singleton settings instance used across the application
settings = Settings()
