from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.db import exists_any_name, run_query
from app.dependencies import get_driver, get_logger
from app.schemas import (
    ADJ_POS_LOOKUP,
    LINE_ITEM_KIND_LOOKUP,
    AdjacentPosition,
    LineItemAdjacent,
    LineItemAdjacentData,
    LineItemAdjacentsDelete,
    LineItemAdjacentsListResponse,
    LineItemAdjacentsUpdate,
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
    return _has_duplicate_adjacent_index_in_items(payload.adjacents)


def _has_duplicate_adjacent_items(items: list[LineItemAdjacent]) -> bool:
    seen: set[tuple[int, str]] = set()
    for adjacent in items:
        key = (adjacent.id, adjacent.position.value)
        if key in seen:
            return True
        seen.add(key)
    return False


def _has_duplicate_adjacent_index_in_items(items: list[LineItemAdjacent]) -> bool:
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


@router.get("/{item_id}/adjacents", response_model=LineItemAdjacentsListResponse)
def list_line_item_adjacents(
    beam_id: int,
    item_id: int,
    page: Annotated[int, Query(..., ge=1)] = 1,
    per_page: Annotated[int, Query(..., ge=1, le=100)] = 10,
    sort: Annotated[list[str] | None, Query(...)] = None,
    position: Annotated[str | None, Query(...)] = None,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Retrieve the list of adjacent items of the current line item."""
    logger.info(
        f"Listing adjacents for line item {item_id} on beam line {beam_id} - "
        f"page: {page}, per_page: {per_page}, sort: {sort}, position: {position}"
    )

    # Validate beam line and current item existence
    existence_records = run_query(
        driver,
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "RETURN li.id AS id",
        {"beam_id": beam_id, "id": item_id},
    )
    if not existence_records:
        raise HTTPException(
            status_code=404,
            detail="Beam line or current item does not exist",
        )

    # Validate sort keys
    if sort:
        for key in sort:
            if key != "position":
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid sort key: {key}. Valid values: position",
                )

    # Validate and normalise position filter
    normalized_position: AdjacentPosition | None = None
    if position is not None:
        normalized_position = ADJ_POS_LOOKUP.get(position.lower())
        if normalized_position is None:
            allowed = ", ".join(item.value for item in AdjacentPosition)
            raise HTTPException(
                status_code=422,
                detail=f"Invalid position; must be one of: {allowed}",
            )

    where_position = "WHERE ($position IS NULL OR rel_type = $position) "
    base_params: dict = {
        "beam_id": beam_id,
        "id": item_id,
        "position": normalized_position.value if normalized_position else None,
    }

    count_query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(current:LineItem {id: $id})-[rel:PREVIOUS|NEXT]->(adj:LineItem) "
        "WITH adj, "
        "  CASE type(rel) WHEN 'PREVIOUS' THEN 'Previous' ELSE 'Next' END AS rel_type, "
        "  rel.index AS index "
        f"{where_position}"
        "RETURN count(adj) AS total"
    )
    total_records = run_query(driver, count_query, base_params)
    total = total_records[0]["total"] if total_records else 0

    order_clause = "ORDER BY rel_type" if sort and "position" in sort else ""
    data_query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(current:LineItem {id: $id})-[rel:PREVIOUS|NEXT]->(adj:LineItem) "
        "WITH adj, "
        "  CASE type(rel) WHEN 'PREVIOUS' THEN 'Previous' ELSE 'Next' END AS rel_type, "
        "  rel.index AS index "
        f"{where_position}"
        f"RETURN adj, rel_type AS position, index "
        f"{order_clause} SKIP $skip LIMIT $limit"
    )
    skip = (page - 1) * per_page
    records = run_query(
        driver,
        data_query,
        {**base_params, "skip": skip, "limit": per_page},
    )
    data = [
        LineItemAdjacentData(
            id=record["adj"]["id"],
            name=record["adj"]["name"],
            description=record["adj"].get("description"),
            position=record["position"],
            index=record["index"],
            link=f"/api/v1/beam-lines/{beam_id}/line-items/{record['adj']['id']}",
        )
        for record in records
    ]
    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.put("/{item_id}/adjacents", status_code=201)
def put_line_item_adjacents(
    beam_id: int,
    item_id: int,
    payload: LineItemAdjacentsUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Add one or multiple adjacent line items to the current one."""
    logger.info(f"Adding adjacents to line item {item_id} for beam line {beam_id}")
    if _has_duplicate_adjacent_items(payload.items) or (
        _has_duplicate_adjacent_index_in_items(payload.items)
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Duplicated items in the list or adjacent item with the same "
                "index already exist"
            ),
        )

    target_ids = [item.id for item in payload.items]
    query = (
        "MATCH (beam:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(current:LineItem {id: $id}) "
        "WITH beam, current "
        "MATCH (beam)-[:HAS_LINE_ITEM]->(target:LineItem) "
        "WHERE target.id IN $target_ids "
        "RETURN count(DISTINCT target.id) = size($target_ids) AS all_targets_exist"
    )
    records = run_query(
        driver,
        query,
        {"beam_id": beam_id, "id": item_id, "target_ids": list(set(target_ids))},
    )
    if not records or not records[0]["all_targets_exist"]:
        raise HTTPException(
            status_code=404,
            detail=(
                "Beam line, current item or at least one of the linked items "
                "do not exist"
            ),
        )

    adjacents = [
        {
            "id": item.id,
            "position": item.position.value,
            "index": item.index,
        }
        for item in payload.items
    ]
    conflict_query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(current:LineItem {id: $id}) "
        "UNWIND $adjacents AS adjacent "
        "WITH current, adjacent "
        "WHERE adjacent.index IS NOT NULL "
        "OPTIONAL MATCH (current)-[rel:PREVIOUS|NEXT]->(existing:LineItem) "
        "WHERE (adjacent.position IN ['Previous', 'Dual'] AND type(rel) = 'PREVIOUS' "
        "       OR adjacent.position IN ['Next', 'Dual'] AND type(rel) = 'NEXT') "
        "AND rel.index = adjacent.index "
        "AND existing.id <> adjacent.id "
        "RETURN count(rel) > 0 AS has_conflict"
    )
    conflict_records = run_query(
        driver,
        conflict_query,
        {"beam_id": beam_id, "id": item_id, "adjacents": adjacents},
    )
    if conflict_records and conflict_records[0]["has_conflict"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Duplicated items in the list or adjacent item with the same "
                "index already exist"
            ),
        )

    create_query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(current:LineItem {id: $id}) "
        "UNWIND $adjacents AS adjacent "
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(target:LineItem {id: adjacent.id}) "
        "FOREACH (_ IN CASE WHEN adjacent.position IN ['Previous', 'Dual'] THEN [1] ELSE [] END | "
        "  MERGE (current)-[r1:PREVIOUS]->(target) ON CREATE SET r1.index = adjacent.index "
        "  MERGE (target)-[r2:NEXT]->(current) ON CREATE SET r2.index = adjacent.index "
        ") "
        "FOREACH (_ IN CASE WHEN adjacent.position IN ['Next', 'Dual'] THEN [1] ELSE [] END | "
        "  MERGE (current)-[r3:NEXT]->(target) ON CREATE SET r3.index = adjacent.index "
        "  MERGE (target)-[r4:PREVIOUS]->(current) ON CREATE SET r4.index = adjacent.index "
        ") "
        "RETURN count(target) AS linked_count"
    )
    run_query(
        driver,
        create_query,
        {"beam_id": beam_id, "id": item_id, "adjacents": adjacents},
    )
    return None


