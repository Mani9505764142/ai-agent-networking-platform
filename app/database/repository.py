"""
Repository Layer

Clean data-access abstraction over SQLAlchemy.
Keeps all query logic separate from API routes and business services.
Supports CRUD operations, pgvector similarity search, routing logs, and agent responses.
"""

from typing import List, Optional, Tuple
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.post import Post
from app.models.routing_log import RoutingLog
from app.models.agent_response import AgentResponseRecord
from app.models.comment import Comment
from app.models.subscription import Subscription
from app.models.feedback import RoutingFeedback


# ── Agent Repository ────────────────────────────────────────────────────────

class AgentRepository:
    """CRUD and vector similarity search operations for AI agents."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, agent: Agent) -> Agent:
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_all(self) -> list[Agent]:
        return self.db.query(Agent).order_by(Agent.created_at.asc()).all()

    def get_by_id(self, agent_id: str) -> Optional[Agent]:
        return self.db.query(Agent).filter(Agent.id == agent_id).first()

    def get_by_company_name(self, company_name: str) -> Optional[Agent]:
        return self.db.query(Agent).filter(Agent.company_name == company_name).first()

    def update(self, agent_id: str, data: dict) -> Optional[Agent]:
        agent = self.get_by_id(agent_id)
        if agent is None:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(agent, key, value)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def update_embedding(self, agent_id: str, embedding: List[float]) -> Optional[Agent]:
        """Update an agent's interest embedding vector."""
        agent = self.get_by_id(agent_id)
        if agent is None:
            return None
        agent.interest_embedding = embedding
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_unembedded_agents(self) -> list[Agent]:
        """Retrieve all active agents whose interest_embedding is NULL."""
        return (
            self.db.query(Agent)
            .filter(Agent.interest_embedding.is_(None))
            .filter(Agent.is_active.is_(True))
            .order_by(Agent.created_at.asc())
            .all()
        )

    def find_similar_agents(
        self,
        query_embedding: List[float],
        exclude_agent_id: Optional[str] = None,
        limit: int = 10,
        min_similarity: Optional[float] = None,
    ) -> List[Tuple[Agent, float]]:
        """Search agents using pgvector cosine similarity.

        - Cosine distance: distance = Agent.interest_embedding <=> query_embedding.
        - Cosine similarity: score = 1.0 - distance.
        - Leverages the HNSW cosine index (vector_cosine_ops).
        - Excludes author if exclude_agent_id is provided.
        - Excludes inactive agents (is_active is True).
        - Excludes agents without embeddings.
        - Orders results by distance ascending (similarity descending).
        """
        distance = Agent.interest_embedding.cosine_distance(query_embedding)
        similarity = (1.0 - distance).label("similarity_score")

        query = (
            self.db.query(Agent, similarity)
            .filter(Agent.is_active.is_(True))
            .filter(Agent.interest_embedding.isnot(None))
        )

        if exclude_agent_id:
            query = query.filter(Agent.id != exclude_agent_id)

        if min_similarity is not None:
            query = query.filter((1.0 - distance) >= min_similarity)

        # Ordering by distance ASC leverages the HNSW vector_cosine_ops index
        query = query.order_by(distance.asc()).limit(limit)

        results = query.all()
        return [(agent, float(score)) for agent, score in results]

    def delete(self, agent_id: str) -> bool:
        agent = self.get_by_id(agent_id)
        if agent is None:
            return False
        # Remove any posts by this author first to maintain referential integrity
        self.db.query(Post).filter(Post.author_agent_id == agent_id).delete()
        self.db.delete(agent)
        self.db.commit()
        return True


# ── Post Repository ─────────────────────────────────────────────────────────

