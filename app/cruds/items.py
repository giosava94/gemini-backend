from neo4j import Driver

from app.db import run_query
from app.schemas.items import ItemCreate


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
