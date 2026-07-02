from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
import logging
from app.db import exists_any_name, run_query
from app.dependencies import get_driver, get_logger
from app.schemas import (
    ItemCreate,
    ItemCreateResponse,
    ItemData,
    ItemDetailData,
    ItemDetailResponse,
    ItemListResponse,
    ItemUpdate,
)

router = APIRouter(
    prefix="/api/v1/items",
    tags=["items"],
)


def _ids_exist(driver: Driver, ids: list[int]) -> bool:
    """Return True if every ID in *ids* belongs to an existing Item or LineItem node."""
    distinct_ids = list(set(ids))
    if not distinct_ids:
        return True
    query = (
        "UNWIND $ids AS id "
        "OPTIONAL MATCH (n) WHERE (n:Item OR n:LineItem) AND n.id = id "
        "RETURN count(n) = size($ids) AS all_exist"
    )
    records = run_query(driver, query, {"ids": distinct_ids})
    return bool(records and records[0]["all_exist"])


@router.post("", status_code=201, response_model=ItemCreateResponse)
def create_item(
    payload: ItemCreate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Create a new non-line item.

    Raises ``409`` when a node with the same name already exists.  Raises
    ``404`` when any of the requested connection IDs do not exist.

    Example request body::

        {
            "name": "RACK-01",
            "kind": "Rack",
            "status": 0,
            "connections": []
        }

    Example response::

        {"id": 42}
    """
    logger.info(f"Creating item with name: {payload.name}")

    if exists_any_name(driver, payload.name):
        raise HTTPException(
            status_code=409, detail="Item with this name already exists"
        )

    if payload.connections and not _ids_exist(driver, payload.connections):
        raise HTTPException(
            status_code=404,
            detail="At least one item that should be connected does not exist",
        )

    query = (
        "MERGE (c:Counter {name: 'item'}) "
        "ON CREATE SET c.value = 0 "
        "SET c.value = c.value + 1 "
        "WITH c.value AS nextId "
        "CREATE (i:Item {"
        "id: nextId, name: $name, description: $description, "
        "kind: $kind, status: $status, labels: $labels, aliases: $aliases"
        "}) "
        "WITH i "
        "CALL (i) { "
        "UNWIND $connections AS connected_id "
        "MATCH (target) WHERE (target:Item OR target:LineItem) AND target.id = connected_id "
        "CREATE (i)-[:CONNECTED_TO]->(target) "
        "RETURN count(*) AS connection_count "
        "} "
        "RETURN i.id AS id"
    )
    records = run_query(
        driver,
        query,
        {
            "name": payload.name,
            "description": payload.description,
            "kind": payload.kind.value,
            "status": payload.status.value,
            "labels": payload.labels,
            "aliases": payload.aliases,
            "connections": list(set(payload.connections)),
        },
    )
    if not records:
        raise HTTPException(status_code=500, detail="Failed to create item")
    return {"id": records[0]["id"]}


@router.get("", response_model=ItemListResponse)
def list_items(
    page: Annotated[int, Query(..., ge=1)] = 1,
    per_page: Annotated[int, Query(..., ge=1, le=100)] = 10,
    sort: Annotated[list[str] | None, Query(...)] = None,
    name: Annotated[str | None, Query(...)] = None,
    alias: Annotated[str | None, Query(...)] = None,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """List non-line items with optional name filtering, sorting, and pagination.

    *page* is 1-based; *per_page* is clamped to 1–100.  *sort* accepts one or
    more of ``"name"`` or ``"kind"``; any other value raises ``422``.  *name*
    is matched as a case-insensitive substring against the item name.

    Example: ``GET /api/v1/items?page=1&per_page=10&sort=name&name=rack``
    """
    logger.info(
        f"Listing items - page: {page}, per_page: {per_page}, "
        f"sort: {sort}, name filter: {name}"
    )

    if sort:
        for key in sort:
            if key not in ("name", "kind"):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid sort key: {key}. Valid values: name, kind",
                )

    where_clause = (
        "WHERE ($name IS NULL OR toLower(i.name) CONTAINS toLower($name)) "
        "AND ($alias IS NULL OR ANY(alias IN coalesce(i.aliases, []) "
        "WHERE toLower(alias) CONTAINS toLower($alias))) "
    )
    parameters: dict = {"name": name, "alias": alias}

    count_query = f"MATCH (i:Item) {where_clause} RETURN count(i) AS total"
    total_records = run_query(driver, count_query, parameters)
    total = total_records[0]["total"] if total_records else 0

    sort_clauses = []
    if sort:
        for key in sort:
            if key == "name":
                sort_clauses.append("toLower(i.name)")
            elif key == "kind":
                sort_clauses.append("i.kind")
    order_clause = f"ORDER BY {', '.join(sort_clauses)}" if sort_clauses else ""

    skip = (page - 1) * per_page
    data_query = (
        f"MATCH (i:Item) {where_clause} "
        f"RETURN i {order_clause} SKIP $skip LIMIT $limit"
    )
    records = run_query(
        driver,
        data_query,
        {**parameters, "skip": skip, "limit": per_page},
    )
    data = [
        ItemData(
            id=record["i"]["id"],
            name=record["i"]["name"],
            description=record["i"].get("description"),
        )
        for record in records
    ]
    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.get("/{item_id}", response_model=ItemDetailResponse)
def get_item(
    item_id: int,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Retrieve a specific non-line item by its ID.

    Returns the item data and a ``links`` object pointing to the connections
    resource.  Raises ``404`` when no Item with *item_id* exists.
    """
    logger.info(f"Fetching item with ID: {item_id}")

    records = run_query(
        driver,
        "MATCH (i:Item {id: $id}) RETURN i",
        {"id": item_id},
    )
    if not records:
        raise HTTPException(status_code=404, detail="Target item does not exist")

    item = records[0]["i"]
    data = ItemDetailData(
        id=item["id"],
        name=item["name"],
        description=item.get("description"),
        kind=item["kind"],
        status=item["status"],
        labels=item.get("labels", []),
        aliases=item.get("aliases", []),
    )
    return {
        "links": {"connections": f"/api/v1/items/{item_id}/connections"},
        "data": data,
    }


@router.patch("/{item_id}", status_code=204)
def patch_item(
    item_id: int,
    payload: ItemUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Partially update a non-line item's name, description, and/or status.

    Only the fields present in *payload* are changed; omitted fields are left
    untouched.  Returns ``204 No Content`` on success.  Raises ``404`` when
    the item does not exist, and ``409`` when the requested name is already
    taken by another node.
    """
    logger.info(f"Updating item with ID: {item_id}")

    if payload.name and exists_any_name(driver, payload.name, exclude_id=item_id):
        raise HTTPException(
            status_code=409, detail="An item with the same name already exists"
        )

    update_clauses: list[str] = []
    parameters: dict = {"id": item_id}
    if payload.name is not None:
        update_clauses.append("i.name = $name")
        parameters["name"] = payload.name
    if payload.description is not None:
        update_clauses.append("i.description = $description")
        parameters["description"] = payload.description
    if payload.status is not None:
        update_clauses.append("i.status = $status")
        parameters["status"] = payload.status.value
    if payload.labels is not None:
        update_clauses.append("i.labels = $labels")
        parameters["labels"] = payload.labels
    if payload.aliases is not None:
        update_clauses.append("i.aliases = $aliases")
        parameters["aliases"] = payload.aliases

    if not update_clauses:
        return None

    records = run_query(
        driver,
        (
            f"MATCH (i:Item {{id: $id}}) "
            f"SET {', '.join(update_clauses)} "
            "RETURN i.id AS id"
        ),
        parameters,
    )
    if not records:
        raise HTTPException(status_code=404, detail="Target item does not exist")
    return None


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    force: Annotated[bool, Query(...)] = False,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Delete a non-line item by its ID.

    Returns ``204 No Content`` on success.  Raises ``409`` when the item still
    has outgoing ``CONNECTED_TO`` relationships and *force* is ``False``; pass
    ``?force=true`` to detach-delete the node together with all its
    relationships.  Returns ``204`` silently when the item does not exist.
    """
    logger.info(f"Deleting item with ID: {item_id}, force: {force}")

    records = run_query(
        driver,
        (
            "MATCH (i:Item {id: $id}) "
            "OPTIONAL MATCH (i)-[rel:CONNECTED_TO]->() "
            "RETURN i.id AS id, count(rel) AS linked_count"
        ),
        {"id": item_id},
    )
    if not records or records[0]["id"] is None:
        return None

    linked_count = records[0]["linked_count"]
    if linked_count and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                "Can't delete an item with connected items; "
                "set force to true to override"
            ),
        )

    run_query(
        driver,
        "MATCH (i:Item {id: $id}) DETACH DELETE i",
        {"id": item_id},
    )
    return None
