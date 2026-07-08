from typing import Annotated, Any
from pydantic import BaseModel, Field

from app.schemas.common import NonNestedDict


class LineItemConnection(BaseModel):
    id: Annotated[int, Field(..., description="Connected line item ID")]
    properties: Annotated[
        NonNestedDict,
        Field(
            default_factory=dict,
            description="Properties of the connection relationship",
        ),
    ]


class LineItemConnectionData(BaseModel):
    """Connected non-line item data model."""

    id: Annotated[int, Field(..., description="Auto-generated unique item ID")]
    properties: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="Properties of the connection relationship",
        ),
    ]
    name: Annotated[str, Field(..., description="Item name in the map")]
    description: Annotated[
        str | None,
        Field(None, description="Item description"),
    ] = None
    link: Annotated[
        str,
        Field(..., description="URL pointing to the non-line item resource"),
    ]


class LineItemConnectionsListResponse(BaseModel):
    """Response model for listing connected non-line items with pagination."""

    page: Annotated[int, Field(..., description="Current page number")]
    per_page: Annotated[int, Field(..., description="Items per page")]
    total: Annotated[int, Field(..., description="Total number of items")]
    data: Annotated[
        list[LineItemConnectionData],
        Field(..., description="List of connected non-line items"),
    ]


class LineItemConnectionsUpdate(BaseModel):
    """Request model for adding non-line item connections to a line item."""

    items: Annotated[
        list[LineItemConnection],
        Field(..., min_length=1, description="List of non-line item to connect"),
    ]


class LineItemConnectionsDelete(BaseModel):
    """Request model for disconnecting non-line items from a line item."""

    items: Annotated[
        list[int],
        Field(..., min_length=1, description="List of non-line item IDs to disconnect"),
    ]
