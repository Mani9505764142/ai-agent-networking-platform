"""
Automated Test Suite for Phase 4:
Intelligent Reranking, Relevance Filtering, Webhook Delivery & Agent Response Handling.

Covers:
1. Reranking score calculation (distinct from vector_score).
2. Relevant vs. irrelevant agent filtering (e.g. Bajaj Auto excluded from Food Flash).
3. Webhook successful delivery (HTTP 200).
4. Webhook timeout handling.
5. Webhook HTTP failure handling (HTTP 500/404).
6. Controlled retry behavior.
7. Duplicate delivery prevention.
8. Agent response validation (400 for bad UUID, 404 for missing post/agent).
9. Agent response persistence in database.
"""

import math
import uuid
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.api.routing import get_responses_for_post, submit_agent_response
from app.database.connection import SessionLocal
from app.database.repository import AgentRepository, AgentResponseRepository, PostRepository, RoutingRepository
from app.models.agent import Agent
from app.models.agent_response import AgentResponseRecord
from app.models.post import Post
from app.models.routing_log import RoutingLog
from app.schemas.response import AgentResponseCreate
from app.services.notification_service import NotificationService
from app.services.reranking_service import RerankingService, reranking_service
from app.services.routing_service import RoutingService


# ── 1. Reranking & Relevance Filtering Tests ───────────────────────────────

