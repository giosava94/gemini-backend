from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.cruds.items import conn_items_exist
from app.cruds.line_item_connections import (
    beam_line_and_line_item_exist,
    disconnect_line_item_connected_records,
    get_line_item_connections,
    get_total_line_item_connections,
    update_line_item_connected_records,
)
from app.dependencies import get_driver, get_logger
from app.schemas.line_item_connections import (
    LineItemConnectionsDelete,
    LineItemConnectionsListResponse,
    LineItemConnectionsUpdate,
)


def check_beam_line_and_line_item_exist(
    beam_id: int, item_id: int, driver: Driver = Depends(get_driver)
):
    if not beam_line_and_line_item_exist(driver, beam_id, item_id):
        raise HTTPException(
            status_code=404,
            detail="Beam line or current line item do not exist",
        )


router = APIRouter(
    prefix="/api/v1/beam-lines/{beam_id}/line-items/{item_id}/connections",
    tags=["line-item-connections"],
    dependencies=[Depends(check_beam_line_and_line_item_exist)],
)


@router.get("", response_model=LineItemConnectionsListResponse)
def list_line_item_connections(
    beam_id: int,
    item_id: int,
    page: Annotated[int, Query(..., ge=1)] = 1,
    per_page: Annotated[int, Query(..., ge=1, le=100)] = 10,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Retrieve the list of connected non-line items of the current line item."""
    logger.info(
        f"Listing connections for line item {item_id} on beam line {beam_id} - "
        f"page: {page}, per_page: {per_page}"
    )

    total = get_total_line_item_connections(driver, beam_id, item_id)
    data = get_line_item_connections(driver, beam_id, item_id)

    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.put("", status_code=201)
def put_line_item_connections(
    beam_id: int,
    item_id: int,
    payload: LineItemConnectionsUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Add one or multiple non-line items to the current line item."""
    logger.info(
        f"Adding connections to line item {item_id} on beam line {beam_id}: "
        f"{[item.id for item in payload.items]}"
    )

    connections = [
        {"id": item.id, "properties": item.properties} for item in payload.items
    ]
    target_ids = [connection["id"] for connection in connections]

    if len(target_ids) != len(set(target_ids)):
        raise HTTPException(status_code=400, detail="Duplicated items in the list")

    # Verify all target IDs exist as Item nodes
    if not conn_items_exist(driver, target_ids):
        raise HTTPException(
            status_code=404,
            detail="Beam line, current item or at least one of the linked items do not exist",
        )

    update_line_item_connected_records(driver, beam_id, item_id, connections)

    return None


@router.delete("", status_code=204)
def delete_line_item_connections(
    beam_id: int,
    item_id: int,
    payload: LineItemConnectionsDelete,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Disconnect one or multiple non-line items from the current line item."""
    logger.info(
        f"Disconnecting connections from line item {item_id} on beam line {beam_id}: "
        f"{payload.items}"
    )

    disconnect_line_item_connected_records(driver, beam_id, item_id, payload.items)

    return None
