from typing import Annotated, Any
from pydantic import BaseModel, Field

from app.schemas.common import NonNestedDict


class ItemConnection(BaseModel):
    id: Annotated[int, Field(..., description="Connected item ID")]
    properties: Annotated[
        NonNestedDict,
        Field(
            default_factory=dict,
            description="Properties of the connection relationship",
        ),
    ]


class ItemConnectionsUpdate(BaseModel):
    """Request model for adding connections to a non-line item."""

    items: Annotated[
        list[ItemConnection],
        Field(..., min_length=1, description="Items to connect"),
    ]


class ItemConnectionsDelete(BaseModel):
    """Request model for disconnecting items from a non-line item."""

    items: Annotated[
        list[int],
        Field(..., min_length=1, description="List of item IDs to disconnect"),
    ]


class ItemConnectionData(BaseModel):
    """Connected item data model (non-line item)."""

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
        Field(..., description="URL pointing to the linked item resource"),
    ]


class ItemConnectionsListResponse(BaseModel):
    """Response model for listing connected items with pagination."""

    page: Annotated[int, Field(..., description="Current page number")]
    per_page: Annotated[int, Field(..., description="Items per page")]
    total: Annotated[int, Field(..., description="Total number of items")]
    data: Annotated[
        list[ItemConnectionData],
        Field(..., description="List of connected non-line items"),
    ]


class ItemLineItemConnectionData(BaseModel):
    """Line item data model as seen from a connected non-line item."""

    id: Annotated[int, Field(..., description="Auto-generated unique line item ID")]
    name: Annotated[str, Field(..., description="Line item name in the map")]
    description: Annotated[
        str | None,
        Field(None, description="Line item description"),
    ] = None
    link: Annotated[
        str,
        Field(..., description="URL pointing to the line item resource"),
    ]


class ItemLineItemConnectionsListResponse(BaseModel):
    """Response model for listing line items connected to a non-line item."""

    page: Annotated[int, Field(..., description="Current page number")]
    per_page: Annotated[int, Field(..., description="Items per page")]
    total: Annotated[int, Field(..., description="Total number of items")]
    data: Annotated[
        list[ItemLineItemConnectionData],
        Field(..., description="List of connected line items"),
    ]
