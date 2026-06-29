from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.db import exists_any_name, run_query
from app.dependencies import get_driver, get_logger
from app.schemas import (
    LINE_ITEM_KIND_LOOKUP,
    LineItemCreate,
    LineItemCreateResponse,
    LineItemData,
    LineItemDetailData,
    LineItemDetailResponse,
    LineItemListResponse,
    LineItemStatus,
)

router = APIRouter(
    prefix="/api/v1/beam-lines/{beam_id}/line-items",
    tags=["line-items"],
)


def _line_item_ids_exist(driver: Driver, ids: list[int]) -> bool:
    """Return whether every distinct line item ID exists."""
    distinct_ids = list(set(ids))
    if not distinct_ids:
        return True
    query = (
        "MATCH (li:LineItem) "
        "WHERE li.id IN $ids "
        "RETURN count(DISTINCT li.id) = size($ids) AS all_exist"
    )
    records = run_query(driver, query, {"ids": distinct_ids})
    return bool(records and records[0]["all_exist"])


def _has_duplicate_adjacent_index(payload: LineItemCreate) -> bool:
    seen: set[tuple[str, int]] = set()
    for adjacent in payload.adjacents:
        if adjacent.index is None:
            continue
        key = (adjacent.position, adjacent.index)
        if key in seen:
            return True
        seen.add(key)
    return False


def _beam_line_exists(driver: Driver, beam_id: int) -> bool:
    records = run_query(
        driver,
        "MATCH (b:BeamLine {id: $id}) RETURN b.id AS id",
        {"id": beam_id},
    )
    return bool(records)


