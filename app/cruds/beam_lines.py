from typing import Any

from neo4j import Driver

from app.db import run_query


def create_beam_line_record(driver: Driver, payload: dict[str, Any]) -> list:
    query = (
        "MERGE (c:Counter {name: 'beamline'}) "
        "ON CREATE SET c.value = 0 "
        "SET c.value = c.value + 1 "
        "WITH c.value AS nextId "
        "CREATE (b:BeamLine {id: nextId, name: $name, description: $description}) "
        "RETURN b.id AS id"
    )
    records = run_query(driver, query, payload)
    return records


def get_total_beam_line_records(driver: Driver, params: dict[str, Any]):
    where_clause = "WHERE ($name IS NULL OR toLower(b.name) CONTAINS toLower($name))"
    count_query = f"MATCH (b:BeamLine) {where_clause} RETURN count(b) AS total"
    total_records = run_query(driver, count_query, params)
    return total_records[0]["total"] if total_records else 0


def get_beam_line_records(driver: Driver, params: dict[str, Any], **kwargs):
    where_clause = "WHERE ($name IS NULL OR toLower(b.name) CONTAINS toLower($name))"
    order_clause = (
        "ORDER BY toLower(b.name)"
        if kwargs["sort"] and "name" in kwargs["sort"]
        else ""
    )
    query = (
        f"MATCH (b:BeamLine) {where_clause} "
        f"RETURN b {order_clause} SKIP $skip LIMIT $limit"
    )
    skip = (kwargs["page"] - 1) * kwargs["per_page"]
    records = run_query(
        driver, query, {**params, "skip": skip, "limit": kwargs["per_page"]}
    )
    return [
        {
            "id": record["b"]["id"],
            "name": record["b"]["name"],
            "description": record["b"].get("description"),
        }
        for record in records
    ]


async def get_beam_line_record(driver: Driver, beam_id: int) -> dict[str, Any] | None:
    query = "MATCH (b:BeamLine {id: $id}) RETURN b"
    records = run_query(driver, query, {"id": beam_id})
    if not records:
        return None

    item = records[0]["b"]
    data = {
        "id": item.get("id"),
        "name": item.get("name"),
        "description": item.get("description"),
    }
    links = {"line_items": f"/api/v1/beam-lines/{beam_id}/line-items"}
    return {"links": links, "data": data}


def update_beam_line_record(driver: Driver, payload: dict[str, Any], beam_id: int):
    parameters = {"id": beam_id, **payload}
    update_clauses = []
    if payload.get("name") is not None:
        update_clauses.append("b.name = $name")
    if payload.get("description") is not None:
        update_clauses.append("b.description = $description")

    query = f"MATCH (b:BeamLine {{id: $id}}) SET {', '.join(update_clauses)} RETURN b"
    records = run_query(driver, query, parameters)
    return records


def get_beam_line_relationships(driver: Driver, beam_id: int):
    query = (
        "MATCH (b:BeamLine {id: $id}) "
        "OPTIONAL MATCH (b)-[r:HAS_LINE_ITEM]->(:LineItem) "
        "RETURN count(r) AS linked_count"
    )
    records = run_query(driver, query, {"id": beam_id})
    return records


def delete_beam_line_record(driver: Driver, beam_id: int):
    records = run_query(
        driver, "MATCH (b:BeamLine {id: $id}) DETACH DELETE b", {"id": beam_id}
    )
    return records
