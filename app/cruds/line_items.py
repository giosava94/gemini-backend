from typing import Any

from neo4j import Driver

from app.db import run_query
from app.schemas.line_items import LineItemCreate, LineItemData, LineItemDetailData


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
