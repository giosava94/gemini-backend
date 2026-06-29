from typing import Annotated
from pydantic import BaseModel, Field
from app.schemas.common import NonEmptyStr


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
    """Links model for related beam line resources."""

    line_items: Annotated[
        str,
        Field(..., description="URL pointing to related line item resources"),
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
        Field(..., description="List of beam lines"),
    ]
