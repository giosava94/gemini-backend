from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.db import exists_any_name, run_query
from app.dependencies import get_driver, get_logger
from app.schemas import (
    LINE_ITEM_KIND_LOOKUP,
    LineItemAdjacent,
    LineItemCreate,
    LineItemCreateResponse,
    LineItemData,
    LineItemDetailData,
    LineItemDetailResponse,
    LineItemListResponse,
    LineItemStatus,
    LineItemUpdate,
)

router = APIRouter(
    prefix="/api/v1/beam-lines/{beam_id}/line-items",
    tags=["line-items"],
)


def _line_item_ids_exist(driver: Driver, ids: list[int]) -> bool:
    """Return True if every distinct ID in *ids* belongs to an existing LineItem node."""
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
    """Return True if *payload* contains two adjacents with the same (position, index) key."""
    return _has_duplicate_adjacent_index_in_items(payload.adjacents)


def _has_duplicate_adjacent_index_in_items(items: list[LineItemAdjacent]) -> bool:
    """Return True if *items* contains two entries sharing the same (position, index) pair."""
    seen: set[tuple[str, int]] = set()
    for adjacent in items:
        if adjacent.index is None:
            continue
        key = (adjacent.position.value, adjacent.index)
        if key in seen:
            return True
        seen.add(key)
    return False


def _beam_line_exists(driver: Driver, beam_id: int) -> bool:
    """Return True if a BeamLine node with *beam_id* exists in the database."""
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
    """Create a new line item under a beam line.

    Raises ``404`` when the beam line does not exist.  Raises ``409`` when a
    node with the same name already exists.  Raises ``400`` when the adjacents
    list contains duplicate ``(position, index)`` pairs.  Raises ``404`` when
    any adjacent or connection ID does not exist.

    Example request body::

        {
            "name": "QD01",
            "kind": "ES_Quadrupole",
            "status": 0,
            "adjacents": [{"id": 5, "position": "Previous", "index": 0}],
            "connections": []
        }

    Example response::

        {"id": 12}
    """
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
        "kind: $kind, status: $status, labels: $labels"
        "}) "
        "CREATE (beam)-[:HAS_LINE_ITEM]->(li) "
        "WITH li "
        "CALL (li) { "
        "UNWIND $adjacents AS adjacent "
        "MATCH (target:LineItem {id: adjacent.id}) "
        "FOREACH (_ IN CASE WHEN adjacent.position IN ['Previous', 'Dual'] THEN [1] ELSE [] END | "
        "  CREATE (li)-[:PREVIOUS {index: adjacent.index}]->(target) "
        "  CREATE (target)-[:NEXT {index: adjacent.index}]->(li) "
        ") "
        "FOREACH (_ IN CASE WHEN adjacent.position IN ['Next', 'Dual'] THEN [1] ELSE [] END | "
        "  CREATE (li)-[:NEXT {index: adjacent.index}]->(target) "
        "  CREATE (target)-[:PREVIOUS {index: adjacent.index}]->(li) "
        ") "
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
            "labels": payload.labels,
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
    """List line items for a beam line with optional filtering, sorting, and pagination.

    :param beam_id: ID of the parent beam line.
    :param page: 1-based page number.
    :param per_page: Number of results per page (1–100).
    :param sort: Optional sort keys; accepted values are ``"name"`` and ``"kind"``.
    :param name: Optional case-insensitive substring filter on the item name.
    :param kind: Optional case-insensitive kind filter (e.g. ``"diagnostic"``).
    :param status: Optional status filter using :class:`LineItemStatus` values.

    Raises ``404`` when the beam line does not exist.  Raises ``422`` for
    unsupported sort keys or unrecognised kind values.

    Example: ``GET /api/v1/beam-lines/1/line-items?page=1&per_page=10&kind=diagnostic``
    """
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
    """Retrieve a specific line item under a beam line.

    Returns the item data along with ``links`` pointing to the adjacents and
    connections sub-resources.  Raises ``404`` when either the beam line or
    the line item does not exist.
    """
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
        labels=item.get("labels", []),
    )
    return {"links": links, "data": data}


@router.patch("/{item_id}", status_code=204)
def patch_line_item(
    beam_id: int,
    item_id: int,
    payload: LineItemUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Partially update a line item's name, description, and/or status.

    Only the fields present in *payload* are changed; omitted fields are left
    untouched.  Returns ``204 No Content`` on success.  Raises ``404`` when
    the beam line or item does not exist, and ``409`` when the new name is
    already taken.
    """
    logger.info(f"Updating line item with ID: {item_id} for beam line {beam_id}")
    if payload.name and exists_any_name(driver, payload.name, exclude_id=item_id):
        raise HTTPException(
            status_code=409,
            detail="An item with the same name already exists",
        )

    update_clauses: list[str] = []
    parameters: dict[str, object] = {"beam_id": beam_id, "id": item_id}
    if payload.name is not None:
        update_clauses.append("li.name = $name")
        parameters["name"] = payload.name
    if payload.description is not None:
        update_clauses.append("li.description = $description")
        parameters["description"] = payload.description
    if payload.status is not None:
        update_clauses.append("li.status = $status")
        parameters["status"] = payload.status.value
    if payload.kind is not None:
        update_clauses.append("li.kind = $kind")
        parameters["kind"] = payload.kind.value
    if payload.labels is not None:
        update_clauses.append("li.labels = $labels")
        parameters["labels"] = payload.labels

    if not update_clauses:
        return None

    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(li:LineItem {id: $id}) "
        f"SET {', '.join(update_clauses)} "
        "RETURN li.id AS id"
    )
    records = run_query(driver, query, parameters)
    if not records:
        raise HTTPException(
            status_code=404,
            detail="Beam line or target item does not exist",
        )
    return None


@router.delete("/{item_id}", status_code=204)
def delete_line_item(
    beam_id: int,
    item_id: int,
    force: Annotated[bool, Query(...)] = False,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Delete a line item under a beam line by its ID.

    Returns ``204 No Content`` on success.  Raises ``404`` when the beam line
    does not exist.  Raises ``409`` when the item still has PREVIOUS, NEXT, or
    CONNECTED_TO relationships and *force* is ``False``; pass ``?force=true``
    to detach-delete the node together with all its relationships.  Returns
    ``204`` silently when the item itself does not exist.
    """
    logger.info(
        f"Deleting line item with ID: {item_id} for beam line {beam_id}, force: {force}"
    )
    if not _beam_line_exists(driver, beam_id):
        raise HTTPException(status_code=404, detail="Beam line does not exist")

    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "OPTIONAL MATCH (li)-[outgoing]-(:LineItem) "
        "WITH li, [rel IN collect(outgoing) "
        "WHERE type(rel) IN ['PREVIOUS', 'NEXT', 'CONNECTED_TO']] AS links "
        "RETURN li.id AS id, size(links) AS linked_count"
    )
    records = run_query(driver, query, {"beam_id": beam_id, "id": item_id})
    if not records:
        return None

    linked_count = records[0]["linked_count"]
    if linked_count and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                "Can't delete an item with a previous or next item; "
                "set force to true to override"
            ),
        )

    run_query(
        driver,
        (
            "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
            "(li:LineItem {id: $id}) "
            "DETACH DELETE li"
        ),
        {"beam_id": beam_id, "id": item_id},
    )
    return None
