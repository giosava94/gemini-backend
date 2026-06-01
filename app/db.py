"""Database and Neo4j driver management."""

from neo4j import GraphDatabase, Driver
from app.config import get_settings
import logging

logger = logging.getLogger("gemini_backend.db")


def create_driver() -> Driver:
    """Create and initialize a Neo4j driver connection."""
    logger.debug("Creating Neo4j driver...")
    s = get_settings()
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    driver.verify_connectivity()
    logger.info(f"Neo4j driver created and verified at {s.neo4j_uri}")
    return driver


def close_driver(driver: Driver) -> None:
    """Close the Neo4j driver connection."""
    if driver is not None:
        logger.debug("Closing Neo4j driver...")
        driver.close()
        logger.info("Neo4j driver closed")


def ensure_constraints(driver: Driver) -> None:
    """Create necessary Neo4j constraints."""
    logger.debug("Ensuring Neo4j constraints...")
    query = (
        "CREATE CONSTRAINT beamline_name_unique IF NOT EXISTS "
        "FOR (n:BeamLine) REQUIRE n.name IS UNIQUE"
    )
    with driver.session() as session:
        session.run(query)
    logger.info("Neo4j constraints ensured")


def run_query(driver: Driver, query: str, parameters: dict | None = None) -> list:
    """Execute a Neo4j query and return results."""
    logger.debug(f"Executing query: {query[:100]}..." if len(query) > 100 else f"Executing query: {query}")
    if parameters:
        logger.debug(f"Query parameters: {parameters}")
    with driver.session() as session:
        result = session.run(query, parameters or {}) # pyright: ignore[reportArgumentType]
        records = [record for record in result]
    logger.debug(f"Query returned {len(records)} record(s)")
    return records


def find_by_id(driver: Driver, item_id: int) -> dict | None:
    """Find a beam line by ID."""
    logger.debug(f"Finding beam line by ID: {item_id}")
    query = "MATCH (b:BeamLine {id: $id}) RETURN b"
    records = run_query(driver, query, {"id": item_id})
    if not records:
        logger.warning(f"Beam line not found with ID: {item_id}")
        return None
    node = records[0]["b"]
    result = {"id": node["id"], "name": node["name"], "description": node.get("description")}
    logger.debug(f"Found beam line: {result}")
    return result


def exists_name(driver: Driver, name: str, exclude_id: int | None = None) -> bool:
    """Check if a beam line name exists (case-insensitive)."""
    logger.debug(f"Checking if beam line name exists: {name}" + (f" (excluding ID: {exclude_id})" if exclude_id else ""))
    query = (
        "MATCH (b:BeamLine) "
        "WHERE toLower(b.name) = toLower($name) "
        "AND ($exclude_id IS NULL OR b.id <> $exclude_id) "
        "RETURN count(b) > 0 AS exists"
    )
    records = run_query(driver, query, {"name": name, "exclude_id": exclude_id})
    exists = bool(records and records[0]["exists"])
    logger.debug(f"Beam line name '{name}' exists: {exists}")
    return exists
