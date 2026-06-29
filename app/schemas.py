from enum import Enum, IntEnum
from typing import Annotated, Any
from pydantic import BaseModel, Field, field_validator
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


# Beam line models
NonEmptyStr = Annotated[str, Field(min_length=1)]


class BeamLineCreate(BaseModel):
    """Request model for creating a new beam line."""

    name: Annotated[NonEmptyStr, Field(..., description="Unique beam line name")]
    description: Annotated[
        str | None,
        Field(None, description="Optional beam line description"),
    ] = None


class BeamLineUpdate(BaseModel):
    """Request model for updating a beam line."""

    name: Annotated[
        NonEmptyStr | None,
        Field(None, description="Updated beam line name"),
    ] = None
    description: Annotated[
        str | None,
        Field(None, description="Updated beam line description"),
    ] = None


class BeamLineData(BaseModel):
    """Beam line data model."""

    id: Annotated[int, Field(..., description="Auto-generated unique beam line ID")]
    name: Annotated[str, Field(..., description="Beam line name")]
    description: Annotated[
        str | None,
        Field(None, description="Beam line description"),
    ] = None


class LinksModel(BaseModel):
    """Links model for related resources."""

    line_items: Annotated[
        str,
        Field(
            ...,
            description="URL pointing to related line item resources",
        ),
    ]


class BeamLineDetailResponse(BaseModel):
    """Response model for retrieving a specific beam line with links."""

    links: Annotated[LinksModel, Field(..., description="Related resource links")]
    data: Annotated[BeamLineData, Field(..., description="Beam line details")]


class BeamLineListResponse(BaseModel):
    """Response model for listing beam lines with pagination."""

    page: Annotated[int, Field(..., description="Current page number")]
    per_page: Annotated[int, Field(..., description="Items per page")]
    total: Annotated[int, Field(..., description="Total number of items")]
    data: Annotated[
        list[BeamLineData],
        Field(..., description="List of beam line items"),
    ]


# Line item models
class LineItemKind(str, Enum):
    """Allowed line item kinds."""

    DIAGNOSTIC = "Diagnostic"
    ES_TRIPLET = "ES_Triplet"
    ES_STEERER = "ES_Steerer"
    ES_DIPOLE = "ES_Dipole"
    ES_QUADRUPOLE = "ES_Quadrupole"
    ES_MULTIPOLE = "ES_Multipole"
    MG_TRIPLET = "MG_Triplet"
    MG_STEERER = "MG_Steerer"
    MG_LENS = "MG_Lens"
    VALVE_GATE = "Valve_Gate"


class LineItemStatus(IntEnum):
    """Allowed line item statuses."""

    ENABLED = 0
    DISABLED = 1
    MAINTENANCE = 2


class AdjacentPosition(str, Enum):
    """Allowed adjacent line item positions."""

    PREVIOUS = "Previous"
    NEXT = "Next"
    DUAL = "Dual"


LINE_ITEM_KIND_LOOKUP = {item.value.lower(): item for item in LineItemKind}
ADJ_POS_LOOKUP = {item.value.lower(): item for item in AdjacentPosition}


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


class LineItemAdjacentsUpdate(BaseModel):
    """Request model for adding adjacent line items."""

    items: Annotated[
        list[LineItemAdjacent],
        Field(..., min_length=1, description="Line items to connect as adjacents"),
    ]


class LineItemCreate(BaseModel):
    """Request model for creating a new line item."""

    name: Annotated[NonEmptyStr, Field(..., description="Unique name")]
    description: Annotated[
        str | None,
        Field(None, description="Optional item description"),
    ] = None
    kind: Annotated[
        LineItemKind,
        Field(..., description="Line item kind"),
    ]
    status: Annotated[
        LineItemStatus,
        Field(default=LineItemStatus.ENABLED, description="Line item status"),
    ]
    adjacents: Annotated[
        list[LineItemAdjacent],
        Field(default_factory=list),
    ]
    connections: Annotated[
        list[int],
        Field(default_factory=list),
    ]

    @field_validator("kind", mode="before")
    @classmethod
    def validate_kind(cls, value: str | LineItemKind) -> LineItemKind:
        if isinstance(value, LineItemKind):
            return value
        if not isinstance(value, str):
            allowed = ", ".join(item.value for item in LineItemKind)
            raise ValueError(f"kind must be one of: {allowed}")
        normalized = LINE_ITEM_KIND_LOOKUP.get(value.lower())
        if normalized is None:
            allowed = ", ".join(item.value for item in LineItemKind)
            raise ValueError(f"kind must be one of: {allowed}")
        return normalized


