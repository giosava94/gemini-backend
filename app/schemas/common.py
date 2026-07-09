from enum import Enum
from typing import Annotated, Any
from pydantic import AfterValidator, BaseModel, Field
from datetime import datetime


class StatusEnum(str, Enum):
    """Service health status enumeration."""

    HEALTHY = "HEALTHY"
    NOT_HEALTHY = "NOT_HEALTHY"


class HealthResponse(BaseModel):
    """Health check response model."""

    status: Annotated[StatusEnum, Field(description="Service generic status")]
    details: Annotated[dict[str, Any], Field(description="Detailed status information")]
    timestamp: Annotated[
        datetime, Field(description="ISO 8601 formatted timestamp of the health check")
    ]


# Shared type alias used across multiple schema modules
NonEmptyStr = Annotated[str, Field(min_length=1)]


def ensure_no_nested_dicts(value: dict[str, Any]) -> dict[str, Any]:
    """Validator to ensure that the dictionary does not contain nested dictionaries."""
    if any(isinstance(v, dict) for v in value.values()):
        raise ValueError("Nested dictionaries are not allowed in connection properties")
    return value


NonNestedDict = Annotated[dict[str, Any], AfterValidator(ensure_no_nested_dicts)]


def drop_duplicates_int(v: list[int]) -> list[int]:
    """Validator to remove duplicated values"""
    return list(set(v))


ListIntNoDuplicates = Annotated[list[int], AfterValidator(drop_duplicates_int)]
