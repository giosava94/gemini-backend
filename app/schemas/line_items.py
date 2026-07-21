"""Pydantic schemas for the LineItem resource.

Line item *kind* values are no longer a hard-coded Python enum.  They are
stored as ``LineItemKind`` nodes in Neo4j and validated against the database
at request time by the router layer.  The ``kind`` field here is therefore a
plain non-empty string; the router is responsible for rejecting unknown kinds
with a ``422`` response.
"""

from enum import IntEnum
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import ListIntNoDuplicates, NonEmptyStr


class LineItemStatus(IntEnum):
    """Allowed line item statuses.

    :cvar DISABLED: The line item is disabled (``0``).
    :cvar ENABLED: The line item is enabled (``1``).
    :cvar MAINTENANCE: The line item is under maintenance (``2``).
    """

    DISABLED = 0
    ENABLED = 1
    MAINTENANCE = 2


class LineItemCreate(BaseModel):
    """Request model for creating a new line item.

    The ``kind`` field must match the ``name`` of an existing
    ``LineItemKind`` node in the database.  Validation is performed by the
    router; schema-level validation only enforces that the value is a
    non-empty string.
    """

    name: Annotated[NonEmptyStr, Field(..., description="Unique line item name")]
    description: Annotated[
        str | None,
        Field(None, description="Optional item description"),
    ] = None
    kind: Annotated[
        NonEmptyStr,
        Field(..., description="Line item kind - must match an existing LineItemKind"),
    ]
    status: Annotated[
        LineItemStatus,
        Field(default=LineItemStatus.ENABLED, description="Line item status"),
    ]
    adjacents: Annotated[
        list["LineItemAdjacent"],
        Field(default_factory=list),
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


class LineItemCreateResponse(BaseModel):
    """Response model for creating a new line item."""

    id: Annotated[int, Field(..., description="Auto-generated item ID")]


class LineItemUpdate(BaseModel):
    """Request model for partially updating a line item.

    All fields are optional.  When ``kind`` is supplied it must match an
    existing ``LineItemKind`` node; validation is performed by the router.
    """

    name: Annotated[
        NonEmptyStr | None,
        Field(None, description="Updated line item name"),
    ] = None
    description: Annotated[
        str | None,
        Field(None, description="Updated line item description"),
    ] = None
    status: Annotated[
        LineItemStatus | None,
        Field(None, description="Updated line item status"),
    ] = None
    kind: Annotated[
        NonEmptyStr | None,
        Field(None, description="Updated kind — must match an existing LineItemKind"),
    ] = None
    labels: Annotated[
        list[str] | None,
        Field(None, description="Updated list of labels"),
    ] = None
    aliases: Annotated[
        list[str] | None,
        Field(None, description="Updated list of aliases"),
    ] = None


class LineItemData(BaseModel):
    """Line item summary data model (used in list responses)."""

    id: Annotated[int, Field(..., description="Auto-generated unique line item ID")]
    name: Annotated[str, Field(..., description="Line item name")]
    description: Annotated[
        str | None,
        Field(None, description="Line item description"),
    ] = None


class LineItemListResponse(BaseModel):
    """Response model for listing line items with pagination."""

    page: Annotated[int, Field(..., description="Current page number")]
    per_page: Annotated[int, Field(..., description="Items per page")]
    total: Annotated[int, Field(..., description="Total number of items")]
    data: Annotated[
        list[LineItemData],
        Field(..., description="List of line items"),
    ]


class LineItemDetailData(LineItemData):
    """Line item detail data model (used in single-item responses)."""

    kind: Annotated[str, Field(..., description="Line item kind")]
    status: Annotated[LineItemStatus, Field(..., description="Line item status")]
    labels: Annotated[
        list[str],
        Field(default_factory=list, description="List of labels"),
    ]
    aliases: Annotated[
        list[str],
        Field(default_factory=list, description="List of aliases"),
    ]


class LineItemLinksModel(BaseModel):
    """Links model for related line item resources."""

    adjacents: Annotated[
        str,
        Field(..., description="URL pointing to related adjacent resources"),
    ]
    connections: Annotated[
        str,
        Field(..., description="URL pointing to related connection resources"),
    ]


class LineItemDetailResponse(BaseModel):
    """Response model for retrieving a specific line item with links."""

    links: Annotated[LineItemLinksModel, Field(..., description="Related links")]
    data: Annotated[LineItemDetailData, Field(..., description="Line item details")]


# Avoid circular import: LineItemAdjacent is defined in line_item_adjacents
# and referenced in LineItemCreate above - resolved via forward reference + model_rebuild.
from app.schemas.line_item_adjacents import LineItemAdjacent  # noqa: E402

LineItemCreate.model_rebuild()
