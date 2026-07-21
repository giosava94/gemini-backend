"""REST endpoints for managing LineItemKind nodes.

Line item kinds form the controlled vocabulary of valid ``kind`` values for
:class:`~app.schemas.line_items.LineItemCreate` and
:class:`~app.schemas.line_items.LineItemUpdate`.  Rather than hard-coding them
as a Python enum, kinds are stored as ``LineItemKind`` nodes in Neo4j and can
be managed at runtime through the following endpoints:

- ``POST   /api/v1/line-item-kinds``         — register a new kind
- ``GET    /api/v1/line-item-kinds``         — list all available kinds
- ``DELETE /api/v1/line-item-kinds/{name}``  — remove a kind (fails when in use)

All routes depend on the shared :func:`~app.dependencies.get_driver` and
:func:`~app.dependencies.get_logger` FastAPI dependencies.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver

from app.cruds.line_item_kinds import (
    create_line_item_kind,
    delete_line_item_kind,
    get_all_line_item_kinds,
    line_item_kind_exists,
    line_item_kind_in_use,
)
from app.dependencies import get_driver, get_logger
from app.schemas.line_item_kinds import (
    LineItemKindCreate,
    LineItemKindListResponse,
)

router = APIRouter(prefix="/api/v1/line-item-kinds", tags=["line-item-kinds"])


@router.post("", status_code=201)
def create_kind(
    payload: LineItemKindCreate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Register a new line item kind.

    The kind *name* must be non-empty and unique (case-sensitive).
    Raises ``409`` when a ``LineItemKind`` node with the same name already
    exists.  Raises ``500`` when the database operation fails.

    Example request body::

        {"name": "Wien Filter"}

    Example response::

        {"name": "Wien Filter"}
    """
    logger.info(f"Creating line item kind: {payload.name}")

    if line_item_kind_exists(driver, payload.name):
        raise HTTPException(
            status_code=409,
            detail=f"Line item kind '{payload.name}' already exists",
        )

    records = create_line_item_kind(driver, payload.name)
    if not records:
        raise HTTPException(
            status_code=500,
            detail="Failed to create line item kind",
        )

    return {"name": records[0]["name"]}


@router.get("", response_model=LineItemKindListResponse)
def list_kinds(
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Return all available line item kinds, sorted alphabetically.

    Returns an empty ``data`` list when no kinds have been registered yet.

    Example response::

        {
            "total": 2,
            "data": [
                {"name": "Diagnostic"},
                {"name": "Wien Filter"}
            ]
        }
    """
    logger.info("Listing all line item kinds")

    data = get_all_line_item_kinds(driver)
    return {"total": len(data), "data": data}


@router.delete("/{name}", status_code=204)
def delete_kind(
    name: str,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Delete a line item kind by its exact name.

    Returns ``204`` when no ``LineItemKind`` node with *name* exists, making
    deletion idempotent. Raises ``409`` when the kind is still referenced by one or more
    ``LineItem`` nodes — remove or reassign those items before deleting the
    kind.

    :param name: URL-encoded kind label to delete (e.g. ``Wien%20Filter``).

    Example: ``DELETE /api/v1/line-item-kinds/Wien%20Filter``
    """
    logger.info(f"Deleting line item kind: {name}")

    if not line_item_kind_exists(driver, name):
        return None

    if line_item_kind_in_use(driver, name):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Line item kind '{name}' is still in use by one or more line items; "
                "reassign or delete those items first"
            ),
        )

    delete_line_item_kind(driver, name)
    return None
