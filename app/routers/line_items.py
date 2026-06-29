from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
import logging
from app.db import exists_any_name, run_query
from app.dependencies import get_driver, get_logger
from app.schemas import LineItemCreate, LineItemCreateResponse

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
