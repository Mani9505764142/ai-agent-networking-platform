"""
Backfill Script for Agent Embeddings

Generates 1536-dimensional vector embeddings for registered agents
whose interest_embedding is currently NULL using Google Gemini (gemini-embedding-001).

Requirements:
- Idempotent: processes only agents where interest_embedding IS NULL.
- Preserves existing agent records without creating duplicates.
- Handles missing or invalid Gemini API credentials gracefully.
- Never generates fake embeddings in production.
"""

import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.core.config import settings
from app.database.connection import SessionLocal, init_db
from app.database.repository import AgentRepository
from app.services.embedding_service import (
    EmbeddingConfigError,
    EmbeddingError,
    EmbeddingService,
    embedding_service,
)


def backfill_embeddings(
    custom_embed_service: Optional[EmbeddingService] = None,
) -> dict:
    """Backfill vector embeddings for all unembedded agents.

    Args:
        custom_embed_service: Optional custom EmbeddingService instance (e.g. for testing).

    Returns:
        dict: Summary of backfill operation (processed, skipped, total).
    """
    print("=" * 60)
    print("AI Agent Networking Platform - Embedding Backfill (Gemini)")
    print("=" * 60)

    init_db()
    db = SessionLocal()
    repo = AgentRepository(db)
    service = custom_embed_service or embedding_service

    processed_count = 0
    skipped_count = 0
    error_count = 0

    try:
        all_agents = repo.get_all()
        unembedded = [a for a in all_agents if a.interest_embedding is None]

        print(f"Total registered agents: {len(all_agents)}")
        print(f"Agents requiring embeddings: {len(unembedded)}")

        if not unembedded:
            print("All agents already possess embeddings. Nothing to backfill.")
            return {
                "processed": 0,
                "skipped": len(all_agents),
                "errors": 0,
                "total": len(all_agents),
            }

        # Check API key configuration before processing
        if not service.api_key:
            print("\n[WARNING] GEMINI_API_KEY is not configured in .env.")
            print("Real 1536-dimensional embeddings cannot be generated without a Gemini API key.")
            print("Fake embeddings are strictly disallowed.")
            print("Please configure GEMINI_API_KEY in your .env file and rerun.")
            return {
                "processed": 0,
                "skipped": len(unembedded),
                "errors": 1,
                "total": len(all_agents),
                "message": "GEMINI_API_KEY missing",
            }

        for agent in unembedded:
            try:
                print(f"Generating embedding for '{agent.company_name}'...")
                embedding = service.generate_agent_embedding(agent.interest_manifesto)
                repo.update_embedding(agent.id, embedding)
                print(f" [SUCCESS] Agent '{agent.company_name}' embedded (dims={len(embedding)}).")
                processed_count += 1
            except (EmbeddingConfigError, EmbeddingError) as e:
                print(f" [ERROR]   Failed to embed '{agent.company_name}': {e}")
                error_count += 1

        print("-" * 60)
        print(f"Backfill completed: {processed_count} processed, {error_count} errors.")
        print("=" * 60)

        return {
            "processed": processed_count,
            "skipped": len(all_agents) - len(unembedded),
            "errors": error_count,
            "total": len(all_agents),
        }
    finally:
        db.close()


if __name__ == "__main__":
    backfill_embeddings()