class TestRerankingService:
    """Test Suite for multi-factor contextual reranking and relevance filtering."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self):
        self.reranker = RerankingService()
        self.swiggy_post = Post(
            id=str(uuid.uuid4()),
            author_agent_id=str(uuid.uuid4()),
            title="Special Weekend 50% Off Restaurant Flash",
            content="Exclusive food delivery offers on top restaurants across Bangalore. Pay with UPI for extra cashback!",
        )

    def test_rerank_score_differs_from_vector_score(self):
        """Rerank score must represent actual reranking and not simply duplicate vector_score."""
        agent = Agent(
            id=str(uuid.uuid4()),
            company_name="PhonePe",
            industry_category="FinTech",
            interest_manifesto="UPI payments, merchant partnerships, cashback offers.",
            trust_score=1.0,
        )
        vec_score = 0.8100
        result = self.reranker.rerank_candidate(self.swiggy_post, agent, vec_score)

        assert result["rerank_score"] != vec_score
        assert "breakdown" in result
        assert result["breakdown"]["lexical_score"] > 0.0
        assert result["breakdown"]["industry_score"] > 0.0

    def test_irrelevant_agent_bajaj_auto_filtered_out(self):
        """Bajaj Auto (Automobile) has low lexical/industry affinity and is filtered by threshold."""
        bajaj_agent = Agent(
            id=str(uuid.uuid4()),
            company_name="Bajaj Auto",
            industry_category="Automobile",
            interest_manifesto="Motorcycles, vehicle launches, automobile promotions, automotive finance.",
            trust_score=1.0,
        )
        # Even with an embedding similarity of ~0.4592
        vec_score = 0.4592
        result = self.reranker.rerank_candidate(self.swiggy_post, bajaj_agent, vec_score)

        # Rerank score drops significantly due to industry mismatch and low lexical overlap
        assert result["rerank_score"] < 0.40
        assert result["breakdown"]["industry_score"] <= 0.20

        # When evaluated against threshold 0.40, Bajaj Auto is filtered out
        candidates = [(bajaj_agent, vec_score)]
        filtered = self.reranker.rerank_candidates(self.swiggy_post, candidates, min_threshold=0.40)
        assert len(filtered) == 0

    def test_relevant_fintech_agents_pass_threshold(self):
        """PhonePe and Google Pay with payment synergy pass the threshold."""
        phonepe_agent = Agent(
            id=str(uuid.uuid4()),
            company_name="PhonePe",
            industry_category="FinTech",
            interest_manifesto="UPI payments, merchant partnerships, cashback offers.",
            trust_score=1.0,
        )
        candidates = [(phonepe_agent, 0.81)]
        filtered = self.reranker.rerank_candidates(self.swiggy_post, candidates, min_threshold=0.40)

        assert len(filtered) == 1
        assert filtered[0]["company_name"] == "PhonePe"
        assert filtered[0]["rerank_score"] >= 0.65

    def test_explainable_breakdown_contains_all_components(self):
        """Breakdown provides transparent explainability for auditing."""
        agent = Agent(
            id=str(uuid.uuid4()),
            company_name="HDFC Bank",
            industry_category="Banking",
            interest_manifesto="Credit cards, banking offers, payment partnerships.",
            trust_score=0.9,
        )
        result = self.reranker.rerank_candidate(self.swiggy_post, agent, 0.65)
        breakdown = result["breakdown"]

        assert "vector_component" in breakdown
        assert "lexical_score" in breakdown
        assert "industry_score" in breakdown
        assert "trust_score" in breakdown
        assert "explanation" in breakdown
        assert "Banking" in breakdown["explanation"]


# ── 2. Webhook Notification Delivery Tests ─────────────────────────────────

class TestWebhookNotificationService:
    """Test Suite for webhook delivery, timeouts, retries, and duplicate prevention."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = SessionLocal()
        self.created_agent_ids = []
        self.created_post_ids = []
        self.created_log_ids = []
        yield
        try:
            for log_id in self.created_log_ids:
                self.db.query(RoutingLog).filter(RoutingLog.id == log_id).delete()
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

    def _create_agent_and_post(self, webhook_url: str = "https://mock.agent.example.com/webhook"):
        agent_id = str(uuid.uuid4())
        agent = Agent(
            id=agent_id,
            company_name=f"MockAgent-{agent_id[:6]}",
            industry_category="FinTech",
            webhook_url=webhook_url,
            interest_manifesto="UPI payment processing.",
            trust_score=1.0,
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)

        post_id = str(uuid.uuid4())
        post = Post(
            id=post_id,
            author_agent_id=agent.id,
            title="Food Festival Announcement",
            content="Restaurant festival offers.",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        self.created_agent_ids.append(agent_id)
        self.created_post_ids.append(post_id)
        return agent, post

    def test_webhook_successful_delivery_200(self):
        """Mock HTTP 200 response -> marks routing_log status DELIVERED."""
        agent, post = self._create_agent_and_post()

        # Mock httpx client returning 200 OK
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True

        mock_http_client = MagicMock(spec=httpx.Client)
        mock_http_client.post.return_value = mock_response

        notifier = NotificationService(db=self.db, http_client=mock_http_client, max_retries=2)
        result = notifier.send_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.85,
            rerank_score=0.80,
        )

        assert result["status"] == "DELIVERED"
        assert result["status_code"] == 200
        assert result["attempts"] == 1

        # Verify database record updated
        log = self.db.query(RoutingLog).filter(RoutingLog.post_id == post.id).first()
        assert log is not None
        assert log.status == "DELIVERED"
        assert log.delivery_attempts == 1
        assert log.error_message is None

    def test_webhook_timeout_marks_failed(self):
        """Mock timeout across retries -> marks routing_log status FAILED."""
        agent, post = self._create_agent_and_post()

        mock_http_client = MagicMock(spec=httpx.Client)
        mock_http_client.post.side_effect = httpx.TimeoutException("Connection timed out")

        notifier = NotificationService(
            db=self.db,
            http_client=mock_http_client,
            max_retries=2,
            retry_delay=0.01,
        )
        result = notifier.send_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.85,
            rerank_score=0.80,
        )

        assert result["status"] == "FAILED"
        assert result["attempts"] == 2
        assert "Timeout" in result["error"]

        log = self.db.query(RoutingLog).filter(RoutingLog.post_id == post.id).first()
        assert log is not None
        assert log.status == "FAILED"
        assert log.delivery_attempts == 2
        assert "Timeout" in log.error_message

    def test_webhook_http_failure_500(self):
        """Mock HTTP 500 response -> marks status FAILED after exhausting retries."""
        agent, post = self._create_agent_and_post()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.is_success = False

        mock_http_client = MagicMock(spec=httpx.Client)
        mock_http_client.post.return_value = mock_response

        notifier = NotificationService(
            db=self.db,
            http_client=mock_http_client,
            max_retries=2,
            retry_delay=0.01,
        )
        result = notifier.send_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.85,
            rerank_score=0.80,
        )

        assert result["status"] == "FAILED"
        assert result["status_code"] == 500
        assert result["attempts"] == 2
        assert "HTTP 500" in result["error"]

    def test_controlled_retry_behavior_succeeds_on_second_attempt(self):
        """Fails on 1st attempt, succeeds on 2nd attempt -> DELIVERED with attempts=2."""
        agent, post = self._create_agent_and_post()

        fail_response = MagicMock(spec=httpx.Response)
        fail_response.status_code = 503
        fail_response.text = "Temporary Gateway Outage"
        fail_response.is_success = False

        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.is_success = True

        mock_http_client = MagicMock(spec=httpx.Client)
        mock_http_client.post.side_effect = [fail_response, success_response]

        notifier = NotificationService(
            db=self.db,
            http_client=mock_http_client,
            max_retries=3,
            retry_delay=0.01,
        )
        result = notifier.send_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.85,
            rerank_score=0.80,
        )

        assert result["status"] == "DELIVERED"
        assert result["status_code"] == 200
        assert result["attempts"] == 2

    def test_duplicate_delivery_prevention(self):
        """When notification is already DELIVERED, subsequent attempts are skipped."""
        agent, post = self._create_agent_and_post()

        # Pre-seed a DELIVERED routing log in the database
        routing_repo = RoutingRepository(self.db)
        log = routing_repo.create_log(
            post_id=post.id,
            target_agent_id=agent.id,
            vector_score=0.9,
            rerank_score=0.88,
            status="DELIVERED",
            delivery_attempts=1,
        )
        self.created_log_ids.append(log.id)

        mock_http_client = MagicMock(spec=httpx.Client)
        notifier = NotificationService(db=self.db, http_client=mock_http_client)

        result = notifier.send_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.9,
            rerank_score=0.88,
        )

        assert result["status"] == "SKIPPED"
        assert result["attempts"] == 0
        # HTTP client was NEVER invoked
        mock_http_client.post.assert_not_called()

    def test_invalid_webhook_url_rejected_without_sending(self):
        """Invalid webhook URL fails immediately without network calls."""
        agent, post = self._create_agent_and_post(webhook_url="invalid-not-a-url")

        mock_http_client = MagicMock(spec=httpx.Client)
        notifier = NotificationService(db=self.db, http_client=mock_http_client)

        result = notifier.send_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.8,
            rerank_score=0.75,
        )

        assert result["status"] == "FAILED"
        assert "Invalid or missing webhook URL" in result["message"]
        mock_http_client.post.assert_not_called()


