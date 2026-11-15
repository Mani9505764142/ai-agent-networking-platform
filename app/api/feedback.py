"""
Feedback API Router

Handles agent evaluation feedback on intelligent relevance routing outcomes.
Allows agents to submit structured relevance assessments (RELEVANT, NOT_RELEVANT,
USEFUL, NOT_USEFUL) to continuously monitor and improve routing quality.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.utils import validate_uuid
from app.database.connection import get_db
from app.database.repository import AgentRepository, FeedbackRepository, PostRepository, RoutingRepository
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackCreateForLog,
    FeedbackResponse,
)

router = APIRouter()


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback on a routing result",
)
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
):
    """Submit evaluation feedback for an intelligent routing result.

    Validates that:
    1. post_id references an existing post.
    2. source_agent_id references an existing agent.
    3. target_agent_id references an existing agent.
    4. If routing_log_id is supplied, it references an existing routing log matching post & target.
    5. Duplicate feedback for the same post + source agent + target agent is rejected (HTTP 409).
    """
    valid_post_id = validate_uuid(payload.post_id, "post_id")
    valid_source_id = validate_uuid(payload.source_agent_id, "source_agent_id")
    valid_target_id = validate_uuid(payload.target_agent_id, "target_agent_id")
    valid_log_id = validate_uuid(payload.routing_log_id, "routing_log_id") if payload.routing_log_id else None

    # Verify post exists
    post_repo = PostRepository(db)
    if not post_repo.get_by_id(valid_post_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id '{payload.post_id}' does not exist.",
        )

    # Verify source agent exists
    agent_repo = AgentRepository(db)
    if not agent_repo.get_by_id(valid_source_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source agent with id '{payload.source_agent_id}' does not exist.",
        )

    # Verify target agent exists
    if not agent_repo.get_by_id(valid_target_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target agent with id '{payload.target_agent_id}' does not exist.",
        )

    # Verify routing_log if provided
    if valid_log_id:
        routing_repo = RoutingRepository(db)
        log = routing_repo.db.query(routing_repo.db.query(routing_repo.create_log.__annotations__.get("return")).column_descriptions[0]["type"]).filter_by(id=valid_log_id).first() if False else db.query(
            routing_repo.create_log.__annotations__.get("return", None) or type(routing_repo.get_by_post_id("dummy"))
        )
        # Cleaner: direct query on RoutingLog
        from app.models.routing_log import RoutingLog
        log_record = db.query(RoutingLog).filter(RoutingLog.id == valid_log_id).first()
        if not log_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Routing log with id '{payload.routing_log_id}' does not exist.",
            )
        if log_record.post_id != valid_post_id or log_record.target_agent_id != valid_target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Routing log does not match the specified post_id and target_agent_id.",
            )

    feedback_repo = FeedbackRepository(db)
    existing = feedback_repo.get_existing(valid_post_id, valid_source_id, valid_target_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback has already been submitted for this post and candidate agent pair.",
        )

    return feedback_repo.create(
        post_id=valid_post_id,
        source_agent_id=valid_source_id,
        target_agent_id=valid_target_id,
        feedback_type=payload.feedback_type,
        routing_log_id=valid_log_id,
        comments=payload.comments,
        rating=payload.rating,
    )


@router.post(
    "/routing-logs/{routing_log_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback against a routing log",
)
def create_feedback_for_routing_log(
    routing_log_id: str,
    payload: FeedbackCreateForLog,
    db: Session = Depends(get_db),
):
    """Submit evaluation feedback directly referencing a routing log ID."""
    valid_log_id = validate_uuid(routing_log_id, "routing_log_id")
    valid_source_id = validate_uuid(payload.source_agent_id, "source_agent_id")

    from app.models.routing_log import RoutingLog
    log_record = db.query(RoutingLog).filter(RoutingLog.id == valid_log_id).first()
    if not log_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routing log with id '{routing_log_id}' does not exist.",
        )

    agent_repo = AgentRepository(db)
    if not agent_repo.get_by_id(valid_source_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source agent with id '{payload.source_agent_id}' does not exist.",
        )

    feedback_repo = FeedbackRepository(db)
    existing = feedback_repo.get_existing(log_record.post_id, valid_source_id, log_record.target_agent_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback has already been submitted for this post and candidate agent pair.",
        )

    return feedback_repo.create(
        post_id=log_record.post_id,
        source_agent_id=valid_source_id,
        target_agent_id=log_record.target_agent_id,
        feedback_type=payload.feedback_type,
        routing_log_id=valid_log_id,
        comments=payload.comments,
        rating=payload.rating,
    )


@router.get(
    "",
    response_model=List[FeedbackResponse],
    status_code=status.HTTP_200_OK,
    summary="List feedback with optional filters",
)
def list_feedback(
    post_id: Optional[str] = Query(default=None, description="Filter by post UUID"),
    source_agent_id: Optional[str] = Query(default=None, description="Filter by source agent UUID"),
    target_agent_id: Optional[str] = Query(default=None, description="Filter by target agent UUID"),
    feedback_type: Optional[str] = Query(default=None, description="Filter by feedback classification"),
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve submitted routing evaluations with optional filtering."""
    valid_post_id = validate_uuid(post_id, "post_id") if post_id else None
    valid_source_id = validate_uuid(source_agent_id, "source_agent_id") if source_agent_id else None
    valid_target_id = validate_uuid(target_agent_id, "target_agent_id") if target_agent_id else None

    # Validate post exists if filtered
    if valid_post_id:
        post_repo = PostRepository(db)
        if not post_repo.get_by_id(valid_post_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post with id '{post_id}' not found.",
            )

    # Validate source agent exists if filtered
    agent_repo = AgentRepository(db)
    if valid_source_id and not agent_repo.get_by_id(valid_source_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source agent with id '{source_agent_id}' not found.",
        )

    # Validate target agent exists if filtered
    if valid_target_id and not agent_repo.get_by_id(valid_target_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target agent with id '{target_agent_id}' not found.",
        )

    feedback_repo = FeedbackRepository(db)
    return feedback_repo.get_all(
        limit=limit,
        skip=skip,
        post_id=valid_post_id,
        source_agent_id=valid_source_id,
        target_agent_id=valid_target_id,
        feedback_type=feedback_type.upper() if feedback_type else None,
    )


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Get feedback by ID",
)
def get_feedback(
    feedback_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific feedback record by UUID."""
    valid_id = validate_uuid(feedback_id, "feedback_id")
    feedback_repo = FeedbackRepository(db)
    record = feedback_repo.get_by_id(valid_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routing feedback with id '{feedback_id}' not found.",
        )
    return record
