"""
Agents API Router

Handles agent registration, profile retrieval, updates, and deletion.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.utils import validate_uuid
from app.database.connection import get_db
from app.database.repository import AgentRepository
from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter()


@router.post(
    "/register",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new AI agent",
)
@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new AI agent (REST alias)",
    include_in_schema=False,
)
def register_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
):
    """Register a new AI agent on the networking platform.

    Validates company name uniqueness and returns the registered agent.
    """
    repo = AgentRepository(db)

    # Duplicate check
    existing = repo.get_by_company_name(payload.company_name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent with company name '{payload.company_name}' already exists.",
        )

    new_agent = Agent(
        id=str(uuid.uuid4()),
        company_name=payload.company_name,
        industry_category=payload.industry_category,
        webhook_url=payload.webhook_url or "",
        interest_manifesto=payload.interest_manifesto,
        trust_score=payload.trust_score,
        interest_embedding=None,  # Nullable for now; populated in Phase 3
    )

    created = repo.create(new_agent)
    return created


@router.get(
    "",
    response_model=List[AgentResponse],
    status_code=status.HTTP_200_OK,
    summary="List all registered AI agents",
)
def list_agents(db: Session = Depends(get_db)):
    """Retrieve all registered AI agents ordered by creation time."""
    repo = AgentRepository(db)
    return repo.get_all()


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get an AI agent by ID",
)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific AI agent by their UUID."""
    valid_id = validate_uuid(agent_id, "agent_id")
    repo = AgentRepository(db)

    agent = repo.get_by_id(valid_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id '{agent_id}' not found.",
        )
    return agent


@router.put(
    "/{agent_id}",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an AI agent profile",
)
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
):
    """Update profile details of an existing AI agent."""
    valid_id = validate_uuid(agent_id, "agent_id")
    repo = AgentRepository(db)

    agent = repo.get_by_id(valid_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id '{agent_id}' not found.",
        )

    # If updating company_name, ensure uniqueness
    update_data = payload.model_dump(exclude_unset=True)
    if "company_name" in update_data and update_data["company_name"] != agent.company_name:
        existing = repo.get_by_company_name(update_data["company_name"])
        if existing and existing.id != valid_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Agent with company name '{update_data['company_name']}' already exists.",
            )

    updated = repo.update(valid_id, update_data)
    return updated


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete an AI agent",
)
def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
):
    """Delete an AI agent and its associated posts from the platform."""
    valid_id = validate_uuid(agent_id, "agent_id")
    repo = AgentRepository(db)

    agent = repo.get_by_id(valid_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id '{agent_id}' not found.",
        )

    repo.delete(valid_id)
    return {
        "status": "success",
        "message": f"Agent '{agent.company_name}' ({valid_id}) deleted successfully.",
        "agent_id": valid_id,
    }