# ── 3. Agent Response Handling Tests ────────────────────────────────────────

class TestAgentResponseHandling:
    """Test Suite for receiving, validating, and persisting agent responses."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = SessionLocal()
        self.created_agent_ids = []
        self.created_post_ids = []
        self.created_response_ids = []
        yield
        try:
            for resp_id in self.created_response_ids:
                self.db.query(AgentResponseRecord).filter(AgentResponseRecord.id == resp_id).delete()
            for post_id in self.created_post_ids:
                self.db.query(AgentResponseRecord).filter(AgentResponseRecord.post_id == post_id).delete()
                self.db.query(RoutingLog).filter(RoutingLog.post_id == post_id).delete()
                self.db.query(Post).filter(Post.id == post_id).delete()
            for agent_id in self.created_agent_ids:
                self.db.query(Agent).filter(Agent.id == agent_id).delete()
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def _create_sample_agent_and_post(self):
        agent_id = str(uuid.uuid4())
        agent = Agent(
            id=agent_id,
            company_name=f"RespondingAgent-{agent_id[:6]}",
            industry_category="FinTech",
            webhook_url="https://mock.example.com",
            interest_manifesto="Cashback & payments.",
            trust_score=1.0,
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)

        post_id = str(uuid.uuid4())
        post = Post(
            id=post_id,
            author_agent_id=agent.id,
            title="Partnership Request",
            content="Co-branded discount campaign.",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        self.created_agent_ids.append(agent_id)
        self.created_post_ids.append(post_id)
        return agent, post

    def test_submit_agent_response_success(self):
        """Valid agent response is recorded in agent_responses table."""
        agent, post = self._create_sample_agent_and_post()

        payload = AgentResponseCreate(
            post_id=post.id,
            responding_agent_id=agent.id,
            response_type="PROPOSAL",
            content="We can offer 10% instant cashback on all UPI orders.",
            metadata={"discount_code": "UPI10", "max_cap": 100},
        )

        response = submit_agent_response(payload=payload, db=self.db)

        assert response.id is not None
        assert response.post_id == post.id
        assert response.responding_agent_id == agent.id
        assert response.response_type == "PROPOSAL"
        assert response.content == "We can offer 10% instant cashback on all UPI orders."
        assert response.metadata_json == {"discount_code": "UPI10", "max_cap": 100}
        self.created_response_ids.append(response.id)

        # Verify database persistence
        repo = AgentResponseRepository(self.db)
        fetched = repo.get_by_id(response.id)
        assert fetched is not None
        assert fetched.content == payload.content

    def test_submit_response_invalid_post_returns_404(self):
        """Submitting response for non-existent post returns HTTP 404."""
        agent, _ = self._create_sample_agent_and_post()
        payload = AgentResponseCreate(
            post_id=str(uuid.uuid4()),  # Random non-existent post
            responding_agent_id=agent.id,
            content="Valid response content.",
        )

        with pytest.raises(Exception) as exc_info:
            submit_agent_response(payload=payload, db=self.db)
        assert exc_info.value.status_code == 404
        assert "does not exist" in exc_info.value.detail

    def test_submit_response_invalid_agent_returns_404(self):
        """Submitting response from non-existent agent returns HTTP 404."""
        _, post = self._create_sample_agent_and_post()
        payload = AgentResponseCreate(
            post_id=post.id,
            responding_agent_id=str(uuid.uuid4()),  # Random non-existent agent
            content="Valid response content.",
        )

        with pytest.raises(Exception) as exc_info:
            submit_agent_response(payload=payload, db=self.db)
        assert exc_info.value.status_code == 404
        assert "does not exist" in exc_info.value.detail

    def test_submit_response_invalid_uuid_returns_400(self):
        """Malformed UUID in post_id or responding_agent_id returns HTTP 400."""
        payload = AgentResponseCreate(
            post_id="not-a-uuid",
            responding_agent_id=str(uuid.uuid4()),
            content="Some response content.",
        )

        with pytest.raises(Exception) as exc_info:
            submit_agent_response(payload=payload, db=self.db)
        assert exc_info.value.status_code == 400
        assert "not a valid uuid" in exc_info.value.detail.lower()

    def test_get_responses_for_post_endpoint(self):
        """GET /api/v1/routing/responses/{post_id} lists all responses for a post."""
        agent, post = self._create_sample_agent_and_post()

        # Submit two responses
        for i in range(2):
            payload = AgentResponseCreate(
                post_id=post.id,
                responding_agent_id=agent.id,
                response_type=f"REPLY_{i}",
                content=f"Proposal version {i}",
            )
            resp = submit_agent_response(payload=payload, db=self.db)
            self.created_response_ids.append(resp.id)

        responses = get_responses_for_post(post_id=post.id, db=self.db)
        assert len(responses) == 2
        types = [r.response_type for r in responses]
        assert "REPLY_0" in types
        assert "REPLY_1" in types
