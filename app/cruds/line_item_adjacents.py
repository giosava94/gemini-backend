from neo4j import Driver

from app.db import run_query


def has_duplicate_adjacent_items(items: list[dict]) -> bool:
    """Return True if *items* contains two entries with the same (id, position) pair."""
    seen: set[tuple] = set()
    for adjacent in items:
        key = (adjacent.get("id"), adjacent.get("position"))
        if key in seen:
            return True
        seen.add(key)
    return False


def has_duplicate_adjacent_index_in_items(items: list[dict]) -> bool:
    """Return True if *items* contains two entries sharing the same (position, index) pair."""
    seen: set[tuple] = set()
    for adjacent in items:
        if adjacent.get("index") is None:
            continue
        key = (adjacent.get("position"), adjacent.get("index"))
        if key in seen:
            return True
        seen.add(key)
    return False


def get_total_line_item_adjacent_relationships(
    driver: Driver, beam_id: int, line_item_id: int, pos: str | None
):
    params = {
        "beam_id": beam_id,
        "id": line_item_id,
        "position": pos,
    }
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(current:LineItem {id: $id})-[rel:PREVIOUS|NEXT]->(adj:LineItem) "
        "WITH adj, "
        "  CASE type(rel) WHEN 'PREVIOUS' THEN 'Previous' ELSE 'Next' END AS rel_type, "
        "  rel.index AS index "
        "WHERE ($position IS NULL OR rel_type = $position) "
        "RETURN count(adj) AS total"
    )
    total_records = run_query(driver, query, params)
    return total_records[0]["total"] if total_records else 0


def get_line_item_adjacent_relationships(
    driver: Driver, beam_id: int, line_item_id: int, pos: str | None, **kwargs
):
    params = {
        "beam_id": beam_id,
        "id": line_item_id,
        "position": pos,
    }
    order_clause = (
        "ORDER BY rel_type" if kwargs["sort"] and "position" in kwargs["sort"] else ""
    )
    data_query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(current:LineItem {id: $id})-[rel:PREVIOUS|NEXT]->(adj:LineItem) "
        "WITH adj, "
        "  CASE type(rel) WHEN 'PREVIOUS' THEN 'Previous' ELSE 'Next' END AS rel_type, "
        "  rel.index AS index "
        "WHERE ($position IS NULL OR rel_type = $position) "
        "RETURN adj, rel_type AS position, index "
        f"{order_clause} SKIP $skip LIMIT $limit"
    )
    skip = (kwargs["page"] - 1) * kwargs["per_page"]
    records = run_query(
        driver,
        data_query,
        {**params, "skip": skip, "limit": kwargs["per_page"]},
    )
    data = [
        {
            "id": record["adj"]["id"],
            "name": record["adj"]["name"],
            "description": record["adj"].get("description"),
            "position": record["position"],
            "index": record["index"],
            "link": f"/api/v1/beam-lines/{beam_id}/line-items/{record['adj']['id']}",
        }
        for record in records
    ]
    return data


def disconnect_adjacents(
    driver: Driver, beam_id: int, line_item_id: int, items: list[int]
):
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(current:LineItem {id: $id}) "
        "UNWIND $target_ids AS target_id "
        "MATCH (target:LineItem {id: target_id}) "
        "OPTIONAL MATCH (current)-[r1:PREVIOUS|NEXT]->(target) "
        "OPTIONAL MATCH (target)-[r2:PREVIOUS|NEXT]->(current) "
        "FOREACH (_ IN CASE WHEN r1 IS NOT NULL THEN [1] ELSE [] END | DELETE r1) "
        "FOREACH (_ IN CASE WHEN r2 IS NOT NULL THEN [1] ELSE [] END | DELETE r2)"
    )
    records = run_query(
        driver,
        query,
        {"beam_id": beam_id, "id": line_item_id, "target_ids": items},
    )
    return records
