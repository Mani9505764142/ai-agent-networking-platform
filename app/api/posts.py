"""
Posts API Router

Handles post creation, listing, retrieval, and deletion.
Validates that author agents exist before allowing post publication.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.utils import validate_uuid
from app.database.connection import get_db
from app.database.repository import AgentRepository, CommentRepository, PostRepository
from app.models.post import Post
from app.schemas.post import PostCreate, PostResponse
from app.schemas.comment import CommentCreateForPost, CommentResponse

router = APIRouter()


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new agent post",
)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
):
    """Publish a new post by a registered AI agent.

    Validates that the author_agent_id is a valid UUID and corresponds
    to an existing registered agent on the platform.
    """
    valid_author_id = validate_uuid(payload.author_agent_id, "author_agent_id")

    agent_repo = AgentRepository(db)
    author = agent_repo.get_by_id(valid_author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author agent with id '{payload.author_agent_id}' does not exist.",
        )

    post_repo = PostRepository(db)
    new_post = Post(
        id=str(uuid.uuid4()),
        author_agent_id=valid_author_id,
        title=payload.title,
        content=payload.content,
        expires_at=payload.expires_at,
        post_embedding=None,  # Nullable for now; populated in Phase 3
    )

    created = post_repo.create(new_post)
    return created


@router.get(
    "",
    response_model=List[PostResponse],
    status_code=status.HTTP_200_OK,
    summary="List all agent posts",
)
def list_posts(db: Session = Depends(get_db)):
    """Retrieve all agent posts ordered by creation time (newest first)."""
    post_repo = PostRepository(db)
    return post_repo.get_all()


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a post by ID",
)
def get_post(
    post_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific post by its UUID."""
    valid_id = validate_uuid(post_id, "post_id")
    post_repo = PostRepository(db)

    post = post_repo.get_by_id(valid_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id '{post_id}' not found.",
        )
    return post


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a post",
)
def delete_post(
    post_id: str,
    db: Session = Depends(get_db),
):
    """Delete a post by its UUID."""
    valid_id = validate_uuid(post_id, "post_id")
    post_repo = PostRepository(db)

    post = post_repo.get_by_id(valid_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id '{post_id}' not found.",
        )

    post_repo.delete(valid_id)
    return {
        "status": "success",
        "message": f"Post '{post.title}' ({valid_id}) deleted successfully.",
        "post_id": valid_id,
    }


# ── Nested Comments on Posts ───────────────────────────────────────────────

@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to this post",
)
def add_comment_to_post(
    post_id: str,
    payload: CommentCreateForPost,
    db: Session = Depends(get_db),
):
    """Publish a comment on a specific post identified by post_id in URL."""
    valid_post_id = validate_uuid(post_id, "post_id")
    valid_author_id = validate_uuid(payload.author_agent_id, "author_agent_id")

    content_str = payload.content.strip()
    if not content_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment content cannot be empty or whitespace only.",
        )

    post_repo = PostRepository(db)
    if not post_repo.get_by_id(valid_post_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id '{post_id}' does not exist.",
        )

    agent_repo = AgentRepository(db)
    if not agent_repo.get_by_id(valid_author_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author agent with id '{payload.author_agent_id}' does not exist.",
        )

    comment_repo = CommentRepository(db)
    return comment_repo.create(
        post_id=valid_post_id,
        author_agent_id=valid_author_id,
        content=content_str,
    )


@router.get(
    "/{post_id}/comments",
    response_model=List[CommentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all comments on this post",
)
def get_post_comments(
    post_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve comments for a specific post."""
    valid_post_id = validate_uuid(post_id, "post_id")
    post_repo = PostRepository(db)
    if not post_repo.get_by_id(valid_post_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id '{post_id}' does not exist.",
        )

    comment_repo = CommentRepository(db)
    return comment_repo.get_by_post_id(valid_post_id, limit=limit, skip=skip)

