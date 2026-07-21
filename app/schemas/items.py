"""Schemas for items whose kind vocabulary is managed in Neo4j."""

from enum import IntEnum
from typing import Annotated
from pydantic import BaseModel, Field
from app.schemas.common import ListIntNoDuplicates, NonEmptyStr


class ItemStatus(IntEnum):
    """Allowed non-line item statuses."""

    ACTIVE = 0
    UNMOUNTED = 1
    MAINTENANCE = 2
    DISMITTED = 3


class ItemCreate(BaseModel):
    """Request model for creating a new non-line item."""

    name: Annotated[NonEmptyStr, Field(..., description="Unique item name")]
    description: Annotated[
        str | None,
        Field(None, description="Optional item description"),
    ] = None
    kind: Annotated[
        NonEmptyStr,
        Field(..., description="Item kind - must match an existing ItemKind"),
    ]
    status: Annotated[
        ItemStatus,
        Field(default=ItemStatus.ACTIVE, description="Item status"),
    ]
    connections: Annotated[
        ListIntNoDuplicates,
        Field(default_factory=list, description="IDs of items to connect to"),
    ]
    labels: Annotated[
        list[str],
        Field(default_factory=list, description="Optional list of labels"),
    ]
    aliases: Annotated[
        list[str],
        Field(default_factory=list, description="Optional list of aliases"),
    ]


class ItemCreateResponse(BaseModel):
    """Response model for creating a new non-line item."""

    id: Annotated[int, Field(..., description="Auto-generated item ID")]


class ItemUpdate(BaseModel):
    """Request model for updating a non-line item."""

    name: Annotated[
        NonEmptyStr | None,
        Field(None, description="Updated item name"),
    ] = None
    description: Annotated[
        str | None,
        Field(None, description="Updated item description"),
    ] = None
    status: Annotated[
        ItemStatus | None,
        Field(None, description="Updated item status"),
    ] = None
    kind: Annotated[
        NonEmptyStr | None,
        Field(None, description="Updated kind - must match an existing ItemKind"),
    ] = None
    labels: Annotated[
        list[str] | None,
        Field(None, description="Updated list of labels"),
    ] = None
    aliases: Annotated[
        list[str] | None,
        Field(None, description="Updated list of aliases"),
    ] = None


class ItemData(BaseModel):
    """Non-line item summary data model."""

    id: Annotated[int, Field(..., description="Auto-generated unique item ID")]
    name: Annotated[str, Field(..., description="Item name")]
    description: Annotated[
        str | None,
        Field(None, description="Item description"),
    ] = None


class ItemListResponse(BaseModel):
    """Response model for listing non-line items with pagination."""

    page: Annotated[int, Field(..., description="Current page number")]
    per_page: Annotated[int, Field(..., description="Items per page")]
    total: Annotated[int, Field(..., description="Total number of items")]
    data: Annotated[
        list[ItemData],
        Field(..., description="List of non-line items"),
    ]


class ItemDetailData(ItemData):
    """Non-line item detail data model."""

    kind: Annotated[str, Field(..., description="Item kind")]
    status: Annotated[ItemStatus, Field(..., description="Item status")]
    labels: Annotated[
        list[str],
        Field(default_factory=list, description="List of labels"),
    ]
    aliases: Annotated[
        list[str],
        Field(default_factory=list, description="List of aliases"),
    ]


class ItemLinksModel(BaseModel):
    """Links model for related non-line item resources."""

    connections: Annotated[
        str,
        Field(..., description="URL pointing to related connection resources"),
    ]


class ItemDetailResponse(BaseModel):
    """Response model for retrieving a specific non-line item."""

    links: Annotated[ItemLinksModel, Field(..., description="Related resource links")]
    data: Annotated[ItemDetailData, Field(..., description="Item details")]
