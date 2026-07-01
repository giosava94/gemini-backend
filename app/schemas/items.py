from enum import Enum, IntEnum
from typing import Annotated
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import NonEmptyStr


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


class ItemStatus(IntEnum):
    """Allowed non-line item statuses."""

    ACTIVE = 0
    UNMOUNTED = 1
    MAINTENANCE = 2
    DISMITTED = 3


ITEM_KIND_LOOKUP = {item.value.lower(): item for item in ItemKind}


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
    labels: Annotated[
        list[str],
        Field(default_factory=list, description="Optional list of labels"),
    ]

    @field_validator("kind", mode="before")
    @classmethod
    def validate_kind(cls, value: str | ItemKind) -> ItemKind:
        """Normalise *value* to an :class:`ItemKind` member, case-insensitively."""
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
    labels: Annotated[
        list[str] | None,
        Field(None, description="Updated list of labels"),
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
    labels: Annotated[
        list[str],
        Field(default_factory=list, description="List of labels"),
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
