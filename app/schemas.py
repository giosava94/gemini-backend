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
