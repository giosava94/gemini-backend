from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.db import run_query
from app.dependencies import get_driver, get_logger
from app.schemas import (
    ItemConnectionData,
    ItemConnectionsDelete,
    ItemConnectionsListResponse,
    ItemConnectionsUpdate,
    ItemLineItemConnectionData,
    ItemLineItemConnectionsListResponse,
)

router = APIRouter(
    prefix="/api/v1/items",
    tags=["item-connections"],
)


@router.put("/{item_id}/connections", status_code=201)
def put_item_connections(
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
            status_code=400,
            detail="An item cannot be connected to itself",
        )

    existence_records = run_query(
        driver,
        "MATCH (i:Item {id: $id}) RETURN i.id AS id",
        {"id": item_id},
    )
    if not existence_records:
        raise HTTPException(
            status_code=404,
            detail="Current item or at least one of the linked items do not exist",
        )

    target_records = run_query(
        driver,
        (
            "UNWIND $ids AS id "
            "OPTIONAL MATCH (n) WHERE (n:Item) AND n.id = id "
            "RETURN count(n) = size($ids) AS all_exist"
        ),
        {"ids": target_ids},
    )
    if not target_records or not target_records[0]["all_exist"]:
        raise HTTPException(
            status_code=404,
            detail="Current item or at least one of the linked items do not exist",
        )

    run_query(
        driver,
        (
            "MATCH (current:Item {id: $id}) "
            "UNWIND $connections AS connection "
            "MATCH (target:Item {id: connection.id}) "
            "MERGE (current)-[rel:CONNECTED_TO]-(target) "
            "SET rel = connection.properties"
        ),
        {"id": item_id, "connections": connections},
    )
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

    existence_records = run_query(
        driver,
        "MATCH (i:Item {id: $id}) RETURN i.id AS id",
        {"id": item_id},
    )
    if not existence_records:
        raise HTTPException(status_code=404, detail="Current item does not exist")

    count_query = (
        "MATCH (i:Item {id: $id})-[:CONNECTED_TO]-(conn) "
        "WHERE conn:Item "
        "RETURN count(conn) AS total"
    )
    total_records = run_query(driver, count_query, {"id": item_id})
    total = total_records[0]["total"] if total_records else 0

    skip = (page - 1) * per_page
    data_query = (
        "MATCH (i:Item {id: $id})-[rel:CONNECTED_TO]-(conn:Item) "
        "RETURN conn, properties(rel) AS rel_props "
        "SKIP $skip LIMIT $limit"
    )
    records = run_query(
        driver,
        data_query,
        {"id": item_id, "skip": skip, "limit": per_page},
    )
    data = [
        ItemConnectionData(
            id=record["conn"]["id"],
            name=record["conn"]["name"],
            description=record["conn"].get("description"),
            properties=record.get("rel_props"),
            link=f"/api/v1/items/{record['conn']['id']}",
        )
        for record in records
    ]
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

    if len(payload.items) != len(set(payload.items)):
        raise HTTPException(status_code=400, detail="Duplicated items in the list")

    existence_records = run_query(
        driver,
        "MATCH (i:Item {id: $id}) RETURN i.id AS id",
        {"id": item_id},
    )
    if not existence_records:
        raise HTTPException(status_code=404, detail="Current item does not exist")

    run_query(
        driver,
        (
            "MATCH (i:Item {id: $id})-[rel:CONNECTED_TO]-(conn:Item) "
            "WHERE conn.id IN $target_ids "
            "DELETE rel"
        ),
        {"id": item_id, "target_ids": payload.items},
    )
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

    existence_records = run_query(
        driver,
        "MATCH (i:Item {id: $id}) RETURN i.id AS id",
        {"id": item_id},
    )
    if not existence_records:
        raise HTTPException(status_code=404, detail="Current item does not exist")

    count_query = (
        "MATCH (li:LineItem)-[:CONNECTED_TO]->(i:Item {id: $id}) "
        "RETURN count(li) AS total"
    )
    total_records = run_query(driver, count_query, {"id": item_id})
    total = total_records[0]["total"] if total_records else 0

    skip = (page - 1) * per_page
    data_query = (
        "MATCH (b:BeamLine)-[:HAS_LINE_ITEM]->(li:LineItem)-[:CONNECTED_TO]->(i:Item {id: $id}) "
        "RETURN li, b.id AS beam_id "
        "SKIP $skip LIMIT $limit"
    )
    records = run_query(
        driver,
        data_query,
        {"id": item_id, "skip": skip, "limit": per_page},
    )
    data = [
        ItemLineItemConnectionData(
            id=record["li"]["id"],
            name=record["li"]["name"],
            description=record["li"].get("description"),
            link=(
                f"/api/v1/beam-lines/{record['beam_id']}"
                f"/line-items/{record['li']['id']}"
            ),
        )
        for record in records
    ]
    return {"page": page, "per_page": per_page, "total": total, "data": data}
