from enum import Enum
from typing import Annotated, Any
from pydantic import BaseModel, Field
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
