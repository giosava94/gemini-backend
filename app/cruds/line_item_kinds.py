"""CRUD operations for LineItemKind nodes.

``LineItemKind`` nodes are standalone Neo4j nodes that store the controlled
vocabulary of valid kind labels for :class:`~app.schemas.line_items.LineItemCreate`.
Each node has a single ``name`` property that is globally unique (enforced by a
Neo4j uniqueness constraint created at application startup).

All functions accept a :class:`neo4j.Driver` as their first argument and
delegate every database call to :func:`~app.db.run_query`, keeping the graph
communication entirely within this module.
"""

from neo4j import Driver

from app.db import run_query


def create_line_item_kind(driver: Driver, name: str) -> list:
    """Create a new ``LineItemKind`` node with the given *name*.

    Uses a counter node (``Counter {name: 'lineitemkind'}``) to assign an
    auto-incrementing integer ``id``.  The operation is not idempotent: callers
    must verify name uniqueness before calling this function.

    :param driver: Active Neo4j driver instance.
    :param name: Label for the new kind (e.g. ``"Wien Filter"``).
    :returns: List with one record containing ``name`` when the node is
        created; an empty list on failure.

    Example Cypher::

        MERGE (c:Counter {name: 'lineitemkind'})
        ON CREATE SET c.value = 0
        SET c.value = c.value + 1
        WITH c.value AS nextId
        CREATE (k:LineItemKind {id: nextId, name: $name})
        RETURN k.name AS name
    """
    query = (
        "MERGE (c:Counter {name: 'lineitemkind'}) "
        "ON CREATE SET c.value = 0 "
        "SET c.value = c.value + 1 "
        "WITH c.value AS nextId "
        "CREATE (k:LineItemKind {id: nextId, name: $name}) "
        "RETURN k.name AS name"
    )
    return run_query(driver, query, {"name": name})


def get_all_line_item_kinds(driver: Driver) -> list[dict]:
    """Return all ``LineItemKind`` nodes, ordered alphabetically by name.

    :param driver: Active Neo4j driver instance.
    :returns: List of dicts with a ``"name"`` key for each kind; empty list
        when no kinds have been created yet.

    Example Cypher::

        MATCH (k:LineItemKind) RETURN k.name AS name ORDER BY toLower(k.name)
    """
    query = "MATCH (k:LineItemKind) RETURN k.name AS name ORDER BY toLower(k.name)"
    records = run_query(driver, query)
    return [{"name": record["name"]} for record in records]


def delete_line_item_kind(driver: Driver, name: str) -> list:
    """Delete the ``LineItemKind`` node whose ``name`` matches *name* exactly.

    The match is case-sensitive.  Returns an empty list whether or not the
    node existed — callers that need to distinguish the two cases should call
    :func:`line_item_kind_exists` first.

    :param driver: Active Neo4j driver instance.
    :param name: Exact kind label to remove.
    :returns: Result list from ``run_query`` (always empty for a DELETE).

    Example Cypher::

        MATCH (k:LineItemKind {name: $name}) DELETE k
    """
    query = "MATCH (k:LineItemKind {name: $name}) DELETE k"
    return run_query(driver, query, {"name": name})


def line_item_kind_exists(driver: Driver, name: str) -> bool:
    """Return ``True`` if a ``LineItemKind`` node with *name* exists.

    The comparison is case-sensitive so that ``"Diagnostic"`` and
    ``"diagnostic"`` are treated as different kinds.

    :param driver: Active Neo4j driver instance.
    :param name: Kind label to look up.
    :returns: ``True`` when a matching node is found, ``False`` otherwise.

    Example Cypher::

        MATCH (k:LineItemKind {name: $name}) RETURN count(k) > 0 AS exists
    """
    query = "MATCH (k:LineItemKind {name: $name}) RETURN count(k) > 0 AS exists"
    records = run_query(driver, query, {"name": name})
    return bool(records and records[0]["exists"])


def line_item_kind_in_use(driver: Driver, name: str) -> bool:
    """Return ``True`` if any ``LineItem`` node currently uses *name* as its kind.

    Used to prevent deletion of a kind that is still referenced by existing
    line items.  The comparison is case-sensitive and matches the value stored
    in ``li.kind``.

    :param driver: Active Neo4j driver instance.
    :param name: Kind label to check for active usage.
    :returns: ``True`` when at least one ``LineItem`` node references the kind.

    Example Cypher::

        MATCH (li:LineItem {kind: $name}) RETURN count(li) > 0 AS in_use
    """
    query = "MATCH (li:LineItem {kind: $name}) RETURN count(li) > 0 AS in_use"
    records = run_query(driver, query, {"name": name})
    return bool(records and records[0]["in_use"])
