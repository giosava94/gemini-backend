import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from neo4j import Driver
from typing import Annotated
import logging
import redis.asyncio as redis
from app.config import get_settings
from app.dependencies import (
    check_name_uniqueness,
    get_driver,
    get_logger,
    get_redis_client,
)
from app.redis import get_with_lock, invalidate_redis_cache
from app.schemas.line_items import (
    LINE_ITEM_KIND_LOOKUP,
    LineItemCreate,
    LineItemCreateResponse,
    LineItemDetailResponse,
    LineItemListResponse,
    LineItemStatus,
    LineItemUpdate,
)
from app.cruds.line_items import (
    create,
    delete_line_item_record,
    get_line_item_record,
    get_line_item_records,
    get_line_item_relationships,
    get_total_line_item_records,
    has_duplicate_adjacent_index,
    adj_and_conn_items_exist,
    beam_line_exists,
    update_line_item_record,
)


def check_beam_line_exists(beam_id: int, driver: Driver = Depends(get_driver)):
    if not beam_line_exists(driver, beam_id):
        raise HTTPException(status_code=404, detail="Beam line does not exist")


router = APIRouter(
    prefix="/api/v1/beam-lines/{beam_id}/line-items",
    tags=["line-items"],
    dependencies=[Depends(check_beam_line_exists)],
)


@router.post(
    "",
    status_code=201,
    response_model=LineItemCreateResponse,
    dependencies=[Depends(check_name_uniqueness)],
)
def create_line_item(
    beam_id: int,
    payload: LineItemCreate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # _token: str = Depends(require_admin),
):
    """Create a new line item under a beam line.

    Raises ``404`` when the beam line does not exist.  Raises ``409`` when a
    node with the same name already exists.  Raises ``400`` when the adjacents
    list contains duplicate ``(position, index)`` pairs.  Raises ``404`` when
    any adjacent or connection ID does not exist.

    Example request body::

        {
            "name": "QD01",
            "kind": "ES_Quadrupole",
            "status": 0,
            "adjacents": [{"id": 5, "position": "Previous", "index": 0}],
            "connections": []
        }

    Example response::

        {"id": 12}
    """
    logger.info(f"Creating line item with name: {payload.name} for beam line {beam_id}")

    if has_duplicate_adjacent_index([i.model_dump() for i in payload.adjacents]):
        raise HTTPException(
            status_code=400,
            detail="Adjacent item with the same index already exists",
        )

    adjacent_ids = [adjacent.id for adjacent in payload.adjacents]
    if not adj_and_conn_items_exist(driver, adjacent_ids + payload.connections):
        raise HTTPException(
            status_code=404,
            detail="Previous, next or connected item does not exist",
        )

    records = create(driver, payload.model_dump(), beam_id)
    if not records:
        raise HTTPException(status_code=500, detail="Failed to create line item")

    return {"id": records[0]["id"]}


