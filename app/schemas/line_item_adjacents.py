from enum import Enum
from typing import Annotated
from pydantic import BaseModel, Field, field_validator


class AdjacentPosition(str, Enum):
    """Allowed adjacent line item positions."""

    PREVIOUS = "Previous"
    NEXT = "Next"
    DUAL = "Dual"


ADJ_POS_LOOKUP = {item.value.lower(): item for item in AdjacentPosition}


def _validate_position(value: str | AdjacentPosition) -> AdjacentPosition:
    """Shared position validator used by multiple models."""
    if isinstance(value, AdjacentPosition):
        return value
    if not isinstance(value, str):
        allowed = ", ".join(item.value for item in AdjacentPosition)
        raise ValueError(f"position must be one of: {allowed}")
    normalized = ADJ_POS_LOOKUP.get(value.lower())
    if normalized is None:
        allowed = ", ".join(item.value for item in AdjacentPosition)
        raise ValueError(f"position must be one of: {allowed}")
    return normalized


class LineItemAdjacent(BaseModel):
    """Adjacent line item request model."""

    id: Annotated[int, Field(..., description="Adjacent line item ID")]
    position: Annotated[
        AdjacentPosition,
        Field(..., description="Adjacent item position"),
    ]
    index: Annotated[
        int | None,
        Field(None, description="Adjacent item ordering index"),
    ] = None

    @field_validator("position", mode="before")
    @classmethod
    def validate_position(cls, value: str | AdjacentPosition) -> AdjacentPosition:
        return _validate_position(value)


class LineItemAdjacentsUpdate(BaseModel):
    """Request model for adding adjacent line items."""

    items: Annotated[
        list[LineItemAdjacent],
        Field(..., min_length=1, description="Line items to connect as adjacents"),
    ]


class LineItemAdjacentsDelete(BaseModel):
    """Request model for disconnecting adjacent line items."""

    items: Annotated[
        list[int],
        Field(..., min_length=1, description="List of line item IDs to disconnect"),
    ]


class LineItemAdjacentPatch(BaseModel):
    """Request model for updating an adjacent line item's position and index."""

    position: Annotated[
        AdjacentPosition,
        Field(
            ...,
            description="New position of the linked item relative to the current one",
        ),
    ]
    index: Annotated[
        int | None,
        Field(
            None,
            description="Ordering index for multiple adjacent items at the same position",
        ),
    ] = None

    @field_validator("position", mode="before")
    @classmethod
    def validate_position(cls, value: str | AdjacentPosition) -> AdjacentPosition:
        return _validate_position(value)


class LineItemAdjacentData(BaseModel):
    """Adjacent line item response data model."""

    id: Annotated[int, Field(..., description="Auto-generated unique line item ID")]
    name: Annotated[str, Field(..., description="Line item name in the map")]
    description: Annotated[
        str | None,
        Field(None, description="Line item description"),
    ] = None
    position: Annotated[
        AdjacentPosition,
        Field(
            ..., description="Position of the linked item relative to the current one"
        ),
    ]
    index: Annotated[
        int | None,
        Field(
            None,
            description="Ordering index for multiple adjacent items at the same position",
        ),
    ] = None
    link: Annotated[
        str,
        Field(..., description="URL pointing to the line item resource"),
    ]


class LineItemAdjacentsListResponse(BaseModel):
    """Response model for listing adjacent line items with pagination."""

    page: Annotated[int, Field(..., description="Current page number")]
    per_page: Annotated[int, Field(..., description="Items per page")]
    total: Annotated[int, Field(..., description="Total number of items")]
    data: Annotated[
        list[LineItemAdjacentData],
        Field(..., description="List of adjacent line items"),
    ]
