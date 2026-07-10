from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.cruds.item_connections import (
    connect_item_records,
    disconnect_item_records,
    get_connected_items,
    get_connected_line_items,
    get_total_connected_items,
    get_total_connected_line_items,
    item_exists,
)
from app.cruds.items import conn_items_exist
from app.dependencies import get_driver, get_logger
from app.schemas.item_connections import (
    ItemConnectionsDelete,
    ItemConnectionsListResponse,
    ItemConnectionsUpdate,
    ItemLineItemConnectionsListResponse,
)

router = APIRouter(prefix="/api/v1/items", tags=["item-connections"])


@router.put("/{item_id}/connections", status_code=201)
async def put_item_connections(
    item_id: int,
    payload: ItemConnectionsUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Add one or multiple non-line items to the current non-line item."""
    logger.info(
        f"Adding connections to item {item_id}: {[item.id for item in payload.items]}"
    )

    connections = [
        {"id": item.id, "properties": item.properties} for item in payload.items
    ]
    target_ids = [connection["id"] for connection in connections]

    if len(target_ids) != len(set(target_ids)):
        raise HTTPException(status_code=400, detail="Duplicated items in the list")

    if item_id in target_ids:
        raise HTTPException(
            status_code=400, detail="An item cannot be connected to itself"
        )

    if not conn_items_exist(driver, [item_id, *target_ids]):
        raise HTTPException(
            status_code=404,
            detail="Current item or at least one of the linked items do not exist",
        )

    connect_item_records(driver, item_id, connections)

    return None


@router.get("/{item_id}/connections", response_model=ItemConnectionsListResponse)
def list_item_connections(
    item_id: int,
    page: Annotated[int, Query(..., ge=1)] = 1,
    per_page: Annotated[int, Query(..., ge=1, le=100)] = 10,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Retrieve the list of connected non-line items of the current item."""
    logger.info(
        f"Listing connections for item {item_id} - page: {page}, per_page: {per_page}"
    )

    if not item_exists(driver, item_id):
        raise HTTPException(status_code=404, detail="Current item does not exist")

    total = get_total_connected_items(driver, item_id)
    data = get_connected_items(driver, item_id, page=page, per_page=per_page)

    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.delete("/{item_id}/connections", status_code=204)
def delete_item_connections(
    item_id: int,
    payload: ItemConnectionsDelete,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Disconnect one or multiple non-line items from the current item."""
    logger.info(f"Disconnecting connections from item {item_id}: {payload.items}")

    if not item_exists(driver, item_id):
        raise HTTPException(status_code=404, detail="Current item does not exist")

    disconnect_item_records(driver, item_id, payload.items)

    return None


@router.get(
    "/{item_id}/line-item-connections",
    response_model=ItemLineItemConnectionsListResponse,
)
def list_item_line_item_connections(
    item_id: int,
    page: Annotated[int, Query(..., ge=1)] = 1,
    per_page: Annotated[int, Query(..., ge=1, le=100)] = 10,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Retrieve the beam line items connected to a specific non-line item."""
    logger.info(
        f"Listing line item connections for item {item_id} - "
        f"page: {page}, per_page: {per_page}"
    )

    if not item_exists(driver, item_id):
        raise HTTPException(status_code=404, detail="Current item does not exist")

    total = get_total_connected_line_items(driver, item_id)
    data = get_connected_line_items(driver, item_id, page=page, per_page=per_page)

    return {"page": page, "per_page": per_page, "total": total, "data": data}