@router.get("", response_model=LineItemListResponse)
def list_line_items(
    beam_id: int,
    page: Annotated[int, Query(..., ge=1)] = 1,
    per_page: Annotated[int, Query(..., ge=1, le=100)] = 10,
    sort: Annotated[list[str] | None, Query(...)] = None,
    name: Annotated[str | None, Query(...)] = None,
    alias: Annotated[str | None, Query(...)] = None,
    kind: Annotated[str | None, Query(...)] = None,
    status: Annotated[LineItemStatus | None, Query(...)] = None,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """List line items for a beam line with optional filtering, sorting, and pagination.

    :param beam_id: ID of the parent beam line.
    :param page: 1-based page number.
    :param per_page: Number of results per page (1-100).
    :param sort: Optional sort keys; accepted values are ``"name"`` and ``"kind"``.
    :param name: Optional case-insensitive substring filter on the item name.
    :param kind: Optional case-insensitive kind filter (e.g. ``"diagnostic"``).
    :param status: Optional status filter using :class:`LineItemStatus` values.

    Raises ``404`` when the beam line does not exist.  Raises ``422`` for
    unsupported sort keys or unrecognised kind values.

    Example: ``GET /api/v1/beam-lines/1/line-items?page=1&per_page=10&kind=diagnostic``
    """
    logger.info(
        "Listing line items - "
        f"beam_id: {beam_id}, page: {page}, per_page: {per_page}, "
        f"name filter: {name}, kind filter: {kind}, "
        f"status: {status.value if status else None}"
    )

    if sort:
        for key in sort:
            if key not in ("name", "kind"):
                raise HTTPException(status_code=422, detail=f"Invalid sort key: {key}")

    normalized_kind = None
    if kind is not None:
        normalized_kind = LINE_ITEM_KIND_LOOKUP.get(kind.lower())
        if normalized_kind is None:
            allowed = ", ".join(item.value for item in LINE_ITEM_KIND_LOOKUP.values())
            raise HTTPException(
                status_code=422,
                detail=f"Invalid kind; must be one of: {allowed}",
            )

    params = {
        "beam_id": beam_id,
        "status": status.value if status else None,
        "name": name,
        "alias": alias,
        "kind": normalized_kind.value if normalized_kind else None,
    }
    total = get_total_line_item_records(driver, params)
    data = get_line_item_records(
        driver, params, sort=sort, page=page, per_page=per_page
    )

    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.get("/{item_id}", response_model=LineItemDetailResponse)
async def get_line_item(
    request: Request,
    beam_id: int,
    item_id: int,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
):
    """Retrieve a specific line item under a beam line.

    Returns the item data along with ``links`` pointing to the adjacents and
    connections sub-resources.  Raises ``404`` when either the beam line or
    the line item does not exist.
    """
    logger.info(f"Fetching line item with ID: {item_id} for beam line {beam_id}")

    # Check Redis
    if redis_client:
        key = f"beam_line:{beam_id}:line_item:{item_id}"
        data = await get_with_lock(
            redis_client,
            key,
            lambda: get_line_item_record(driver, beam_id, item_id),
            logger,
        )
    else:
        data = await get_line_item_record(driver, beam_id, item_id)

    if not data:
        raise HTTPException(
            status_code=404, detail="Beam line or target item does not exist"
        )

    # HTTP cache headers + ETag
    data_str = json.dumps(data, sort_keys=True)
    etag = f'"{hashlib.md5(data_str.encode()).hexdigest()}"'

    # Check if client has current version
    if request.headers.get("if-none-match") == etag:
        logger.info(
            f"Browser's cached value for line item with ID: {item_id} for "
            f"beam line {beam_id} matches retrieved value"
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
async def patch_line_item(
    beam_id: int,
    item_id: int,
    payload: LineItemUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
    # _token: str = Depends(require_admin),
):
    """Partially update a line item's name, description, and/or status.

    Only the fields present in *payload* are changed; omitted fields are left
    untouched.  Returns ``204 No Content`` on success.  Raises ``404`` when
    the beam line or item does not exist, and ``409`` when the new name is
    already taken.
    """
    logger.info(f"Updating line item with ID: {item_id} for beam line {beam_id}")

    data = payload.model_dump(exclude_none=True)
    if not data:
        return None

    records = update_line_item_record(driver, data, beam_id, item_id)
    if not records:
        raise HTTPException(
            status_code=404, detail="Beam line or target item does not exist"
        )

    # Invalidate redis cache
    if redis_client:
        key = f"beam_line:{beam_id}:line_item:{item_id}"
        await invalidate_redis_cache(redis_client, key, logger)

    return None


@router.delete("/{item_id}", status_code=204)
async def delete_line_item(
    beam_id: int,
    item_id: int,
    force: Annotated[bool, Query(...)] = False,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
    # _token: str = Depends(require_admin),
):
    """Delete a line item under a beam line by its ID.

    Returns ``204 No Content`` on success.  Raises ``404`` when the beam line
    does not exist.  Raises ``409`` when the item still has PREVIOUS, NEXT, or
    CONNECTED_TO relationships and *force* is ``False``; pass ``?force=true``
    to detach-delete the node together with all its relationships.  Returns
    ``204`` silently when the item itself does not exist.
    """
    logger.info(
        f"Deleting line item with ID: {item_id} for beam line {beam_id}, force: {force}"
    )

    records = get_line_item_relationships(driver, beam_id, item_id)
    if not records:
        return None

    linked_count = records[0]["linked_count"]
    if linked_count and not force:
        raise HTTPException(
            status_code=409,
            detail="Can't delete an item with a previous or next item; set force to true to override",
        )

    delete_line_item_record(driver, beam_id, item_id)

    # Invalidate redis cache
    if redis_client:
        key = f"beam_line:{beam_id}:line_item:{item_id}"
        await invalidate_redis_cache(redis_client, key, logger)

    return None
