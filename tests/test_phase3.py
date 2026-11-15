"""
Automated Test Suite for Phase 3:
Embeddings, Vector Search & Intelligent Relevance Routing.

Covers:
1. Agent embedding generation (mocked Google Gemini).
2. Post embedding generation (mocked Google Gemini).
3. Exact 1536-dimension vector verification.
4. Vector storage (1536-dimensional vectors in PostgreSQL).
5. pgvector cosine similarity search.
6. Author exclusion from routing results.
7. Inactive agent exclusion from routing results.
8. Relevance ranking (similarity order verification).
9. Routing log creation and persistence.
10. API error handling (404 for missing post, 400 for invalid UUID, service failures).
"""

import math
import uuid
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors

from app.api.routing import get_routing_logs_for_post, list_routing_logs, route_post
from app.database.connection import SessionLocal
from app.database.repository import AgentRepository, PostRepository, RoutingRepository
from app.models.agent import Agent
from app.models.post import Post
from app.models.routing_log import RoutingLog
from app.services.embedding_service import (
    EmbeddingAPIError,
    EmbeddingConfigError,
    EmbeddingError,
    EmbeddingService,
)
from app.services.routing_service import PostNotFoundError, RoutingService


# ── Helper: Normalized 1536-dim vector generator ───────────────────────────

def make_unit_vector(angle: float) -> list[float]:
    """Generate a 1536-dim normalized vector with energy in first two dimensions."""
    vec = [0.0] * 1536
    vec[0] = math.cos(angle)
    vec[1] = math.sin(angle)
    return vec


# ── 1. Embedding Service Tests (Google Gemini) ──────────────────────────────

class TestEmbeddingService:
    """Test Step 1: Embedding generation using mocked Google Gemini API."""

    def test_missing_api_key_raises_config_error(self):
        """Service without API key raises EmbeddingConfigError."""
        service = EmbeddingService(api_key="")
        with pytest.raises(EmbeddingConfigError) as exc_info:
            service.generate_embedding("Test manifesto")
        assert "Gemini API key is not configured" in str(exc_info.value)

    def test_empty_text_raises_error(self):
        """Empty or whitespace-only input raises EmbeddingError."""
        service = EmbeddingService(api_key="mock-gemini-key")
        with pytest.raises(EmbeddingError) as exc_info:
            service.generate_embedding("   ")
        assert "cannot be empty" in str(exc_info.value)

    @patch("app.services.embedding_service.genai.Client")
    def test_agent_embedding_generation_success(self, mock_client_cls):
        """Successful generation of 1536-dim agent embedding using gemini-embedding-001."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_emb = MagicMock()
        mock_emb.values = [0.05] * 1536
        mock_response.embeddings = [mock_emb]
        mock_client.models.embed_content.return_value = mock_response

        service = EmbeddingService(api_key="mock-gemini-key")
        result = service.generate_agent_embedding("FinTech UPI payments and merchant banking.")

        assert len(result) == 1536
        assert result[0] == 0.05
        mock_client.models.embed_content.assert_called_once()
        call_kwargs = mock_client.models.embed_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-embedding-001"
        assert call_kwargs["contents"] == "FinTech UPI payments and merchant banking."
        assert call_kwargs["config"].output_dimensionality == 1536

    @patch("app.services.embedding_service.genai.Client")
    def test_post_embedding_generation_success(self, mock_client_cls):
        """Successful generation of 1536-dim post embedding from title + content."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_emb = MagicMock()
        mock_emb.values = [0.08] * 1536
        mock_response.embeddings = [mock_emb]
        mock_client.models.embed_content.return_value = mock_response

        service = EmbeddingService(api_key="mock-gemini-key")
        result = service.generate_post_embedding(
            title="Special 50% Cashback",
            content="Use UPI for payments across partner restaurants.",
        )

        assert len(result) == 1536
        assert result[0] == 0.08
        call_kwargs = mock_client.models.embed_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-embedding-001"
        assert "Special 50% Cashback\n\nUse UPI for payments across partner restaurants." in call_kwargs["contents"]
        assert call_kwargs["config"].output_dimensionality == 1536

    @patch("app.services.embedding_service.genai.Client")
    def test_embedding_exactly_1536_dimensions(self, mock_client_cls):
        """Explicitly verify that generated embedding has exactly 1536 dimensions."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_emb = MagicMock()
        exact_1536_vector = [float(i) / 1536.0 for i in range(1536)]
        mock_emb.values = exact_1536_vector
        mock_response.embeddings = [mock_emb]
        mock_client.models.embed_content.return_value = mock_response

        service = EmbeddingService(api_key="mock-gemini-key")
        embedding = service.generate_embedding("Test strict dimensionality")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    @patch("app.services.embedding_service.genai.Client")
    def test_dimension_mismatch_raises_error(self, mock_client_cls):
        """If API returns wrong dimensionality, raise EmbeddingAPIError."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_emb = MagicMock()
        mock_emb.values = [0.1] * 768  # Wrong dimensionality (768 instead of 1536)
        mock_response.embeddings = [mock_emb]
        mock_client.models.embed_content.return_value = mock_response

        service = EmbeddingService(api_key="mock-gemini-key")
        with pytest.raises(EmbeddingAPIError) as exc_info:
            service.generate_embedding("Valid text")
        assert "expected 1536" in str(exc_info.value)
        assert "768" in str(exc_info.value)

    @patch("app.services.embedding_service.genai.Client")
    def test_client_error_mapping(self, mock_client_cls):
        """Gemini ClientError maps to EmbeddingAPIError."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.embed_content.side_effect = errors.ClientError(
            code=400,
            response_json={"error": {"message": "Invalid argument"}},
        )

        service = EmbeddingService(api_key="mock-gemini-key")
        with pytest.raises(EmbeddingAPIError) as exc_info:
            service.generate_embedding("Valid text")
        assert "Gemini API request failed" in str(exc_info.value)

    @patch("app.services.embedding_service.genai.Client")
    def test_server_error_mapping(self, mock_client_cls):
        """Gemini ServerError maps to EmbeddingAPIError."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.embed_content.side_effect = errors.ServerError(
            code=503,
            response_json={"error": {"message": "Service unavailable"}},
        )

        service = EmbeddingService(api_key="mock-gemini-key")
        with pytest.raises(EmbeddingAPIError) as exc_info:
            service.generate_embedding("Valid text")
        assert "Gemini server error" in str(exc_info.value)


