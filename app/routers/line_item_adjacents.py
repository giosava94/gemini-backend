from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.db import run_query
from app.dependencies import get_driver, get_logger
from app.schemas.line_item_adjacents import (
    ADJ_POS_LOOKUP,
    AdjacentPosition,
    LineItemAdjacent,
    LineItemAdjacentData,
    LineItemAdjacentPatch,
    LineItemAdjacentsDelete,
    LineItemAdjacentsListResponse,
    LineItemAdjacentsUpdate,
)

router = APIRouter(
    prefix="/api/v1/beam-lines/{beam_id}/line-items",
    tags=["line-item-adjacents"],
)


def _has_duplicate_adjacent_items(items: list[LineItemAdjacent]) -> bool:
    """Return True if *items* contains two entries with the same (id, position) pair."""
    seen: set[tuple[int, str]] = set()
    for adjacent in items:
        key = (adjacent.id, adjacent.position.value)
        if key in seen:
            return True
        seen.add(key)
    return False


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
    """Retrieve adjacent line items of the current line item with optional filtering and sorting.

    :param beam_id: ID of the parent beam line.
    :param item_id: ID of the line item whose adjacents are listed.
    :param page: 1-based page number.
    :param per_page: Number of results per page (1–100).
    :param sort: Optional sort keys; only ``"position"`` is accepted.
    :param position: Optional case-insensitive filter on the adjacent position
        (``"previous"``, ``"next"``, or ``"dual"``).

    Raises ``404`` when the beam line or item does not exist.  Raises ``422``
    for unsupported sort keys or unrecognised position values.

    Example: ``GET /api/v1/beam-lines/1/line-items/5/adjacents?position=previous``
    """
    logger.info(
        f"Listing adjacents for line item {item_id} on beam line {beam_id} - "
        f"page: {page}, per_page: {per_page}, sort: {sort}, position: {position}"
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
            detail="Beam line or current item does not exist",
        )

    if sort:
        for key in sort:
            if key != "position":
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid sort key: {key}. Valid values: position",
                )

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

    if any(item.id == item_id for item in payload.items):
        raise HTTPException(
            status_code=400,
            detail="An item cannot be adjacent to itself",
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


@router.patch("/{item_id}/adjacents/{adj_id}", status_code=204)
def patch_line_item_adjacent(
    beam_id: int,
    item_id: int,
    adj_id: int,
    payload: LineItemAdjacentPatch,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Change the position (and optionally the index) of a specific adjacent item."""
    logger.info(
        f"Patching adjacent {adj_id} of line item {item_id} on beam line {beam_id}: "
        f"position={payload.position.value}, index={payload.index}"
    )

    # Verify beam line, current item, and target adjacent item all exist
    existence_records = run_query(
        driver,
        (
            "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
            "(current:LineItem {id: $id})-[:PREVIOUS|NEXT]->(adj:LineItem {id: $adj_id}) "
            "RETURN current.id AS current_id, adj.id AS adj_id"
        ),
        {"beam_id": beam_id, "id": item_id, "adj_id": adj_id},
    )
    if not existence_records:
        raise HTTPException(
            status_code=404,
            detail="Beam line, current item or target linked item do not exist",
        )

    # Check index conflict: another adjacent at the same new position already holds this index
    if payload.index is not None:
        conflict_records = run_query(
            driver,
            (
                "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
                "(current:LineItem {id: $id})-[rel:PREVIOUS|NEXT]->(other:LineItem) "
                "WHERE other.id <> $adj_id "
                "AND (($position IN ['Previous', 'Dual'] AND type(rel) = 'PREVIOUS') "
                "     OR ($position IN ['Next', 'Dual'] AND type(rel) = 'NEXT')) "
                "AND rel.index = $index "
                "RETURN count(rel) > 0 AS has_conflict"
            ),
            {
                "beam_id": beam_id,
                "id": item_id,
                "adj_id": adj_id,
                "position": payload.position.value,
                "index": payload.index,
            },
        )
        if conflict_records and conflict_records[0]["has_conflict"]:
            raise HTTPException(
                status_code=400,
                detail="Adjacent item with the same index already exists",
            )

    # Delete existing relationships between current and adj in both directions,
    # then recreate according to the new position.
    run_query(
        driver,
        (
            "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
            "(current:LineItem {id: $id}), "
            "(adj:LineItem {id: $adj_id}) "
            "OPTIONAL MATCH (current)-[r1:PREVIOUS|NEXT]->(adj) "
            "OPTIONAL MATCH (adj)-[r2:PREVIOUS|NEXT]->(current) "
            "FOREACH (_ IN CASE WHEN r1 IS NOT NULL THEN [1] ELSE [] END | DELETE r1) "
            "FOREACH (_ IN CASE WHEN r2 IS NOT NULL THEN [1] ELSE [] END | DELETE r2) "
            "WITH current, adj "
            "FOREACH (_ IN CASE WHEN $position IN ['Previous', 'Dual'] THEN [1] ELSE [] END | "
            "  CREATE (current)-[:PREVIOUS {index: $index}]->(adj) "
            "  CREATE (adj)-[:NEXT {index: $index}]->(current) "
            ") "
            "FOREACH (_ IN CASE WHEN $position IN ['Next', 'Dual'] THEN [1] ELSE [] END | "
            "  CREATE (current)-[:NEXT {index: $index}]->(adj) "
            "  CREATE (adj)-[:PREVIOUS {index: $index}]->(current) "
            ")"
        ),
        {
            "beam_id": beam_id,
            "id": item_id,
            "adj_id": adj_id,
            "position": payload.position.value,
            "index": payload.index,
        },
    )
    return None
