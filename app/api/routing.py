"""
Routing API Router

Endpoints for intelligent relevance routing of agent posts, multi-factor
reranking, audited webhook notifications, and agent response handling.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.utils import validate_uuid
from app.database.connection import get_db
from app.database.repository import AgentRepository, AgentResponseRepository, PostRepository, RoutingRepository
from app.schemas.response import AgentResponseCreate, AgentResponseDetail
from app.schemas.routing import RoutingLogResponse, RoutingResponse
from app.services.embedding_service import EmbeddingAPIError, EmbeddingConfigError
from app.services.routing_service import PostNotFoundError, RoutingService

router = APIRouter()


@router.post(
    "/posts/{post_id}",
    response_model=RoutingResponse,
    status_code=status.HTTP_200_OK,
    summary="Route a post to relevant agents with reranking",
)
def route_post(
    post_id: str,
    limit: int = Query(default=10, ge=1, le=100, description="Max target agents to match"),
    min_similarity: Optional[float] = Query(default=None, ge=-1.0, le=1.0, description="Minimum raw vector similarity threshold"),
    min_rerank_threshold: Optional[float] = Query(default=0.35, ge=0.0, le=1.0, description="Minimum rerank score threshold"),
    dispatch_webhooks: bool = Query(default=False, description="Whether to dispatch live HTTP webhooks immediately"),
    db: Session = Depends(get_db),
):
    """Trigger intelligent relevance routing for a given post.

    Calculates cosine vector similarity, applies multi-factor reranking
    (lexical overlap, industry alignment, trust weighting), filters out
    agents below min_rerank_threshold, records decision logs, and optionally
    dispatches webhooks.
    """
    valid_id = validate_uuid(post_id, "post_id")
    service = RoutingService(db)

    try:
        return service.route_post(
            post_id=valid_id,
            limit=limit,
            min_similarity=min_similarity,
            min_rerank_threshold=min_rerank_threshold,
            dispatch_webhooks=dispatch_webhooks,
        )
    except PostNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except EmbeddingConfigError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service not configured: {e}",
        )
    except EmbeddingAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding generation error: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Routing failure: {e}",
        )


@router.post(
    "/{post_id}",
    response_model=RoutingResponse,
    status_code=status.HTTP_200_OK,
    summary="Route a post (convenience alias)",
    include_in_schema=False,
)
def route_post_alias(
    post_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    min_similarity: Optional[float] = Query(default=None, ge=-1.0, le=1.0),
    min_rerank_threshold: Optional[float] = Query(default=0.35, ge=0.0, le=1.0),
    dispatch_webhooks: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Convenience alias for POST /posts/{post_id}."""
    return route_post(
        post_id=post_id,
        limit=limit,
        min_similarity=min_similarity,
        min_rerank_threshold=min_rerank_threshold,
        dispatch_webhooks=dispatch_webhooks,
        db=db,
    )


@router.get(
    "/logs",
    response_model=List[RoutingLogResponse],
    status_code=status.HTTP_200_OK,
    summary="List all routing logs",
)
def list_routing_logs(
    post_id: Optional[str] = Query(default=None, description="Filter logs by post UUID"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of logs to return"),
    skip: int = Query(default=0, ge=0, description="Number of logs to skip"),
    db: Session = Depends(get_db),
):
    """Retrieve historical routing logs, optionally filtered by post ID."""
    if post_id:
        post_id = validate_uuid(post_id, "post_id")

    repo = RoutingRepository(db)
    return repo.get_all(limit=limit, skip=skip, post_id=post_id)


@router.get(
    "/logs/{post_id}",
    response_model=List[RoutingLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get routing logs for a specific post",
)
def get_routing_logs_for_post(
    post_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve all routing logs recorded for a specific post ordered by score."""
    valid_id = validate_uuid(post_id, "post_id")
    repo = RoutingRepository(db)
    return repo.get_by_post_id(valid_id)


# ── Agent Response Endpoints ────────────────────────────────────────────────

@router.post(
    "/responses",
    response_model=AgentResponseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Receive an agent reply to a routed post",
)
def submit_agent_response(
    payload: AgentResponseCreate,
    db: Session = Depends(get_db),
):
    """Receive and record a response/bid/proposal from an agent for a routed post.

    Validates that:
    1. Both post_id and responding_agent_id are valid UUIDs.
    2. The referenced post exists in the database.
    3. The responding agent exists in the database.
    4. Automatically associates with the corresponding routing_log if available.
    """
    valid_post_id = validate_uuid(payload.post_id, "post_id")
    valid_agent_id = validate_uuid(payload.responding_agent_id, "responding_agent_id")

    # 1. Verify Post exists
    post_repo = PostRepository(db)
    post = post_repo.get_by_id(valid_post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id '{payload.post_id}' does not exist.",
        )

    # 2. Verify Responding Agent exists
    agent_repo = AgentRepository(db)
    agent = agent_repo.get_by_id(valid_agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id '{payload.responding_agent_id}' does not exist.",
        )

    # 3. Associate with RoutingLog if exists
    routing_repo = RoutingRepository(db)
    routing_log = routing_repo.get_by_post_and_agent(valid_post_id, valid_agent_id)
    routing_log_id = routing_log.id if routing_log else None

    # 4. Store response in dedicated agent_responses table
    response_repo = AgentResponseRepository(db)
    created_response = response_repo.create(
        post_id=valid_post_id,
        responding_agent_id=valid_agent_id,
        content=payload.content,
        response_type=payload.response_type,
        routing_log_id=routing_log_id,
        metadata_json=payload.metadata or {},
    )

    return created_response


@router.get(
    "/responses/{post_id}",
    response_model=List[AgentResponseDetail],
    status_code=status.HTTP_200_OK,
    summary="Get all agent responses for a post",
)
def get_responses_for_post(
    post_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve all replies and proposals submitted by agents for a specific post."""
    valid_post_id = validate_uuid(post_id, "post_id")

    post_repo = PostRepository(db)
    post = post_repo.get_by_id(valid_post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id '{post_id}' does not exist.",
        )

    response_repo = AgentResponseRepository(db)
    return response_repo.get_by_post_id(valid_post_id)
