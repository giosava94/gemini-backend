from enum import Enum, IntEnum
from typing import Annotated
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import ListIntNoDuplicates, NonEmptyStr


class LineItemKind(str, Enum):
    """Allowed line item kinds."""

    DIAGNOSTIC = "Diagnostic"
    ES_TRIPLET = "ES Triplet"
    ES_STEERER = "ES Steerer"
    ES_DIPOLE = "ES Dipole"
    ES_QUADRUPOLE = "ES Quadrupole"
    ES_MULTIPOLE = "ES Multipole"
    MG_TRIPLET = "MG Triplet"
    MG_STEERER = "MG Steerer"
    MG_DIPOLE = "MG Dipole"
    MG_SOLENOID = "MG Solenoid"
    MG_QUADRUPOLE = "MG Quadrupole"
    VALVE_GATE = "Valve Gate"
    HIGH_ENERGY_BUNCHER = "High Energy Buncher"
    LOW_ENERGY_BUNCHER = "Low Energy Buncher"
    RFQ = "Radiofrequency Quadrupole"
    CRYOSTAT = "Cryostat"
    CHARGE_BREEDER = "Charge Breeder"
    BEAM_COOLER = "Beam Cooler"
    TAPE_STATION = "Tape Station"
    ION_SOURCE = "Ion Source"
    TARGET_ION_SOURCE = "Target Ion Source"
    WIEN_FILTER = "Wien Filter"


class LineItemStatus(IntEnum):
    """Allowed line item statuses."""

    DISABLED = 0
    ENABLED = 1
    MAINTENANCE = 2


LINE_ITEM_KIND_LOOKUP = {item.value.lower(): item for item in LineItemKind}


class LineItemCreate(BaseModel):
    """Request model for creating a new line item."""

    name: Annotated[NonEmptyStr, Field(..., description="Unique name")]
    description: Annotated[
        str | None,
        Field(None, description="Optional item description"),
    ] = None
    kind: Annotated[LineItemKind, Field(..., description="Line item kind")]
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

    @field_validator("kind", mode="before")
    @classmethod
    def validate_kind(cls, value: str | LineItemKind) -> LineItemKind:
        """Normalise *value* to a :class:`LineItemKind` member, case-insensitively."""
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
    kind: Annotated[
        LineItemKind | None,
        Field(None, description="Updated line item kind"),
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
# and referenced in LineItemCreate above — resolved via forward reference + update_forward_refs
from app.schemas.line_item_adjacents import LineItemAdjacent  # noqa: E402

LineItemCreate.model_rebuild()
