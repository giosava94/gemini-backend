"""Pydantic schemas for the ItemKind resource."""

from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import NonEmptyStr


class ItemKindCreate(BaseModel):
    """Request model for registering an item kind."""

    name: Annotated[NonEmptyStr, Field(..., description="Unique kind label")]


class ItemKindData(BaseModel):
    """Response model for one item kind."""

    name: Annotated[str, Field(..., description="Kind label")]


class ItemKindListResponse(BaseModel):
    """Response model for the complete item-kind vocabulary."""

    total: Annotated[int, Field(..., description="Total number of available kinds")]
    data: Annotated[
        list[ItemKindData], Field(..., description="List of item kind labels")
    ]
