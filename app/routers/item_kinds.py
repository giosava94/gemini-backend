"""REST endpoints for managing the ItemKind controlled vocabulary."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver

from app.cruds.item_kinds import (
    create_item_kind,
    delete_item_kind,
    get_all_item_kinds,
    item_kind_exists,
    item_kind_in_use,
)
from app.dependencies import get_driver, get_logger
from app.schemas.item_kinds import ItemKindCreate, ItemKindListResponse

router = APIRouter(prefix="/api/v1/item-kinds", tags=["item-kinds"])


@router.post("", status_code=201)
def create_kind(
    payload: ItemKindCreate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Register a new item kind."""
    logger.info(f"Creating item kind: {payload.name}")

    if item_kind_exists(driver, payload.name):
        raise HTTPException(
            status_code=409, detail=f"Item kind '{payload.name}' already exists"
        )

    records = create_item_kind(driver, payload.name)
    if not records:
        raise HTTPException(status_code=500, detail="Failed to create item kind")

    return {"name": records[0]["name"]}


@router.get("", response_model=ItemKindListResponse)
def list_kinds(
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Return all available item kinds sorted alphabetically."""
    logger.info("Listing all item kinds")
    data = get_all_item_kinds(driver)
    return {"total": len(data), "data": data}


@router.delete("/{name}", status_code=204)
def delete_kind(
    name: str,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Delete an unused item kind by its exact name."""
    logger.info(f"Deleting item kind: {name}")

    if not item_kind_exists(driver, name):
        return None

    if item_kind_in_use(driver, name):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Item kind '{name}' is still in use by one or more items; "
                "reassign or delete those items first"
            ),
        )

    delete_item_kind(driver, name)
    return None