@router.delete("/{item_id}/adjacents", status_code=204)
def delete_line_item_adjacents(
    beam_id: int,
    item_id: int,
    payload: LineItemAdjacentsDelete,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Disconnect one or multiple adjacent line items from the current one."""
    logger.info(
        f"Disconnecting adjacents from line item {item_id} on beam line {beam_id}: "
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
            detail="Beam line or current item does not exist",
        )

    # Delete PREVIOUS/NEXT relationships in both directions between current and each target
    run_query(
        driver,
        (
            "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
            "(current:LineItem {id: $id}) "
            "UNWIND $target_ids AS target_id "
            "MATCH (target:LineItem {id: target_id}) "
            "OPTIONAL MATCH (current)-[r1:PREVIOUS|NEXT]->(target) "
            "OPTIONAL MATCH (target)-[r2:PREVIOUS|NEXT]->(current) "
            "FOREACH (_ IN CASE WHEN r1 IS NOT NULL THEN [1] ELSE [] END | DELETE r1) "
            "FOREACH (_ IN CASE WHEN r2 IS NOT NULL THEN [1] ELSE [] END | DELETE r2)"
        ),
        {"beam_id": beam_id, "id": item_id, "target_ids": payload.items},
    )
    return None


@router.patch("/{item_id}", status_code=204)
def patch_line_item(
    beam_id: int,
    item_id: int,
    payload: LineItemUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Update a specific line item under a beam line."""
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
    """Delete a specific line item under a beam line."""
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
