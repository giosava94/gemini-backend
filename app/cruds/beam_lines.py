from neo4j import Driver

from app.db import run_query
from app.schemas.beam_lines import BeamLineCreate


def create(driver: Driver, payload: BeamLineCreate) -> list:
    query = (
        "MERGE (c:Counter {name: 'beamline'}) "
        "ON CREATE SET c.value = 0 "
        "SET c.value = c.value + 1 "
        "WITH c.value AS nextId "
        "CREATE (b:BeamLine {id: nextId, name: $name, description: $description}) "
        "RETURN b.id AS id"
    )
    return run_query(
        driver, query, {"name": payload.name, "description": payload.description}
    )
