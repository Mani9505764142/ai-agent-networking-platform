"""
Subscriptions API Router

Handles agent-to-agent subscriptions and follower graphs.
Validates agent existence, prevents self-subscriptions and duplicate subscriptions.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.utils import validate_uuid
from app.database.connection import get_db
from app.database.repository import AgentRepository, SubscriptionRepository
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionDeleteResponse,
    SubscriptionResponse,
)

router = APIRouter()


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe one agent to another",
)
def create_subscription(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
):
    """Subscribe an agent (subscriber) to another agent (target).

    Validates that:
    1. Both subscriber and target IDs are valid UUIDs.
    2. An agent cannot subscribe to itself.
    3. Both agents exist in the database.
    4. Duplicate subscriptions are rejected with HTTP 409 Conflict.
    """
    valid_sub_id = validate_uuid(payload.subscriber_agent_id, "subscriber_agent_id")
    valid_target_id = validate_uuid(payload.target_agent_id, "target_agent_id")

    if valid_sub_id == valid_target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Self-subscription is not allowed. An agent cannot subscribe to itself.",
        )

    agent_repo = AgentRepository(db)
    subscriber = agent_repo.get_by_id(valid_sub_id)
    if not subscriber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscriber agent with id '{payload.subscriber_agent_id}' does not exist.",
        )

    target = agent_repo.get_by_id(valid_target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target agent with id '{payload.target_agent_id}' does not exist.",
        )

    sub_repo = SubscriptionRepository(db)
    existing = sub_repo.get_subscription(valid_sub_id, valid_target_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent '{subscriber.company_name}' is already subscribed to '{target.company_name}'.",
        )

    return sub_repo.create(subscriber_agent_id=valid_sub_id, target_agent_id=valid_target_id)


@router.delete(
    "/{subscription_id}",
    response_model=SubscriptionDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Unsubscribe by subscription ID",
)
def delete_subscription_by_id(
    subscription_id: str,
    db: Session = Depends(get_db),
):
    """Remove a subscription relationship by its primary key UUID."""
    valid_id = validate_uuid(subscription_id, "subscription_id")
    sub_repo = SubscriptionRepository(db)
    sub = sub_repo.get_by_id(valid_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription with id '{subscription_id}' not found.",
        )

    sub_id = sub.subscriber_agent_id
    target_id = sub.target_agent_id
    sub_repo.delete_by_id(valid_id)

    return SubscriptionDeleteResponse(
        message="Subscription removed successfully.",
        subscriber_agent_id=sub_id,
        target_agent_id=target_id,
    )


@router.delete(
    "",
    response_model=SubscriptionDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Unsubscribe by agent pair",
)
def unsubscribe_agents(
    subscriber_agent_id: str = Query(..., description="UUID of the subscriber agent"),
    target_agent_id: str = Query(..., description="UUID of the target agent being unfollowed"),
    db: Session = Depends(get_db),
):
    """Remove a subscription by specifying subscriber and target agent UUIDs."""
    valid_sub_id = validate_uuid(subscriber_agent_id, "subscriber_agent_id")
    valid_target_id = validate_uuid(target_agent_id, "target_agent_id")

    sub_repo = SubscriptionRepository(db)
    existing = sub_repo.get_subscription(valid_sub_id, valid_target_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active subscription between '{subscriber_agent_id}' and '{target_agent_id}' not found.",
        )

    sub_repo.delete(valid_sub_id, valid_target_id)
    return SubscriptionDeleteResponse(
        message="Successfully unsubscribed from target agent.",
        subscriber_agent_id=valid_sub_id,
        target_agent_id=valid_target_id,
    )


@router.get(
    "",
    response_model=List[SubscriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="List subscriptions with optional filters",
)
def list_subscriptions(
    subscriber_agent_id: Optional[str] = Query(default=None, description="Filter by subscriber agent UUID"),
    target_agent_id: Optional[str] = Query(default=None, description="Filter by target agent UUID"),
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List subscription relationships."""
    valid_sub_id = validate_uuid(subscriber_agent_id, "subscriber_agent_id") if subscriber_agent_id else None
    valid_target_id = validate_uuid(target_agent_id, "target_agent_id") if target_agent_id else None

    sub_repo = SubscriptionRepository(db)
    return sub_repo.get_all(
        limit=limit,
        skip=skip,
        subscriber_agent_id=valid_sub_id,
        target_agent_id=valid_target_id,
    )


@router.get(
    "/following/{agent_id}",
    response_model=List[SubscriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="List agents followed by a specific agent",
)
def get_following(
    agent_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve all agents that the specified agent is following."""
    valid_id = validate_uuid(agent_id, "agent_id")
    agent_repo = AgentRepository(db)
    if not agent_repo.get_by_id(valid_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id '{agent_id}' not found.",
        )

    sub_repo = SubscriptionRepository(db)
    return sub_repo.get_following(valid_id, limit=limit, skip=skip)


@router.get(
    "/subscribers/{agent_id}",
    response_model=List[SubscriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="List subscribers of a specific agent",
)
def get_subscribers(
    agent_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve all subscribers (followers) of the specified agent."""
    valid_id = validate_uuid(agent_id, "agent_id")
    agent_repo = AgentRepository(db)
    if not agent_repo.get_by_id(valid_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id '{agent_id}' not found.",
        )

    sub_repo = SubscriptionRepository(db)
    return sub_repo.get_subscribers(valid_id, limit=limit, skip=skip)


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get subscription by ID",
)
def get_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific subscription by its UUID."""
    valid_id = validate_uuid(subscription_id, "subscription_id")
    sub_repo = SubscriptionRepository(db)
    sub = sub_repo.get_by_id(valid_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription with id '{subscription_id}' not found.",
        )
    return sub
