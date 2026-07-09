from typing import Any

from neo4j import Driver

from app.db import run_query
from app.schemas.line_item_adjacents import LineItemAdjacent
from app.schemas.line_items import (
    LineItemCreate,
    LineItemData,
    LineItemDetailData,
    LineItemUpdate,
)


def create(driver: Driver, payload: LineItemCreate, beam_id: int) -> list:
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
        "kind: $kind, status: $status, labels: $labels, aliases: $aliases"
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
    return run_query(
        driver,
        query,
        {
            "beam_id": beam_id,
            "name": payload.name,
            "description": payload.description,
            "kind": payload.kind.value,
            "status": payload.status.value,
            "labels": payload.labels,
            "aliases": payload.aliases,
            "adjacents": adjacents,
            "connections": list(set(payload.connections)),
        },
    )


def get_total_line_item_records(driver: Driver, params: dict[str, Any]):
    where_clause = (
        "WHERE ($status IS NULL OR li.status = $status) "
        "AND ($name IS NULL OR toLower(li.name) CONTAINS toLower($name)) "
        "AND ($alias IS NULL OR ANY(alias IN coalesce(li.aliases, []) "
        "WHERE toLower(alias) CONTAINS toLower($alias))) "
        "AND ($kind IS NULL OR li.kind = $kind)"
    )
    count_query = (
        "MATCH (b:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem) "
        f"{where_clause} RETURN count(li) AS total"
    )
    total_records = run_query(driver, count_query, params)
    return total_records[0]["total"] if total_records else 0


def get_line_item_records(driver: Driver, params: dict[str, Any], **kwargs):
    where_clause = (
        "WHERE ($status IS NULL OR li.status = $status) "
        "AND ($name IS NULL OR toLower(li.name) CONTAINS toLower($name)) "
        "AND ($alias IS NULL OR ANY(alias IN coalesce(li.aliases, []) "
        "WHERE toLower(alias) CONTAINS toLower($alias))) "
        "AND ($kind IS NULL OR li.kind = $kind)"
    )

    sort_clauses = []
    if kwargs["sort"]:
        for key in kwargs["sort"]:
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
    skip = (kwargs["page"] - 1) * kwargs["per_page"]
    records = run_query(
        driver, query, {**params, "skip": skip, "limit": kwargs["per_page"]}
    )
    return [
        LineItemData(
            id=record["li"]["id"],
            name=record["li"]["name"],
            description=record["li"].get("description"),
        ).model_dump()
        for record in records
    ]


async def get_line_item_record(
    driver: Driver, beam_id: int, item_id: int
) -> dict[str, Any] | None:
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "RETURN li"
    )
    records = run_query(driver, query, {"beam_id": beam_id, "id": item_id})
    if not records:
        return None

    item = records[0]["li"]
    data = LineItemDetailData(
        id=item.get("id"),
        name=item.get("name"),
        description=item.get("description"),
        kind=item.get("kind"),
        status=item.get("status"),
        labels=item.get("labels", []),
        aliases=item.get("aliases", []),
    )
    base_url = f"/api/v1/beam-lines/{beam_id}/line-items/{item_id}"
    links = {
        "adjacents": f"{base_url}/adjacents",
        "connections": f"{base_url}/connections",
    }
    return {"links": links, "data": data.model_dump()}


def update_line_item_record(
    driver: Driver, payload: LineItemUpdate, beam_id: int, line_item_id: int
):
    update_clauses: list[str] = []
    parameters: dict[str, object] = {"beam_id": beam_id, "id": line_item_id}
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
    if payload.aliases is not None:
        update_clauses.append("li.aliases = $aliases")
        parameters["aliases"] = payload.aliases

    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(li:LineItem {id: $id}) "
        f"SET {', '.join(update_clauses)} "
        "RETURN li.id AS id"
    )
    records = run_query(driver, query, parameters)
    return records


def get_line_item_relationships(driver: Driver, beam_id: int, line_item_id: int):
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "OPTIONAL MATCH (li)-[outgoing]-(:LineItem) "
        "WITH li, [rel IN collect(outgoing) "
        "WHERE type(rel) IN ['PREVIOUS', 'NEXT', 'CONNECTED_TO']] AS links "
        "RETURN li.id AS id, size(links) AS linked_count"
    )
    records = run_query(driver, query, {"beam_id": beam_id, "id": line_item_id})
    return records


def delete_line_item_record(driver: Driver, beam_id: int, line_item_id: int):
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(li:LineItem {id: $id}) "
        "DETACH DELETE li"
    )
    records = run_query(driver, query, {"beam_id": beam_id, "id": line_item_id})
    return records


def adj_and_conn_items_exist(driver: Driver, ids: list[int]) -> bool:
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


def has_duplicate_adjacent_index(items: list[LineItemAdjacent]) -> bool:
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


def beam_line_exists(driver: Driver, beam_id: int) -> bool:
    records = run_query(
        driver, "MATCH (b:BeamLine {id: $id}) RETURN b.id AS id", {"id": beam_id}
    )
    return bool(records)
