"""Database and Neo4j driver management."""

from neo4j import GraphDatabase, Driver
from app.config import get_settings


def create_driver() -> Driver:
    """Create and initialize a Neo4j driver connection."""
    s = get_settings()
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    driver.verify_connectivity()
    return driver


def close_driver(driver: Driver) -> None:
    """Close the Neo4j driver connection."""
    if driver is not None:
        driver.close()


def ensure_constraints(driver: Driver) -> None:
    """Create necessary Neo4j constraints."""
    query = (
        "CREATE CONSTRAINT beamline_name_unique IF NOT EXISTS "
        "FOR (n:BeamLine) REQUIRE n.name IS UNIQUE"
    )
    with driver.session() as session:
        session.run(query)


def run_query(driver: Driver, query: str, parameters: dict | None = None) -> list:
    """Execute a Neo4j query and return results."""
    with driver.session() as session:
        result = session.run(query, parameters or {}) # pyright: ignore[reportArgumentType]
        return [record for record in result]


def find_by_id(driver: Driver, item_id: int) -> dict | None:
    """Find a beam line by ID."""
    query = "MATCH (b:BeamLine {id: $id}) RETURN b"
    records = run_query(driver, query, {"id": item_id})
    if not records:
        return None
    node = records[0]["b"]
    return {"id": node["id"], "name": node["name"], "description": node.get("description")}


def exists_name(driver: Driver, name: str, exclude_id: int | None = None) -> bool:
    """Check if a beam line name exists (case-insensitive)."""
    query = (
        "MATCH (b:BeamLine) "
        "WHERE toLower(b.name) = toLower($name) "
        "AND ($exclude_id IS NULL OR b.id <> $exclude_id) "
        "RETURN count(b) > 0 AS exists"
    )
    records = run_query(driver, query, {"name": name, "exclude_id": exclude_id})
    return bool(records and records[0]["exists"])