# ── 2. Vector Storage, Search, Ranking & Exclusion Tests ───────────────────

class TestVectorSearchAndRouting:
    """Test Steps 2, 3, 4: Vector storage, similarity search, author exclusion, ranking."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Yield a database session and clean up created test records."""
        self.db = SessionLocal()
        self.created_agent_ids = []
        self.created_post_ids = []
        self.created_log_ids = []
        yield
        try:
            # Cleanup in reverse foreign key order
            for log_id in self.created_log_ids:
                self.db.query(RoutingLog).filter(RoutingLog.id == log_id).delete()
            for post_id in self.created_post_ids:
                self.db.query(RoutingLog).filter(RoutingLog.post_id == post_id).delete()
                self.db.query(Post).filter(Post.id == post_id).delete()
            for agent_id in self.created_agent_ids:
                self.db.query(RoutingLog).filter(RoutingLog.target_agent_id == agent_id).delete()
                self.db.query(Post).filter(Post.author_agent_id == agent_id).delete()
                self.db.query(Agent).filter(Agent.id == agent_id).delete()
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def _create_test_agent(
        self,
        company_name: str,
        embedding: list[float] = None,
        is_active: bool = True,
    ) -> Agent:
        agent_id = str(uuid.uuid4())
        agent = Agent(
            id=agent_id,
            company_name=company_name,
            industry_category="Testing",
            webhook_url=f"https://{company_name.lower().replace(' ', '')}.example.com/webhook",
            interest_manifesto=f"Manifesto for {company_name}",
            trust_score=0.95,
            is_active=is_active,
            interest_embedding=embedding,
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        self.created_agent_ids.append(agent_id)
        return agent

    def _create_test_post(
        self,
        author_id: str,
        title: str = "Test Post",
        embedding: list[float] = None,
    ) -> Post:
        post_id = str(uuid.uuid4())
        post = Post(
            id=post_id,
            author_agent_id=author_id,
            title=title,
            content=f"Content for {title}",
            post_embedding=embedding,
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        self.created_post_ids.append(post_id)
        return post

    def test_vector_storage_and_retrieval(self):
        """Vector embeddings are accurately stored and retrieved via pgvector."""
        test_vec = make_unit_vector(0.0)
        agent = self._create_test_agent("Vector Store Agent", embedding=test_vec)

        repo = AgentRepository(self.db)
        fetched = repo.get_by_id(agent.id)
        assert fetched is not None
        assert fetched.interest_embedding is not None
        assert math.isclose(fetched.interest_embedding[0], 1.0, abs_tol=1e-4)

    def test_similarity_search_and_relevance_ranking(self):
        """Cosine similarity search orders agents by decreasing relevance."""
        # Query vector: angle 0 -> (1.0, 0.0)
        query_vec = make_unit_vector(0.0)

        # Agent High: angle 0.1 -> cos(0.1) ~ 0.995 (Highest)
        agent_high = self._create_test_agent("High Match Agent", embedding=make_unit_vector(0.1))
        # Agent Mid: angle 0.8 -> cos(0.8) ~ 0.696 (Medium)
        agent_mid = self._create_test_agent("Mid Match Agent", embedding=make_unit_vector(0.8))
        # Agent Low: angle 1.4 -> cos(1.4) ~ 0.170 (Lowest)
        agent_low = self._create_test_agent("Low Match Agent", embedding=make_unit_vector(1.4))

        repo = AgentRepository(self.db)
        results = repo.find_similar_agents(query_embedding=query_vec, limit=10)

        # Filter only our test agents
        test_results = [r for r in results if r[0].id in (agent_high.id, agent_mid.id, agent_low.id)]

        assert len(test_results) == 3
        # Strict descending similarity ranking
        assert test_results[0][0].id == agent_high.id
        assert test_results[1][0].id == agent_mid.id
        assert test_results[2][0].id == agent_low.id

        score_high = test_results[0][1]
        score_mid = test_results[1][1]
        score_low = test_results[2][1]
        assert score_high > score_mid > score_low
        assert math.isclose(score_high, math.cos(0.1), abs_tol=0.01)

    def test_author_exclusion(self):
        """The authoring agent is strictly excluded from routing candidates."""
        vec = make_unit_vector(0.0)
        author = self._create_test_agent("Author Agent", embedding=vec)
        recipient = self._create_test_agent("Recipient Agent", embedding=vec)

        repo = AgentRepository(self.db)
        results = repo.find_similar_agents(
            query_embedding=vec,
            exclude_agent_id=author.id,
            limit=10,
        )

        returned_agent_ids = [r[0].id for r in results]
        assert author.id not in returned_agent_ids
        assert recipient.id in returned_agent_ids

    def test_inactive_agent_exclusion(self):
        """Inactive agents (is_active=False) are never returned in search."""
        vec = make_unit_vector(0.0)
        active_agent = self._create_test_agent("Active Agent", embedding=vec, is_active=True)
        inactive_agent = self._create_test_agent("Inactive Agent", embedding=vec, is_active=False)

        repo = AgentRepository(self.db)
        results = repo.find_similar_agents(query_embedding=vec, limit=10)

        returned_agent_ids = [r[0].id for r in results]
        assert active_agent.id in returned_agent_ids
        assert inactive_agent.id not in returned_agent_ids

    def test_routing_service_workflow_and_log_persistence(self):
        """End-to-end routing service generates embedding, matches agents, and logs decisions."""
        author = self._create_test_agent("Post Author Agent", embedding=make_unit_vector(1.5))
        target_agent = self._create_test_agent("Target Matched Agent", embedding=make_unit_vector(0.0))

        # Create post initially with NO embedding
        post = self._create_test_post(author_id=author.id, title="FinTech Deal", embedding=None)

        # Mock embedding service that produces unit vector at angle 0.0
        mock_embed_service = MagicMock(spec=EmbeddingService)
        mock_embed_service.generate_post_embedding.return_value = make_unit_vector(0.0)

        routing_service = RoutingService(db=self.db, embed_service=mock_embed_service)
        outcome = routing_service.route_post(post_id=post.id, limit=5)

        assert outcome["status"] == "success"
        assert outcome["post_id"] == post.id
        assert outcome["routed_count"] >= 1

        matched_agent_ids = [r["agent_id"] for r in outcome["results"]]
        assert target_agent.id in matched_agent_ids
        assert author.id not in matched_agent_ids

        # Verify post embedding was saved in the database
        refreshed_post = PostRepository(self.db).get_by_id(post.id)
        assert refreshed_post.post_embedding is not None

        # Verify routing logs were persisted
        routing_repo = RoutingRepository(self.db)
        logs = routing_repo.get_by_post_id(post.id)
        assert len(logs) >= 1
        log_target_ids = [l.target_agent_id for l in logs]
        assert target_agent.id in log_target_ids
        assert author.id not in log_target_ids
        assert logs[0].status == "NOTIFIED"
        assert 0.0 <= logs[0].vector_score <= 1.0


# ── 3. API Endpoints & Error Handling Tests ─────────────────────────────────

class TestRoutingAPI:
    """Test Step 5: Routing API endpoints and HTTP error conditions."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = SessionLocal()
        self.created_agent_ids = []
        self.created_post_ids = []
        yield
        try:
            for post_id in self.created_post_ids:
                self.db.query(RoutingLog).filter(RoutingLog.post_id == post_id).delete()
                self.db.query(Post).filter(Post.id == post_id).delete()
            for agent_id in self.created_agent_ids:
                self.db.query(Agent).filter(Agent.id == agent_id).delete()
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def test_route_nonexistent_post_returns_404(self):
        """Routing a non-existent post UUID returns HTTP 404."""
        nonexistent_id = str(uuid.uuid4())
        with pytest.raises(Exception) as exc_info:
            route_post(post_id=nonexistent_id, limit=10, min_similarity=None, db=self.db)
        assert exc_info.value.status_code == 404
        assert "does not exist" in exc_info.value.detail

    def test_route_invalid_uuid_returns_400(self):
        """Routing with an invalid UUID string returns HTTP 400."""
        with pytest.raises(Exception) as exc_info:
            route_post(post_id="not-a-valid-uuid", limit=10, min_similarity=None, db=self.db)
        assert exc_info.value.status_code == 400
        assert "not a valid uuid" in exc_info.value.detail.lower()

    def test_list_routing_logs_endpoint(self):
        """GET /api/v1/routing/logs returns logs."""
        logs = list_routing_logs(post_id=None, limit=10, skip=0, db=self.db)
        assert isinstance(logs, list)

    def test_get_routing_logs_for_post_endpoint(self):
        """GET /api/v1/routing/logs/{post_id} retrieves logs for specific post."""
        test_post_id = str(uuid.uuid4())
        logs = get_routing_logs_for_post(post_id=test_post_id, db=self.db)
        assert isinstance(logs, list)
