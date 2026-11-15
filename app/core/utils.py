"""
Core Utilities

Common helper functions, validation routines, and formatters.
"""

import uuid
from fastapi import HTTPException, status


def validate_uuid(val: str, field_name: str = "id") -> str:
    """Validate that a given string is a valid UUID.

    Raises HTTP 400 Bad Request if the format is invalid.
    """
    try:
        uuid_obj = uuid.UUID(str(val).strip())
        return str(uuid_obj)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. '{val}' is not a valid UUID.",
        )
