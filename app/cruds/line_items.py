from neo4j import Driver

from app.db import run_query
from app.schemas.line_items import LineItemCreate


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
