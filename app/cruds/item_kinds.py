"""CRUD operations for the database-managed ItemKind vocabulary."""

from neo4j import Driver

from app.db import run_query


def create_item_kind(driver: Driver, name: str) -> list:
    """Create an ``ItemKind`` node and return its name."""
    query = (
        "MERGE (c:Counter {name: 'itemkind'}) "
        "ON CREATE SET c.value = 0 "
        "SET c.value = c.value + 1 "
        "WITH c.value AS nextId "
        "CREATE (k:ItemKind {id: nextId, name: $name}) "
        "RETURN k.name AS name"
    )
    return run_query(driver, query, {"name": name})


def get_all_item_kinds(driver: Driver) -> list[dict]:
    """Return all ``ItemKind`` nodes ordered alphabetically by name."""
    query = "MATCH (k:ItemKind) RETURN k.name AS name ORDER BY toLower(k.name)"
    records = run_query(driver, query)
    return [{"name": record["name"]} for record in records]


def delete_item_kind(driver: Driver, name: str) -> list:
    """Delete the ``ItemKind`` node matching *name*."""
    query = "MATCH (k:ItemKind {name: $name}) DELETE k"
    return run_query(driver, query, {"name": name})


def item_kind_exists(driver: Driver, name: str) -> bool:
    """Return whether an ``ItemKind`` node matching *name* exists."""
    query = "MATCH (k:ItemKind {name: $name}) RETURN count(k) > 0 AS exists"
    records = run_query(driver, query, {"name": name})
    return bool(records and records[0]["exists"])


def item_kind_in_use(driver: Driver, name: str) -> bool:
    """Return whether an ``Item`` currently references *name* as its kind."""
    query = "MATCH (i:Item {kind: $name}) RETURN count(i) > 0 AS in_use"
    records = run_query(driver, query, {"name": name})
    return bool(records and records[0]["in_use"])
