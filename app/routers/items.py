"""REST endpoints for items with database-managed kind validation."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from neo4j import Driver
from typing import Annotated
import logging
import redis.asyncio as redis
from app.config import get_settings
from app.cruds.item_kinds import item_kind_exists
from app.dependencies import (
    check_name_uniqueness,
    get_driver,
    get_logger,
    get_redis_client,
)
from app.redis import get_with_lock, invalidate_redis_cache
from app.schemas.items import (
    ItemCreate,
    ItemCreateResponse,
    ItemDetailResponse,
    ItemListResponse,
    ItemUpdate,
)
from app.cruds.items import (
    create,
    delete_item_record,
    get_item_record,
    get_item_records,
    get_item_relationships,
    get_total_item_records,
    conn_items_exist,
    update_item_record,
)

router = APIRouter(prefix="/api/v1/items", tags=["items"])


@router.post(
    "",
    status_code=201,
    response_model=ItemCreateResponse,
    dependencies=[Depends(check_name_uniqueness)],
)
def create_item(
    payload: ItemCreate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Create a new non-line item.

    Raises ``422`` when ``kind`` is not registered as an ``ItemKind`` node.
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

    if not item_kind_exists(driver, payload.kind):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown item kind '{payload.kind}'. "
                "Register it via POST /api/v1/item-kinds first."
            ),
        )

    if not conn_items_exist(driver, payload.connections):
        raise HTTPException(
            status_code=404,
            detail="At least one item that should be connected does not exist",
        )

    records = create(driver, payload.model_dump())
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

    params = {"name": name, "alias": alias}
    total = get_total_item_records(driver, params)
    data = get_item_records(driver, params, sort=sort, page=page, per_page=per_page)

    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.get("/{item_id}", response_model=ItemDetailResponse)
async def get_item(
    request: Request,
    item_id: int,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
):
    """Retrieve a specific non-line item by its ID.

    Returns the item data and a ``links`` object pointing to the connections
    resource.  Raises ``404`` when no Item with *item_id* exists.
    """
    logger.info(f"Fetching item with ID: {item_id}")

    # Check Redis
    if redis_client:
        key = f"item:{item_id}"
        data = await get_with_lock(
            redis_client, key, lambda: get_item_record(driver, item_id), logger
        )
    else:
        data = await get_item_record(driver, item_id)

    if not data:
        raise HTTPException(status_code=404, detail="Target item does not exist")

    # HTTP cache headers + ETag
    data_str = json.dumps(data, sort_keys=True)
    etag = f'"{hashlib.md5(data_str.encode()).hexdigest()}"'

    # Check if client has current version
    if request.headers.get("if-none-match") == etag:
        logger.info(
            f"Browser's cached value for item with ID {item_id} matches retrieved value"
        )
        return Response(status_code=304, headers={"ETag": etag})

    return Response(
        content=data_str,
        media_type="application/json",
        headers={
            "ETag": etag,
            "Cache-Control": f"public, max-age={get_settings().browser_cache_exp_time}",
        },
    )


@router.patch(
    "/{item_id}",
    status_code=204,
    dependencies=[Depends(check_name_uniqueness)],
)
async def patch_item(
    item_id: int,
    payload: ItemUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
    # _token: str = Depends(require_admin),
):
    """Partially update a non-line item's fields.

    Only the fields present in *payload* are changed; omitted fields are left
    untouched.  A supplied ``kind`` must exist in the database-managed
    ``ItemKind`` vocabulary.  Returns ``204 No Content`` on success.  Raises
    ``404`` when the item does not exist, and ``409`` when the requested name
    is already taken by another node.
    """
    logger.info(f"Updating item with ID: {item_id}")

    data = payload.model_dump(exclude_none=True)
    if not data:
        return None

    if "kind" in data and not item_kind_exists(driver, data["kind"]):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown item kind '{data['kind']}'. "
                "Register it via POST /api/v1/item-kinds first."
            ),
        )

    records = update_item_record(driver, data, item_id)
    if not records:
        raise HTTPException(status_code=404, detail="Target item does not exist")

    # Invalidate redis cache
    if redis_client:
        key = f"item:{item_id}"
        await invalidate_redis_cache(redis_client, key, logger)

    return None


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    force: Annotated[bool, Query(...)] = False,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
    # _token: str = Depends(require_admin),
):
    """Delete a non-line item by its ID.

    Returns ``204 No Content`` on success.  Raises ``409`` when the item still
    has outgoing ``CONNECTED_TO`` relationships and *force* is ``False``; pass
    ``?force=true`` to detach-delete the node together with all its
    relationships.  Returns ``204`` silently when the item does not exist.
    """
    logger.info(f"Deleting item with ID: {item_id}, force: {force}")

    records = get_item_relationships(driver, item_id)
    if not records:
        return None

    linked_count = records[0]["linked_count"]
    if linked_count and not force:
        raise HTTPException(
            status_code=409,
            detail="Can't delete an item with connected items; set force to true to override",
        )

    delete_item_record(driver, item_id)

    # Invalidate redis cache
    if redis_client:
        key = f"item:{item_id}"
        await invalidate_redis_cache(redis_client, key, logger)

    return None
