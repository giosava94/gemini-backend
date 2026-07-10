from neo4j import Driver

from app.db import run_query
from app.schemas.line_item_connections import LineItemConnectionData


def beam_line_and_line_item_exist(driver: Driver, beam_id: int, item_id: int):
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "RETURN li.id AS id"
    )
    records = run_query(
        driver,
        query,
        {"beam_id": beam_id, "id": item_id},
    )
    return bool(records)


def get_total_line_item_connections(driver: Driver, beam_id: int, line_item_id: int):
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(li:LineItem {id: $id})-[:CONNECTED_TO]->(conn:Item) "
        "RETURN count(conn) AS total"
    )
    total_records = run_query(driver, query, {"beam_id": beam_id, "id": line_item_id})
    return total_records[0]["total"] if total_records else 0


def get_line_item_connections(
    driver: Driver, beam_id: int, line_item_id: int, **kwargs
):
    skip = (kwargs["page"] - 1) * kwargs["per_page"]
    data_query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(li:LineItem {id: $id})-[rel:CONNECTED_TO]->(conn:Item) "
        "RETURN conn, properties(rel) AS rel_props "
        "SKIP $skip LIMIT $limit"
    )
    records = run_query(
        driver,
        data_query,
        {
            "beam_id": beam_id,
            "id": line_item_id,
            "skip": skip,
            "limit": kwargs["per_page"],
        },
    )
    return [
        LineItemConnectionData(
            id=record["conn"]["id"],
            name=record["conn"]["name"],
            description=record["conn"].get("description"),
            properties=record.get("rel_props") or {},
            link=f"/api/v1/items/{record['conn']['id']}",
        ).model_dump()
        for record in records
    ]


def update_line_item_connected_records(
    driver: Driver, beam_id: int, line_item_id: int, connections: list[dict]
):
    # MERGE so re-connecting an already connected item is a no-op
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->(li:LineItem {id: $id}) "
        "UNWIND $connections AS connection "
        "MATCH (target:Item {id: connection.id}) "
        "MERGE (li)-[rel:CONNECTED_TO]->(target) "
        "SET rel = connection.properties"
    )
    records = run_query(
        driver,
        query,
        {"beam_id": beam_id, "id": line_item_id, "connections": connections},
    )
    return records


def disconnect_line_item_connected_records(
    driver: Driver, beam_id: int, line_item_id: int, items: list[int]
):
    query = (
        "MATCH (:BeamLine {id: $beam_id})-[:HAS_LINE_ITEM]->"
        "(li:LineItem {id: $id})-[rel:CONNECTED_TO]->(conn:Item) "
        "WHERE conn.id IN $target_ids "
        "DELETE rel"
    )
    records = run_query(
        driver, query, {"beam_id": beam_id, "id": line_item_id, "target_ids": items}
    )
    return records
