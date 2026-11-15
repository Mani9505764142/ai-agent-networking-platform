"""
Comments API Router

Handles comments and threaded discussions on agent posts.
Validates that posts and author agents exist before allowing comment publication.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.utils import validate_uuid
from app.database.connection import get_db
from app.database.repository import AgentRepository, CommentRepository, PostRepository
from app.schemas.comment import CommentCreate, CommentResponse

router = APIRouter()


@router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment on a post",
)
def create_comment(
    payload: CommentCreate,
    db: Session = Depends(get_db),
):
    """Publish a new comment on an agent post.

    Validates that:
    1. post_id is a valid UUID and references an existing post.
    2. author_agent_id is a valid UUID and references an existing agent.
    3. content is non-empty.
    """
    valid_post_id = validate_uuid(payload.post_id, "post_id")
    valid_author_id = validate_uuid(payload.author_agent_id, "author_agent_id")

    content_str = payload.content.strip()
    if not content_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment content cannot be empty or whitespace only.",
        )

    # Validate post exists
    post_repo = PostRepository(db)
    post = post_repo.get_by_id(valid_post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id '{payload.post_id}' does not exist.",
        )

    # Validate author agent exists
    agent_repo = AgentRepository(db)
    author = agent_repo.get_by_id(valid_author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author agent with id '{payload.author_agent_id}' does not exist.",
        )

    comment_repo = CommentRepository(db)
    comment = comment_repo.create(
        post_id=valid_post_id,
        author_agent_id=valid_author_id,
        content=content_str,
    )
    return comment


@router.get(
    "",
    response_model=List[CommentResponse],
    status_code=status.HTTP_200_OK,
    summary="List comments with optional filters",
)
def list_comments(
    post_id: Optional[str] = Query(default=None, description="Filter comments by post UUID"),
    author_agent_id: Optional[str] = Query(default=None, description="Filter comments by author agent UUID"),
    limit: int = Query(default=50, ge=1, le=100, description="Max comments to return"),
    skip: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """Retrieve comments ordered by creation timestamp.

    Optionally filters by post_id or author_agent_id.
    """
    valid_post_id = validate_uuid(post_id, "post_id") if post_id else None
    valid_author_id = validate_uuid(author_agent_id, "author_agent_id") if author_agent_id else None

    # If post_id filter specified, verify post exists
    if valid_post_id:
        post_repo = PostRepository(db)
        if not post_repo.get_by_id(valid_post_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post with id '{post_id}' not found.",
            )

    # If author_agent_id filter specified, verify agent exists
    if valid_author_id:
        agent_repo = AgentRepository(db)
        if not agent_repo.get_by_id(valid_author_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with id '{author_agent_id}' not found.",
            )

    comment_repo = CommentRepository(db)
    return comment_repo.get_all(
        limit=limit,
        skip=skip,
        post_id=valid_post_id,
        author_agent_id=valid_author_id,
    )


@router.get(
    "/{comment_id}",
    response_model=CommentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a comment by ID",
)
def get_comment(
    comment_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific comment by its UUID."""
    valid_id = validate_uuid(comment_id, "comment_id")
    comment_repo = CommentRepository(db)
    comment = comment_repo.get_by_id(valid_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment with id '{comment_id}' not found.",
        )
    return comment


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a comment",
)
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
):
    """Delete a comment by its UUID."""
    valid_id = validate_uuid(comment_id, "comment_id")
    comment_repo = CommentRepository(db)
    deleted = comment_repo.delete(valid_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment with id '{comment_id}' not found.",
        )
    return {"message": "Comment deleted successfully", "comment_id": comment_id}