class PostRepository:
    """CRUD and embedding operations for agent posts."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, post: Post) -> Post:
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def get_all(self) -> list[Post]:
        return self.db.query(Post).order_by(Post.created_at.desc()).all()

    def get_by_id(self, post_id: str) -> Optional[Post]:
        return self.db.query(Post).filter(Post.id == post_id).first()

    def get_by_author(self, author_agent_id: str) -> list[Post]:
        return (
            self.db.query(Post)
            .filter(Post.author_agent_id == author_agent_id)
            .order_by(Post.created_at.desc())
            .all()
        )

    def update_embedding(self, post_id: str, embedding: List[float]) -> Optional[Post]:
        """Update a post's vector embedding."""
        post = self.get_by_id(post_id)
        if post is None:
            return None
        post.post_embedding = embedding
        self.db.commit()
        self.db.refresh(post)
        return post

    def delete(self, post_id: str) -> bool:
        post = self.get_by_id(post_id)
        if post is None:
            return False
        self.db.delete(post)
        self.db.commit()
        return True


# ── Routing Repository ──────────────────────────────────────────────────────

class RoutingRepository:
    """Operations for persisting and retrieving intelligent routing logs."""

    def __init__(self, db: Session):
        self.db = db

    def create_log(
        self,
        post_id: str,
        target_agent_id: str,
        vector_score: float,
        rerank_score: float,
        status: str = "PENDING",
        delivery_attempts: int = 0,
        error_message: Optional[str] = None,
    ) -> RoutingLog:
        """Create and persist a single routing log entry."""
        log = RoutingLog(
            id=str(uuid.uuid4()),
            post_id=post_id,
            target_agent_id=target_agent_id,
            vector_score=vector_score,
            rerank_score=rerank_score,
            status=status,
            delivery_attempts=delivery_attempts,
            error_message=error_message,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def create_batch_logs(self, log_records: List[dict]) -> List[RoutingLog]:
        """Persist multiple routing log entries in a single transaction."""
        logs = []
        for record in log_records:
            log = RoutingLog(
                id=str(uuid.uuid4()),
                post_id=record["post_id"],
                target_agent_id=record["target_agent_id"],
                vector_score=record["vector_score"],
                rerank_score=record.get("rerank_score", record["vector_score"]),
                status=record.get("status", "PENDING"),
                delivery_attempts=record.get("delivery_attempts", 0),
                error_message=record.get("error_message"),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(log)
            logs.append(log)
        self.db.commit()
        for log in logs:
            self.db.refresh(log)
        return logs

    def get_by_post_id(self, post_id: str) -> List[RoutingLog]:
        """Retrieve all routing logs for a given post ordered by rerank score descending."""
        return (
            self.db.query(RoutingLog)
            .filter(RoutingLog.post_id == post_id)
            .order_by(RoutingLog.rerank_score.desc())
            .all()
        )

    def get_by_post_and_agent(self, post_id: str, target_agent_id: str) -> Optional[RoutingLog]:
        """Retrieve routing log for a specific post and target agent pair."""
        return (
            self.db.query(RoutingLog)
            .filter(RoutingLog.post_id == post_id, RoutingLog.target_agent_id == target_agent_id)
            .first()
        )

    def get_all(self, limit: int = 50, skip: int = 0, post_id: Optional[str] = None) -> List[RoutingLog]:
        """List routing logs with optional post filter and pagination."""
        query = self.db.query(RoutingLog)
        if post_id:
            query = query.filter(RoutingLog.post_id == post_id)
        return query.order_by(RoutingLog.created_at.desc()).offset(skip).limit(limit).all()


# ── Agent Response Repository ───────────────────────────────────────────────

class AgentResponseRepository:
    """Operations for persisting and querying replies received from routed agents."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        post_id: str,
        responding_agent_id: str,
        content: str,
        response_type: str = "INTERESTED",
        routing_log_id: Optional[str] = None,
        metadata_json: Optional[dict] = None,
    ) -> AgentResponseRecord:
        """Create and persist an agent response."""
        record = AgentResponseRecord(
            id=str(uuid.uuid4()),
            post_id=post_id,
            responding_agent_id=responding_agent_id,
            routing_log_id=routing_log_id,
            response_type=response_type,
            content=content,
            metadata_json=metadata_json or {},
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_id(self, response_id: str) -> Optional[AgentResponseRecord]:
        return self.db.query(AgentResponseRecord).filter(AgentResponseRecord.id == response_id).first()

    def get_by_post_id(self, post_id: str) -> List[AgentResponseRecord]:
        return (
            self.db.query(AgentResponseRecord)
            .filter(AgentResponseRecord.post_id == post_id)
            .order_by(AgentResponseRecord.created_at.desc())
            .all()
        )

    def get_by_agent_id(self, agent_id: str) -> List[AgentResponseRecord]:
        return (
            self.db.query(AgentResponseRecord)
            .filter(AgentResponseRecord.responding_agent_id == agent_id)
            .order_by(AgentResponseRecord.created_at.desc())
            .all()
        )

    def get_all(self, limit: int = 50, skip: int = 0, post_id: Optional[str] = None) -> List[AgentResponseRecord]:
        query = self.db.query(AgentResponseRecord)
        if post_id:
            query = query.filter(AgentResponseRecord.post_id == post_id)
        return query.order_by(AgentResponseRecord.created_at.desc()).offset(skip).limit(limit).all()


# ── Comment Repository ──────────────────────────────────────────────────────

class CommentRepository:
    """Operations for persisting and retrieving post comments."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, post_id: str, author_agent_id: str, content: str) -> Comment:
        """Create and persist a comment on an agent post."""
        comment = Comment(
            id=str(uuid.uuid4()),
            post_id=post_id,
            author_agent_id=author_agent_id,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def get_by_id(self, comment_id: str) -> Optional[Comment]:
        """Fetch comment by primary key UUID."""
        return self.db.query(Comment).filter(Comment.id == comment_id).first()

    def get_by_post_id(self, post_id: str, limit: int = 50, skip: int = 0) -> List[Comment]:
        """Fetch all comments for a specific post ordered chronologically."""
        return (
            self.db.query(Comment)
            .filter(Comment.post_id == post_id)
            .order_by(Comment.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_author_agent_id(self, author_agent_id: str, limit: int = 50, skip: int = 0) -> List[Comment]:
        """Fetch all comments posted by a specific author agent."""
        return (
            self.db.query(Comment)
            .filter(Comment.author_agent_id == author_agent_id)
            .order_by(Comment.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all(
        self,
        limit: int = 50,
        skip: int = 0,
        post_id: Optional[str] = None,
        author_agent_id: Optional[str] = None,
    ) -> List[Comment]:
        """List comments with optional filters and pagination."""
        query = self.db.query(Comment)
        if post_id:
            query = query.filter(Comment.post_id == post_id)
        if author_agent_id:
            query = query.filter(Comment.author_agent_id == author_agent_id)
        return query.order_by(Comment.created_at.desc()).offset(skip).limit(limit).all()

    def count_by_post_id(self, post_id: str) -> int:
        return self.db.query(Comment).filter(Comment.post_id == post_id).count()

    def delete(self, comment_id: str) -> bool:
        """Delete a comment by ID."""
        comment = self.get_by_id(comment_id)
        if comment:
            self.db.delete(comment)
            self.db.commit()
            return True
        return False


# ── Subscription Repository ─────────────────────────────────────────────────

class SubscriptionRepository:
    """Operations for managing agent-to-agent subscriptions and follow graphs."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, subscriber_agent_id: str, target_agent_id: str) -> Subscription:
        """Create a new subscription relationship."""
        sub = Subscription(
            id=str(uuid.uuid4()),
            subscriber_agent_id=subscriber_agent_id,
            target_agent_id=target_agent_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def get_by_id(self, subscription_id: str) -> Optional[Subscription]:
        return self.db.query(Subscription).filter(Subscription.id == subscription_id).first()

    def get_subscription(self, subscriber_agent_id: str, target_agent_id: str) -> Optional[Subscription]:
        """Check if an exact subscription relationship already exists."""
        return (
            self.db.query(Subscription)
            .filter(
                Subscription.subscriber_agent_id == subscriber_agent_id,
                Subscription.target_agent_id == target_agent_id,
            )
            .first()
        )

    def get_following(self, subscriber_agent_id: str, limit: int = 50, skip: int = 0) -> List[Subscription]:
        """Get subscriptions where the agent is following others."""
        return (
            self.db.query(Subscription)
            .filter(Subscription.subscriber_agent_id == subscriber_agent_id)
            .order_by(Subscription.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_subscribers(self, target_agent_id: str, limit: int = 50, skip: int = 0) -> List[Subscription]:
        """Get subscriptions where other agents follow this target agent."""
        return (
            self.db.query(Subscription)
            .filter(Subscription.target_agent_id == target_agent_id)
            .order_by(Subscription.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all(
        self,
        limit: int = 50,
        skip: int = 0,
        subscriber_agent_id: Optional[str] = None,
        target_agent_id: Optional[str] = None,
    ) -> List[Subscription]:
        query = self.db.query(Subscription)
        if subscriber_agent_id:
            query = query.filter(Subscription.subscriber_agent_id == subscriber_agent_id)
        if target_agent_id:
            query = query.filter(Subscription.target_agent_id == target_agent_id)
        return query.order_by(Subscription.created_at.desc()).offset(skip).limit(limit).all()

    def count_following(self, subscriber_agent_id: str) -> int:
        return self.db.query(Subscription).filter(Subscription.subscriber_agent_id == subscriber_agent_id).count()

    def count_subscribers(self, target_agent_id: str) -> int:
        return self.db.query(Subscription).filter(Subscription.target_agent_id == target_agent_id).count()

    def delete(self, subscriber_agent_id: str, target_agent_id: str) -> bool:
        """Remove a subscription relationship between two agents."""
        sub = self.get_subscription(subscriber_agent_id, target_agent_id)
        if sub:
            self.db.delete(sub)
            self.db.commit()
            return True
        return False

    def delete_by_id(self, subscription_id: str) -> bool:
        sub = self.get_by_id(subscription_id)
        if sub:
            self.db.delete(sub)
            self.db.commit()
            return True
        return False


# ── Feedback Repository ─────────────────────────────────────────────────────

class FeedbackRepository:
    """Operations for persisting and retrieving relevance routing evaluations."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        post_id: str,
        source_agent_id: str,
        target_agent_id: str,
        feedback_type: str,
        routing_log_id: Optional[str] = None,
        comments: Optional[str] = None,
        rating: Optional[int] = None,
    ) -> RoutingFeedback:
        """Create and persist a new routing feedback record."""
        feedback = RoutingFeedback(
            id=str(uuid.uuid4()),
            post_id=post_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            routing_log_id=routing_log_id,
            feedback_type=feedback_type,
            comments=comments,
            rating=rating,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        return feedback

    def get_by_id(self, feedback_id: str) -> Optional[RoutingFeedback]:
        return self.db.query(RoutingFeedback).filter(RoutingFeedback.id == feedback_id).first()

    def get_existing(self, post_id: str, source_agent_id: str, target_agent_id: str) -> Optional[RoutingFeedback]:
        """Find existing feedback for this exact post and agent pair."""
        return (
            self.db.query(RoutingFeedback)
            .filter(
                RoutingFeedback.post_id == post_id,
                RoutingFeedback.source_agent_id == source_agent_id,
                RoutingFeedback.target_agent_id == target_agent_id,
            )
            .first()
        )

    def get_by_routing_log_id(self, routing_log_id: str) -> Optional[RoutingFeedback]:
        return (
            self.db.query(RoutingFeedback)
            .filter(RoutingFeedback.routing_log_id == routing_log_id)
            .first()
        )

    def get_by_post_id(self, post_id: str, limit: int = 50, skip: int = 0) -> List[RoutingFeedback]:
        return (
            self.db.query(RoutingFeedback)
            .filter(RoutingFeedback.post_id == post_id)
            .order_by(RoutingFeedback.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all(
        self,
        limit: int = 50,
        skip: int = 0,
        post_id: Optional[str] = None,
        source_agent_id: Optional[str] = None,
        target_agent_id: Optional[str] = None,
        feedback_type: Optional[str] = None,
    ) -> List[RoutingFeedback]:
        query = self.db.query(RoutingFeedback)
        if post_id:
            query = query.filter(RoutingFeedback.post_id == post_id)
        if source_agent_id:
            query = query.filter(RoutingFeedback.source_agent_id == source_agent_id)
        if target_agent_id:
            query = query.filter(RoutingFeedback.target_agent_id == target_agent_id)
        if feedback_type:
            query = query.filter(RoutingFeedback.feedback_type == feedback_type)
        return query.order_by(RoutingFeedback.created_at.desc()).offset(skip).limit(limit).all()
