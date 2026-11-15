"""
Notification Service

Handles asynchronous and synchronous webhook delivery to target agents
for intelligently routed posts. Includes timeout management, controlled retries,
duplicate delivery prevention, and delivery auditing in routing_logs.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.database.repository import RoutingRepository
from app.models.agent import Agent
from app.models.post import Post
from app.models.routing_log import RoutingLog

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 0.5


class NotificationService:
    """Manages secure, audited webhook notification delivery to partner agents."""

    def __init__(
        self,
        db: Session,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        http_client: Optional[httpx.Client] = None,
    ):
        self.db = db
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._http_client = http_client
        self.routing_repo = RoutingRepository(db)

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self.timeout)

    def is_already_delivered(self, post_id: str, target_agent_id: str) -> bool:
        """Check if this post was already successfully delivered to this target agent."""
        existing = (
            self.db.query(RoutingLog)
            .filter(
                RoutingLog.post_id == post_id,
                RoutingLog.target_agent_id == target_agent_id,
                RoutingLog.status == "DELIVERED",
            )
            .first()
        )
        return existing is not None

    def send_webhook(
        self,
        target_agent: Agent,
        post: Post,
        vector_score: float,
        rerank_score: float,
        routing_log_id: Optional[str] = None,
    ) -> Dict:
        """Send a post notification webhook to an agent with retries and audit logging.

        Args:
            target_agent: Target Agent ORM model instance.
            post: Post ORM model instance being notified.
            vector_score: Baseline semantic cosine similarity score.
            rerank_score: Multi-factor reranked score.
            routing_log_id: Optional existing RoutingLog ID to update.

        Returns:
            Dict containing delivery outcome (status, attempts, status_code, error).
        """
        # 1. Prevent duplicate delivery
        if self.is_already_delivered(post.id, target_agent.id):
            logger.info("Notification for post %s to agent %s already DELIVERED. Skipping.", post.id, target_agent.id)
            return {
                "status": "SKIPPED",
                "message": "Notification already delivered previously",
                "attempts": 0,
                "agent_id": target_agent.id,
                "webhook_url": target_agent.webhook_url,
            }

        # 2. Validate webhook URL
        webhook_url = (target_agent.webhook_url or "").strip()
        if not webhook_url or not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
            error_msg = f"Invalid or missing webhook URL: '{webhook_url}'"
            self._update_log_status(
                routing_log_id=routing_log_id,
                post_id=post.id,
                target_agent_id=target_agent.id,
                vector_score=vector_score,
                rerank_score=rerank_score,
                status="FAILED",
                attempts=0,
                error_message=error_msg,
            )
            return {
                "status": "FAILED",
                "message": error_msg,
                "attempts": 0,
                "agent_id": target_agent.id,
                "webhook_url": webhook_url,
            }

        # 3. Construct standard webhook payload
        payload = {
            "event": "agent.post.routed",
            "post_id": post.id,
            "author_agent_id": post.author_agent_id,
            "title": post.title,
            "content": post.content,
            "similarity_score": vector_score,
            "rerank_score": rerank_score,
            "target_agent_id": target_agent.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 4. Attempt delivery with controlled retries
        last_error = None
        status_code = None
        attempts = 0

        client = self._get_client()
        try:
            for attempt in range(1, self.max_retries + 1):
                attempts = attempt
                try:
                    logger.debug("Dispatching webhook attempt %d/%d to %s", attempt, self.max_retries, webhook_url)
                    response = client.post(
                        webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json", "User-Agent": "AIAgentPlatform-Notifier/1.0"},
                    )
                    status_code = response.status_code

                    # STRICT SUCCESS CHECK: Only HTTP 2xx is considered delivered
                    if 200 <= status_code < 300:
                        logger.info("Webhook delivered successfully to %s (HTTP %d)", target_agent.company_name, status_code)
                        self._update_log_status(
                            routing_log_id=routing_log_id,
                            post_id=post.id,
                            target_agent_id=target_agent.id,
                            vector_score=vector_score,
                            rerank_score=rerank_score,
                            status="DELIVERED",
                            attempts=attempts,
                            error_message=None,
                        )
                        return {
                            "status": "DELIVERED",
                            "status_code": status_code,
                            "attempts": attempts,
                            "agent_id": target_agent.id,
                            "webhook_url": webhook_url,
                        }
                    else:
                        last_error = f"HTTP {status_code}: {response.text[:150]}"
                        logger.warning("Webhook to %s failed with status %d (attempt %d/%d)", target_agent.company_name, status_code, attempt, self.max_retries)

                except httpx.TimeoutException as e:
                    last_error = f"Timeout ({self.timeout}s): {e}"
                    logger.warning("Webhook to %s timed out (attempt %d/%d)", target_agent.company_name, attempt, self.max_retries)
                except httpx.RequestError as e:
                    last_error = f"Connection error: {e}"
                    logger.warning("Webhook to %s connection error (attempt %d/%d): %s", target_agent.company_name, attempt, self.max_retries, e)

                if attempt < self.max_retries and self.retry_delay > 0:
                    time.sleep(self.retry_delay * attempt)
        finally:
            if self._http_client is None:
                client.close()

        # All retries exhausted without a 2xx response -> FAILED
        self._update_log_status(
            routing_log_id=routing_log_id,
            post_id=post.id,
            target_agent_id=target_agent.id,
            vector_score=vector_score,
            rerank_score=rerank_score,
            status="FAILED",
            attempts=attempts,
            error_message=last_error,
        )

        return {
            "status": "FAILED",
            "status_code": status_code,
            "attempts": attempts,
            "error": last_error,
            "agent_id": target_agent.id,
            "webhook_url": webhook_url,
        }

    def _update_log_status(
        self,
        routing_log_id: Optional[str],
        post_id: str,
        target_agent_id: str,
        vector_score: float,
        rerank_score: float,
        status: str,
        attempts: int,
        error_message: Optional[str],
    ) -> RoutingLog:
        """Helper to create or update delivery status in routing_logs."""
        log = None
        if routing_log_id:
            log = self.db.query(RoutingLog).filter(RoutingLog.id == routing_log_id).first()

        if log is None:
            # Check existing for this post + agent pair
            log = (
                self.db.query(RoutingLog)
                .filter(RoutingLog.post_id == post_id, RoutingLog.target_agent_id == target_agent_id)
                .first()
            )

        if log is None:
            # Create fresh record
            log = RoutingLog(
                post_id=post_id,
                target_agent_id=target_agent_id,
                vector_score=vector_score,
                rerank_score=rerank_score,
                status=status,
                delivery_attempts=attempts,
                error_message=error_message,
            )
            self.db.add(log)
        else:
            log.status = status
            log.delivery_attempts = attempts
            log.error_message = error_message

        self.db.commit()
        self.db.refresh(log)
        return log


def get_notification_service(db: Session) -> NotificationService:
    """Dependency helper for NotificationService."""
    return NotificationService(db=db)