@router.post("", status_code=201, response_model=LineItemCreateResponse)
def create_line_item(
    beam_id: int,
    payload: LineItemCreate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Create a new line item under a beam line."""
    logger.info(f"Creating line item with name: {payload.name} for beam line {beam_id}")
    beam_records = run_query(
        driver,
        "MATCH (b:BeamLine {id: $id}) RETURN b.id AS id",
        {"id": beam_id},
    )
    if not beam_records:
        raise HTTPException(status_code=404, detail="Beam line does not exist")

    if exists_any_name(driver, payload.name):
        raise HTTPException(
            status_code=409,
            detail="Item with this name already exists",
        )

    if _has_duplicate_adjacent_index(payload):
        raise HTTPException(
            status_code=400,
            detail="Adjacent item with the same index already exists",
        )

    adjacent_ids = [adjacent.id for adjacent in payload.adjacents]
    connection_ids = payload.connections
    if not _line_item_ids_exist(driver, adjacent_ids + connection_ids):
        raise HTTPException(
            status_code=404,
            detail="Previous, next or connected item does not exist",
        )

    adjacents = [
        {
            "id": adjacent.id,
            "position": adjacent.position.value,
            "index": adjacent.index,
        }
        for adjacent in payload.adjacents
    ]
    query = (
        "MATCH (beam:BeamLine {id: $beam_id}) "
        "MERGE (c:Counter {name: 'lineitem'}) "
        "ON CREATE SET c.value = 0 "
        "SET c.value = c.value + 1 "
        "WITH beam, c.value AS nextId "
        "CREATE (li:LineItem {"
        "id: nextId, name: $name, description: $description, "
        "kind: $kind, status: $status"
        "}) "
        "CREATE (beam)-[:HAS_LINE_ITEM]->(li) "
        "WITH li "
        "CALL (li) { "
        "UNWIND $adjacents AS adjacent "
        "MATCH (target:LineItem {id: adjacent.id}) "
        "CREATE (li)-[:ADJACENT_TO {"
        "position: adjacent.position, index: adjacent.index"
        "}]->(target) "
        "RETURN count(*) AS adjacent_count "
        "} "
        "CALL (li) { "
        "UNWIND $connections AS connected_id "
        "MATCH (target:LineItem {id: connected_id}) "
        "CREATE (li)-[:CONNECTED_TO]->(target) "
        "RETURN count(*) AS connection_count "
        "} "
        "RETURN li.id AS id"
    )
    records = run_query(
        driver,
        query,
        {
            "beam_id": beam_id,
            "name": payload.name,
            "description": payload.description,
            "kind": payload.kind.value,
            "status": payload.status.value,
            "adjacents": adjacents,
            "connections": list(set(connection_ids)),
        },
    )
    if not records:
        raise HTTPException(status_code=500, detail="Failed to create line item")
    return {"id": records[0]["id"]}


@router.get("", response_model=LineItemListResponse)
def list_line_items(
    beam_id: int,
    page: Annotated[int, Query(..., ge=1)] = 1,
    per_page: Annotated[int, Query(..., ge=1, le=100)] = 10,
    sort: Annotated[list[str] | None, Query(...)] = None,
    name: Annotated[str | None, Query(...)] = None,
    kind: Annotated[str | None, Query(...)] = None,
    status: Annotated[LineItemStatus | None, Query(...)] = None,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """List line items for a beam line with pagination and filtering."""
    logger.info(
        "Listing line items - "
        f"beam_id: {beam_id}, page: {page}, per_page: {per_page}, "
        f"name filter: {name}, kind filter: {kind}, "
        f"status: {status.value if status else None}"
    )
    if not _beam_line_exists(driver, beam_id):
        raise HTTPException(status_code=404, detail="Beam line does not exist")

    if sort:
        for key in sort:
            if key not in ("name", "kind"):
                raise HTTPException(status_code=422, detail=f"Invalid sort key: {key}")

    normalized_kind = None
    if kind is not None:
        normalized_kind = LINE_ITEM_KIND_LOOKUP.get(kind.lower())
        if normalized_kind is None:
            allowed = ", ".join(item.value for item in LINE_ITEM_KIND_LOOKUP.values())
            raise HTTPException(
                status_code=422,
                detail=f"Invalid kind; must be one of: {allowed}",
            )

    where_clause = (
        "WHERE ($status IS NULL OR li.status = $status) "
        "AND ($name IS NULL OR toLower(li.name) CONTAINS toLower($name)) "
        "AND ($kind IS NULL OR li.kind = $kind)"
    )
    parameters = {
        "beam_id": beam_id,
        "status": status.value if status else None,
        "name": name,
        "kind": normalized_kind.value if normalized_kind else None,
    }
    count_query = (
        "MATCH (b:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem) "
        f"{where_clause} "
        "RETURN count(li) AS total"
    )
    total_records = run_query(driver, count_query, parameters)
    total = total_records[0]["total"] if total_records else 0

    sort_clauses = []
    if sort:
        for key in sort:
            if key == "name":
                sort_clauses.append("toLower(li.name)")
            elif key == "kind":
                sort_clauses.append("li.kind")
    order_clause = f"ORDER BY {', '.join(sort_clauses)}" if sort_clauses else ""
    query = (
        "MATCH (b:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem) "
        f"{where_clause} "
        f"RETURN li {order_clause} SKIP $skip LIMIT $limit"
    )
    skip = (page - 1) * per_page
    records = run_query(
        driver,
        query,
        {
            **parameters,
            "skip": skip,
            "limit": per_page,
        },
    )
    data = [
        LineItemData(
            id=record["li"]["id"],
            name=record["li"]["name"],
            description=record["li"].get("description"),
        )
        for record in records
    ]
    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.get("/{item_id}", response_model=LineItemDetailResponse)
def get_line_item(
    beam_id: int,
    item_id: int,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Retrieve a specific line item under a beam line."""
    logger.info(f"Fetching line item with ID: {item_id} for beam line {beam_id}")
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "RETURN li"
    )
    records = run_query(driver, query, {"beam_id": beam_id, "id": item_id})
    if not records:
        raise HTTPException(
            status_code=404,
            detail="Beam line or target item does not exist",
        )

    item = records[0]["li"]
    base_url = f"/api/v1/beam-lines/{beam_id}/line-items/{item_id}"
    links = {
        "adjacents": f"{base_url}/adjacents",
        "connections": f"{base_url}/connections",
    }
    data = LineItemDetailData(
        id=item["id"],
        name=item["name"],
        description=item.get("description"),
        kind=item["kind"],
        status=item["status"],
    )
    return {"links": links, "data": data}