class LineItemUpdate(BaseModel):
    """Request model for updating a line item."""

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


class LineItemCreateResponse(BaseModel):
    """Response model for creating a new line item."""

    id: Annotated[int, Field(..., description="Auto-generated item ID")]


class LineItemData(BaseModel):
    """Line item data model."""

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
    """Line item detail data model."""

    kind: Annotated[LineItemKind, Field(..., description="Line item kind")]
    status: Annotated[LineItemStatus, Field(..., description="Line item status")]


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


class LineItemAdjacentData(BaseModel):
    """Adjacent line item data model."""

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


# Non-line item models
class ItemKind(str, Enum):
    """Allowed non-line item kinds."""

    MTBX = "MTBX"
    RACK = "Rack"
    BACCO = "BACCO"
    PRIMARY_PUMP = "Primary_Pump"
    TURBOMOLECULAR_PUMP = "Turbomolecular_Pump"
    FLANGE = "Flange"
    LINE = "Line"
    BOX = "Box"


ITEM_KIND_LOOKUP = {item.value.lower(): item for item in ItemKind}


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
    kind: Annotated[ItemKind, Field(..., description="Item kind")]
    status: Annotated[
        ItemStatus,
        Field(default=ItemStatus.ACTIVE, description="Item status"),
    ]
    connections: Annotated[
        list[int],
        Field(default_factory=list, description="IDs of items to connect to"),
    ]

    @field_validator("kind", mode="before")
    @classmethod
    def validate_kind(cls, value: str | ItemKind) -> ItemKind:
        if isinstance(value, ItemKind):
            return value
        if not isinstance(value, str):
            allowed = ", ".join(item.value for item in ItemKind)
            raise ValueError(f"kind must be one of: {allowed}")
        normalized = ITEM_KIND_LOOKUP.get(value.lower())
        if normalized is None:
            allowed = ", ".join(item.value for item in ItemKind)
            raise ValueError(f"kind must be one of: {allowed}")
        return normalized


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


class ItemCreateResponse(BaseModel):
    """Response model for creating a new non-line item."""

    id: Annotated[int, Field(..., description="Auto-generated item ID")]


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

    kind: Annotated[ItemKind, Field(..., description="Item kind")]
    status: Annotated[ItemStatus, Field(..., description="Item status")]


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


# Line item connections models
class LineItemConnectionData(BaseModel):
    """Connected non-line item data model."""

    id: Annotated[int, Field(..., description="Auto-generated unique item ID")]
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


class LineItemConnectionsDelete(BaseModel):
    """Request model for disconnecting non-line items from a line item."""

    items: Annotated[
        list[int],
        Field(..., min_length=1, description="List of non-line item IDs to disconnect"),
    ]


class ItemConnectionsUpdate(BaseModel):
    """Request model for adding connections to a non-line item."""

    items: Annotated[
        list[int],
        Field(..., min_length=1, description="List of item IDs to connect"),
    ]


class LineItemConnectionsUpdate(BaseModel):
    """Request model for adding non-line item connections to a line item."""

    items: Annotated[
        list[int],
        Field(..., min_length=1, description="List of non-line item IDs to connect"),
    ]


class ItemConnectionData(BaseModel):
    """Connected item data model (line or non-line item)."""

    id: Annotated[int, Field(..., description="Auto-generated unique item ID")]
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
        Field(..., description="List of connected line or non-line items"),
    ]


class ItemConnectionsDelete(BaseModel):
    """Request model for disconnecting items from a non-line item."""

    items: Annotated[
        list[int],
        Field(..., min_length=1, description="List of item IDs to disconnect"),
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
