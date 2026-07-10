from neo4j import Driver

from app.db import run_query
from app.schemas.item_connections import ItemConnectionData, ItemLineItemConnectionData


def connect_item_records(driver: Driver, item_id: int, connections: list[dict]):
    query = (
        "MATCH (current:Item {id: $id}) "
        "UNWIND $connections AS connection "
        "MATCH (target:Item {id: connection.id}) "
        "MERGE (current)-[rel:CONNECTED_TO]-(target) "
        "SET rel = connection.properties"
    )
    records = run_query(driver, query, {"id": item_id, "connections": connections})
    return records


def get_total_connected_items(driver: Driver, item_id: int):
    query = (
        "MATCH (i:Item {id: $id})-[:CONNECTED_TO]-(conn:Item) "
        "RETURN count(conn) AS total"
    )
    total_records = run_query(driver, query, {"id": item_id})
    return total_records[0]["total"] if total_records else 0


def get_connected_items(driver: Driver, item_id: int, **kwargs):
    skip = (kwargs["page"] - 1) * kwargs["per_page"]
    query = (
        "MATCH (i:Item {id: $id})-[rel:CONNECTED_TO]-(conn:Item) "
        "RETURN conn, properties(rel) AS rel_props "
        "SKIP $skip LIMIT $limit"
    )
    records = run_query(
        driver, query, {"id": item_id, "skip": skip, "limit": kwargs["per_page"]}
    )
    return [
        ItemConnectionData(
            id=record["conn"]["id"],
            name=record["conn"]["name"],
            description=record["conn"].get("description"),
            properties=record.get("rel_props"),
            link=f"/api/v1/items/{record['conn']['id']}",
        ).model_dump()
        for record in records
    ]


def disconnect_item_records(driver: Driver, item_id: int, items: list[int]):
    query = (
        "MATCH (i:Item {id: $id})-[rel:CONNECTED_TO]-(conn:Item) "
        "WHERE conn.id IN $target_ids "
        "DELETE rel"
    )
    records = run_query(driver, query, {"id": item_id, "target_ids": items})
    return records


def item_exists(driver: Driver, item_id: int) -> bool:
    records = run_query(
        driver, "MATCH (i:Item {id: $id}) RETURN i.id AS id", {"id": item_id}
    )
    return bool(records)


def get_total_connected_line_items(driver: Driver, item_id: int):
    query = (
        "MATCH (li:LineItem)-[:CONNECTED_TO]->(i:Item {id: $id}) "
        "RETURN count(li) AS total"
    )
    total_records = run_query(driver, query, {"id": item_id})
    return total_records[0]["total"] if total_records else 0


def get_connected_line_items(driver: Driver, item_id: int, **kwargs):
    skip = (kwargs["page"] - 1) * kwargs["per_page"]
    query = (
        "MATCH (b:BeamLine)-[:HAS_LINE_ITEM]->(li:LineItem)-[:CONNECTED_TO]->(i:Item {id: $id}) "
        "RETURN li, b.id AS beam_id "
        "SKIP $skip LIMIT $limit"
    )
    records = run_query(
        driver, query, {"id": item_id, "skip": skip, "limit": kwargs["per_page"]}
    )
    return [
        ItemLineItemConnectionData(
            id=record["conn"]["id"],
            name=record["conn"]["name"],
            description=record["conn"].get("description"),
            link=(
                f"/api/v1/beam-lines/{record['beam_id']}"
                f"/line-items/{record['li']['id']}"
            ),
        ).model_dump()
        for record in records
    ]
