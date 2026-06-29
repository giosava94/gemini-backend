"""Database and Neo4j driver management."""

from neo4j import GraphDatabase, Driver
from app.config import get_settings
import logging

logger = logging.getLogger("gemini_backend.db")


def create_driver() -> Driver:
    """Create and return a verified Neo4j driver using the application settings.

    Reads ``neo4j_uri``, ``neo4j_user``, and ``neo4j_password`` from
    :func:`~app.config.get_settings` and calls
    ``driver.verify_connectivity()`` before returning.

    :raises neo4j.exceptions.ServiceUnavailable: If the database is unreachable.
    """
    logger.debug("Creating Neo4j driver...")
    s = get_settings()
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    driver.verify_connectivity()
    logger.info(f"Neo4j driver created and verified at {s.neo4j_uri}")
    return driver


def close_driver(driver: Driver) -> None:
    """Close the Neo4j driver connection.

    A no-op when *driver* is ``None`` (e.g. if startup failed before the
    driver was created).
    """
    if driver is not None:
        logger.debug("Closing Neo4j driver...")
        driver.close()
        logger.info("Neo4j driver closed")


def ensure_constraints(driver: Driver) -> None:
    """Create uniqueness constraints for BeamLine, LineItem, and Item names.

    Uses ``IF NOT EXISTS`` so the operation is idempotent and safe to call on
    every application startup.
    """
    logger.debug("Ensuring Neo4j constraints...")
    queries = (
        "CREATE CONSTRAINT beamline_name_unique IF NOT EXISTS "
        "FOR (n:BeamLine) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT lineitem_name_unique IF NOT EXISTS "
        "FOR (n:LineItem) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT item_name_unique IF NOT EXISTS "
        "FOR (n:Item) REQUIRE n.name IS UNIQUE",
    )
    with driver.session() as session:
        for query in queries:
            session.run(query)
    logger.info("Neo4j constraints ensured")


def run_query(driver: Driver, query: str, parameters: dict | None = None) -> list:
    """Execute a Cypher query and return all records as a list.

    Opens a new session for each call, runs *query* with optional
    *parameters*, and eagerly collects all results before closing the session.

    :param driver: Active Neo4j driver instance.
    :param query: Cypher query string.
    :param parameters: Optional mapping of query parameter names to values.
    :returns: List of ``neo4j.Record`` objects (empty list when no rows match).
    """
    logger.debug(
        f"Executing query: {query[:100]}..."
        if len(query) > 100
        else f"Executing query: {query}"
    )
    if parameters:
        logger.debug(f"Query parameters: {parameters}")
    with driver.session() as session:
        result = session.run(query, parameters or {})  # pyright: ignore[reportArgumentType]
        records = [record for record in result]
    logger.debug(f"Query returned {len(records)} record(s)")
    return records


def find_by_id(driver: Driver, item_id: int) -> dict | None:
    """Find a BeamLine node by its integer ID.

    Returns a plain ``dict`` with keys ``id``, ``name``, and ``description``
    when the node is found, or ``None`` when no matching BeamLine exists.
    """
    logger.debug(f"Finding beam line by ID: {item_id}")
    query = "MATCH (b:BeamLine {id: $id}) RETURN b"
    records = run_query(driver, query, {"id": item_id})
    if not records:
        logger.warning(f"Beam line not found with ID: {item_id}")
        return None
    node = records[0]["b"]
    result = {
        "id": node["id"],
        "name": node["name"],
        "description": node.get("description"),
    }
    logger.debug(f"Found beam line: {result}")
    return result


def exists_any_name(driver: Driver, name: str, exclude_id: int | None = None) -> bool:
    """Return ``True`` if any BeamLine, LineItem, or Item node shares *name*.

    The comparison is case-insensitive.  Pass *exclude_id* to skip the node
    that owns that ID (useful when validating a rename that keeps the same
    name on the same node).

    :param driver: Active Neo4j driver instance.
    :param name: Name to look up (case-insensitive).
    :param exclude_id: Node ID to exclude from the search, or ``None``.
    :returns: ``True`` if a matching node is found, ``False`` otherwise.
    """
    logger.debug(
        f"Checking if item name exists: {name}"
        + (f" (excluding ID: {exclude_id})" if exclude_id else "")
    )
    query = (
        "MATCH (n) "
        "WHERE (n:BeamLine OR n:LineItem OR n:Item) "
        "AND toLower(n.name) = toLower($name) "
        "AND ($exclude_id IS NULL OR n.id <> $exclude_id) "
        "RETURN count(n) > 0 AS exists"
    )
    records = run_query(driver, query, {"name": name, "exclude_id": exclude_id})
    exists = bool(records and records[0]["exists"])
    logger.debug(f"Item name '{name}' exists: {exists}")
    return exists
