"""
Embedding Service

Generates vector embeddings for agent profiles and posts using
Google Gemini's official Python SDK (google-genai) and the
gemini-embedding-001 model configured for 1536 dimensions.
Powers semantic similarity search and intelligent relevance routing.
"""

from typing import List, Optional
import logging
from google import genai
from google.genai import types, errors

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingError(Exception):
    """Base exception for embedding service errors."""
    pass


class EmbeddingConfigError(EmbeddingError):
    """Raised when the embedding service is improperly configured (e.g., missing API key)."""
    pass


class EmbeddingAPIError(EmbeddingError):
    """Raised when the upstream Gemini API call fails."""
    pass


class EmbeddingService:
    """Service for generating high-dimensional text embeddings via Google Gemini."""

    def __init__(self, api_key: Optional[str] = None, model: str = EMBEDDING_MODEL):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        """Lazily initialize and return the Google GenAI client."""
        if not self.api_key:
            raise EmbeddingConfigError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in your environment or .env file."
            )
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_embedding(self, text: str) -> List[float]:
        """Generate a 1536-dimensional embedding vector for input text using Gemini.

        Args:
            text: Input text string to embed.

        Returns:
            List[float]: 1536-element float embedding vector.

        Raises:
            EmbeddingConfigError: If Gemini API key is missing.
            EmbeddingError: If input text is empty or invalid.
            EmbeddingAPIError: If the Gemini API request fails or returns invalid dimensions.
        """
        if not text or not text.strip():
            raise EmbeddingError("Input text cannot be empty or whitespace only.")

        clean_text = text.strip()
        client = self._get_client()

        try:
            response = client.models.embed_content(
                model=self.model,
                contents=clean_text,
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                ),
            )

            if not response.embeddings or not response.embeddings[0].values:
                raise EmbeddingAPIError("Empty embedding vector received from Gemini API.")

            embedding = response.embeddings[0].values

            if len(embedding) != EMBEDDING_DIMENSIONS:
                raise EmbeddingAPIError(
                    f"Unexpected embedding dimension: expected {EMBEDDING_DIMENSIONS}, received {len(embedding)}"
                )

            return list(embedding)

        except errors.ClientError as e:
            logger.error("Gemini client error (code %s): %s", getattr(e, "code", "unknown"), e)
            raise EmbeddingAPIError(f"Gemini API request failed: {e}") from e
        except errors.ServerError as e:
            logger.error("Gemini server error: %s", e)
            raise EmbeddingAPIError(f"Gemini server error: {e}") from e
        except errors.APIError as e:
            logger.error("Gemini API error: %s", e)
            raise EmbeddingAPIError(f"Gemini API error: {e}") from e
        except EmbeddingError:
            raise
        except Exception as e:
            logger.error("Unexpected error in Gemini embedding generation: %s", e)
            raise EmbeddingAPIError(f"Unexpected embedding error: {e}") from e

    def generate_agent_embedding(self, interest_manifesto: str) -> List[float]:
        """Generate vector embedding from an agent's interest manifesto."""
        return self.generate_embedding(interest_manifesto)

    def generate_post_embedding(self, title: str, content: str) -> List[float]:
        """Generate vector embedding from a post's title and content."""
        combined_text = f"{title.strip()}\n\n{content.strip()}".strip()
        return self.generate_embedding(combined_text)


# Singleton instance for general use across the application
embedding_service = EmbeddingService()
