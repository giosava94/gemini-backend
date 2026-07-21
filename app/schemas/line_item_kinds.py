"""Pydantic schemas for the LineItemKind resource.

A ``LineItemKind`` node in Neo4j stores the allowed kind values for
:class:`~app.schemas.line_items.LineItemCreate` and
:class:`~app.schemas.line_items.LineItemUpdate`.  This schema module defines
the request/response models used by the ``/api/v1/line-item-kinds`` router.
"""

from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import NonEmptyStr


class LineItemKindCreate(BaseModel):
    """Request model for creating a new line item kind.

    :param name: Human-readable label for the kind (e.g. ``"ES Quadrupole"``).
        Must be non-empty and unique across all ``LineItemKind`` nodes.
    """

    name: Annotated[NonEmptyStr, Field(..., description="Unique kind label")]


class LineItemKindData(BaseModel):
    """Response data model for a single line item kind.

    :param name: The kind label as stored in the database.
    """

    name: Annotated[str, Field(..., description="Kind label")]


class LineItemKindListResponse(BaseModel):
    """Response model for the full list of available line item kinds.

    Kinds are a small controlled vocabulary so no pagination is applied.

    :param total: Total count of available kinds.
    :param data: Alphabetically ordered list of kind data objects.
    """

    total: Annotated[int, Field(..., description="Total number of available kinds")]
    data: Annotated[
        list[LineItemKindData],
        Field(..., description="List of line item kind labels"),
    ]
