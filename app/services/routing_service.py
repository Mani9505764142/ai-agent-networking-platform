"""
Routing Service

Intelligent relevance routing engine for agent posts.
Orchestrates:
1. Post embedding verification & generation
2. Dense semantic pgvector cosine candidate retrieval
3. Multi-factor reranking (lexical overlap, industry alignment, trust weighting)
4. Configurable relevance threshold filtering
5. Webhook notification dispatch with retries & duplicate prevention
6. Delivery status tracking in routing_logs
"""

from typing import Dict, List, Optional
import logging
from sqlalchemy.orm import Session

from app.database.repository import AgentRepository, PostRepository, RoutingRepository
from app.models.post import Post
from app.services.embedding_service import EmbeddingService, embedding_service
from app.services.notification_service import NotificationService
from app.services.reranking_service import RerankingService, reranking_service

logger = logging.getLogger(__name__)

DEFAULT_MIN_RERANK_THRESHOLD = 0.40


class RoutingServiceError(Exception):
    """Base exception for routing service errors."""
    pass


class PostNotFoundError(RoutingServiceError):
    """Raised when the specified post cannot be found."""
    pass


class RoutingService:
    """Orchestrates intelligent relevance routing and audited notification delivery."""

    def __init__(
        self,
        db: Session,
        embed_service: Optional[EmbeddingService] = None,
        rerank_svc: Optional[RerankingService] = None,
        notify_svc: Optional[NotificationService] = None,
    ):
        self.db = db
        self.embedding_service = embed_service or embedding_service
        self.reranking_service = rerank_svc or reranking_service
        self.notification_service = notify_svc or NotificationService(db=db)
        self.agent_repo = AgentRepository(db)
        self.post_repo = PostRepository(db)
        self.routing_repo = RoutingRepository(db)

    def route_post(
        self,
        post_id: str,
        limit: int = 10,
        min_similarity: Optional[float] = None,
        min_rerank_threshold: Optional[float] = None,
        dispatch_webhooks: bool = False,
    ) -> Dict:
        """Route a post to semantically and contextually relevant agents.

        Workflow:
        1. Fetch post by ID.
        2. Ensure post has an embedding (generate and persist if missing).
        3. Query candidate agents using pgvector cosine similarity.
        4. Apply multi-factor reranking (lexical + industry alignment + trust).
        5. Filter candidates below min_rerank_threshold.
        6. Persist routing decisions in routing_logs.
        7. Optionally dispatch webhooks to qualified target agents.
        8. Return ranked results with separate vector & rerank scores.

        Args:
            post_id: UUID string of the post to route.
            limit: Maximum number of target agents to return.
            min_similarity: Optional raw vector similarity cutoff.
            min_rerank_threshold: Optional reranking score cutoff (defaults to 0.40 if None).
            dispatch_webhooks: Whether to immediately attempt HTTP webhook notifications.

        Returns:
            Dict containing post metadata, routed agent details, scores, and delivery outcomes.
        """
        post = self.post_repo.get_by_id(post_id)
        if not post:
            raise PostNotFoundError(f"Post with id '{post_id}' does not exist.")

        # Step 2: Ensure post has an embedding
        post_embedding = post.post_embedding
        if post_embedding is None:
            logger.info("Post %s has no embedding; generating now.", post_id)
            post_embedding = self.embedding_service.generate_post_embedding(
                title=post.title,
                content=post.content,
            )
            self.post_repo.update_embedding(post_id, post_embedding)

        # Step 3: Candidate retrieval using pgvector cosine similarity
        raw_candidates = self.agent_repo.find_similar_agents(
            query_embedding=post_embedding,
            exclude_agent_id=post.author_agent_id,
            limit=limit * 2,  # Fetch wider candidate pool before reranking
            min_similarity=min_similarity,
        )

        # Step 4 & 5: Multi-factor reranking & threshold filtering
        threshold = min_rerank_threshold if min_rerank_threshold is not None else DEFAULT_MIN_RERANK_THRESHOLD
        reranked_candidates = self.reranking_service.rerank_candidates(
            post=post,
            candidates=raw_candidates,
            min_threshold=threshold,
        )

        # Truncate to desired limit
        top_candidates = reranked_candidates[:limit]

        # Step 6: Persist routing decisions in routing_logs
        routed_results = []
        for cand in top_candidates:
            agent = cand["agent"]
            vector_score = cand["vector_score"]
            rerank_score = cand["rerank_score"]

            # Save initial routing log
            routing_log = self.routing_repo.create_log(
                post_id=post_id,
                target_agent_id=agent.id,
                vector_score=vector_score,
                rerank_score=rerank_score,
                status="NOTIFIED" if not dispatch_webhooks else "PENDING",
            )

            delivery_status = "NOTIFIED"
            delivery_attempts = 0
            delivery_error = None

            # Step 7: Webhook notification dispatch
            if dispatch_webhooks:
                delivery_result = self.notification_service.send_webhook(
                    target_agent=agent,
                    post=post,
                    vector_score=vector_score,
                    rerank_score=rerank_score,
                    routing_log_id=routing_log.id,
                )
                delivery_status = delivery_result.get("status", "FAILED")
                delivery_attempts = delivery_result.get("attempts", 0)
                delivery_error = delivery_result.get("error")

            routed_results.append({
                "agent_id": agent.id,
                "company_name": agent.company_name,
                "industry_category": agent.industry_category,
                "webhook_url": agent.webhook_url,
                "similarity_score": vector_score,
                "vector_score": vector_score,
                "rerank_score": rerank_score,
                "trust_score": agent.trust_score,
                "delivery_status": delivery_status,
                "delivery_attempts": delivery_attempts,
                "delivery_error": delivery_error,
                "breakdown": cand["breakdown"],
            })

        logger.info(
            "Routing completed for post %s: %d candidates evaluated, %d passed threshold (>=%.2f)",
            post_id, len(raw_candidates), len(routed_results), threshold,
        )

        return {
            "post_id": post_id,
            "post_title": post.title,
            "author_agent_id": post.author_agent_id,
            "candidate_count": len(raw_candidates),
            "routed_count": len(routed_results),
            "relevance_threshold": threshold,
            "results": routed_results,
            "status": "success",
        }
