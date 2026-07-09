from typing import Any

from neo4j import Driver

from app.db import run_query
from app.schemas.items import ItemCreate, ItemData, ItemDetailData


def create(driver: Driver, payload: ItemCreate) -> list:
    query = (
        "MERGE (c:Counter {name: 'item'}) "
        "ON CREATE SET c.value = 0 "
        "SET c.value = c.value + 1 "
        "WITH c.value AS nextId "
        "CREATE (i:Item {"
        "id: nextId, name: $name, description: $description, "
        "kind: $kind, status: $status, labels: $labels, aliases: $aliases"
        "}) "
        "WITH i "
        "CALL (i) { "
        "UNWIND $connections AS connected_id "
        "MATCH (target) WHERE (target:Item OR target:LineItem) AND target.id = connected_id "
        "CREATE (i)-[:CONNECTED_TO]->(target) "
        "RETURN count(*) AS connection_count "
        "} "
        "RETURN i.id AS id"
    )
    return run_query(
        driver,
        query,
        {
            "name": payload.name,
            "description": payload.description,
            "kind": payload.kind.value,
            "status": payload.status.value,
            "labels": payload.labels,
            "aliases": payload.aliases,
            "connections": list(set(payload.connections)),
        },
    )


def get_total_item_records(driver: Driver, params: dict[str, Any]):
    where_clause = (
        "WHERE ($name IS NULL OR toLower(i.name) CONTAINS toLower($name)) "
        "AND ($alias IS NULL OR ANY(alias IN coalesce(i.aliases, []) "
        "WHERE toLower(alias) CONTAINS toLower($alias))) "
    )
    count_query = f"MATCH (i:Item) {where_clause} RETURN count(i) AS total"
    total_records = run_query(driver, count_query, params)
    return total_records[0]["total"] if total_records else 0


def get_item_records(driver: Driver, params: dict[str, Any], **kwargs):
    where_clause = (
        "WHERE ($name IS NULL OR toLower(i.name) CONTAINS toLower($name)) "
        "AND ($alias IS NULL OR ANY(alias IN coalesce(i.aliases, []) "
        "WHERE toLower(alias) CONTAINS toLower($alias))) "
    )

    sort_clauses = []
    if kwargs["sort"]:
        for key in kwargs["sort"]:
            if key == "name":
                sort_clauses.append("toLower(i.name)")
            elif key == "kind":
                sort_clauses.append("i.kind")
    order_clause = f"ORDER BY {', '.join(sort_clauses)}" if sort_clauses else ""

    skip = (kwargs["page"] - 1) * kwargs["per_page"]
    data_query = (
        f"MATCH (i:Item) {where_clause} RETURN i {order_clause} SKIP $skip LIMIT $limit"
    )
    records = run_query(
        driver,
        data_query,
        {**params, "skip": skip, "limit": kwargs["per_page"]},
    )
    return [
        ItemData(
            id=record["i"]["id"],
            name=record["i"]["name"],
            description=record["i"].get("description"),
        ).model_dump()
        for record in records
    ]


async def get_item_record(driver: Driver, item_id: int) -> dict[str, Any] | None:
    records = run_query(driver, "MATCH (i:Item {id: $id}) RETURN i", {"id": item_id})
    if not records:
        return None

    item = records[0]["i"]
    data = ItemDetailData(
        id=item.get("id"),
        name=item.get("name"),
        description=item.get("description"),
        kind=item.get("kind"),
        status=item.get("status"),
        labels=item.get("labels", []),
        aliases=item.get("aliases", []),
    )
    links = {"connections": f"/api/v1/items/{item_id}/connections"}
    return {"links": links, "data": data.model_dump()}
