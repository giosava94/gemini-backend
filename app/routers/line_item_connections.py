from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.db import run_query
from app.dependencies import get_driver, get_logger
from app.schemas import (
    LineItemConnectionData,
    LineItemConnectionsDelete,
    LineItemConnectionsListResponse,
    LineItemConnectionsUpdate,
)

router = APIRouter(
    prefix="/api/v1/beam-lines/{beam_id}/line-items",
    tags=["line-item-connections"],
)


@router.get("/{item_id}/connections", response_model=LineItemConnectionsListResponse)
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

    existence_records = run_query(
        driver,
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "RETURN li.id AS id",
        {"beam_id": beam_id, "id": item_id},
    )
    if not existence_records:
        raise HTTPException(
            status_code=404,
            detail="Beam line or current line item do not exist",
        )

    count_query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(li:LineItem {id: $id})-[:CONNECTED_TO]->(conn:Item) "
        "RETURN count(conn) AS total"
    )
    total_records = run_query(driver, count_query, {"beam_id": beam_id, "id": item_id})
    total = total_records[0]["total"] if total_records else 0

    skip = (page - 1) * per_page
    data_query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(li:LineItem {id: $id})-[:CONNECTED_TO]->(conn:Item) "
        "RETURN conn SKIP $skip LIMIT $limit"
    )
    records = run_query(
        driver,
        data_query,
        {"beam_id": beam_id, "id": item_id, "skip": skip, "limit": per_page},
    )
    data = [
        LineItemConnectionData(
            id=record["conn"]["id"],
            name=record["conn"]["name"],
            description=record["conn"].get("description"),
            link=f"/api/v1/items/{record['conn']['id']}",
        )
        for record in records
    ]
    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.delete("/{item_id}/connections", status_code=204)
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

    if len(payload.items) != len(set(payload.items)):
        raise HTTPException(status_code=400, detail="Duplicated items in the list")

    existence_records = run_query(
        driver,
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "RETURN li.id AS id",
        {"beam_id": beam_id, "id": item_id},
    )
    if not existence_records:
        raise HTTPException(
            status_code=404,
            detail="Beam line or current line item do not exist",
        )

    run_query(
        driver,
        (
            "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
            "(li:LineItem {id: $id})-[rel:CONNECTED_TO]->(conn:Item) "
            "WHERE conn.id IN $target_ids "
            "DELETE rel"
        ),
        {"beam_id": beam_id, "id": item_id, "target_ids": payload.items},
    )
    return None


@router.put("/{item_id}/connections", status_code=201)
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
        f"{payload.items}"
    )

    if len(payload.items) != len(set(payload.items)):
        raise HTTPException(status_code=400, detail="Duplicated items in the list")

    # Verify beam line and current line item exist
    existence_records = run_query(
        driver,
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "RETURN li.id AS id",
        {"beam_id": beam_id, "id": item_id},
    )
    if not existence_records:
        raise HTTPException(
            status_code=404,
            detail="Beam line, current item or at least one of the linked items do not exist",
        )

    # Verify all target IDs exist as Item nodes
    target_ids = list(set(payload.items))
    target_records = run_query(
        driver,
        (
            "UNWIND $ids AS id "
            "OPTIONAL MATCH (n:Item {id: id}) "
            "RETURN count(n) = size($ids) AS all_exist"
        ),
        {"ids": target_ids},
    )
    if not target_records or not target_records[0]["all_exist"]:
        raise HTTPException(
            status_code=404,
            detail="Beam line, current item or at least one of the linked items do not exist",
        )

    # MERGE so re-connecting an already connected item is a no-op
    run_query(
        driver,
        (
            "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
            "(li:LineItem {id: $id}) "
            "UNWIND $target_ids AS target_id "
            "MATCH (target:Item {id: target_id}) "
            "MERGE (li)-[:CONNECTED_TO]->(target)"
        ),
        {"beam_id": beam_id, "id": item_id, "target_ids": target_ids},
    )
    return None
