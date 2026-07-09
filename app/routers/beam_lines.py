import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from neo4j import Driver
from typing import Annotated
import logging
import redis.asyncio as redis
from app.config import get_settings
from app.redis import get_with_lock, invalidate_redis_cache
from app.schemas.beam_lines import (
    BeamLineCreate,
    BeamLineDetailResponse,
    BeamLineListResponse,
    BeamLineUpdate,
)
from app.dependencies import (
    check_name_uniqueness,
    get_driver,
    get_logger,
    get_redis_client,
)
from app.cruds.beam_lines import (
    create_beam_line_record,
    delete_beam_line_record,
    get_beam_line_records,
    get_beam_line_relationships,
    get_total_beam_line_records,
    get_beam_line_record,
    update_beam_line_record,
)
from app.schemas.beam_lines import BeamLineCreateResponse

router = APIRouter(prefix="/api/v1/beam-lines", tags=["beam-lines"])


@router.post(
    "",
    status_code=201,
    response_model=BeamLineCreateResponse,
    dependencies=[Depends(check_name_uniqueness)],
)
def create_beam_line(
    payload: BeamLineCreate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    # token: str = Depends(require_admin),
):
    """Create a new beam line.

    Returns the auto-generated ID of the created node.  Raises ``409`` when
    a BeamLine, LineItem, or Item with the same name already exists (names
    are unique across all node types).

    Example request body::

        {"name": "LEBT", "description": "Low Energy Beam Transport"}

    Example response::

        {"id": 1}
    """
    logger.info(f"Creating beam line with name: {payload.name}")

    records = create_beam_line_record(driver, payload)
    if not records:
        raise HTTPException(status_code=500, detail="Failed to create beam line")

    return {"id": records[0]["id"]}


@router.get("", response_model=BeamLineListResponse)
def list_beam_lines(
    page: Annotated[int, Query(..., ge=1)] = 1,
    per_page: Annotated[int, Query(..., ge=1, le=100)] = 10,
    sort: Annotated[list[str] | None, Query(...)] = None,
    name: Annotated[str | None, Query(...)] = None,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
):
    """Return a paginated list of beam lines with optional filtering and sorting.

    :param page: 1-based page number.
    :param per_page: Number of results per page (1-100).
    :param sort: Optional list of sort keys; only ``"name"`` is accepted.
    :param name: Optional case-insensitive substring filter on the beam line name.

    Raises ``422`` when an unsupported sort key is supplied.

    Example: ``GET /api/v1/beam-lines?page=1&per_page=5&sort=name&name=lebt``
    """
    logger.info(
        f"Listing beam lines - page: {page}, per_page: {per_page}, name filter: {name}"
    )

    if sort:
        for key in sort:
            if key != "name":
                raise HTTPException(status_code=422, detail=f"Invalid sort key: {key}")

    params = {"name": name}
    total = get_total_beam_line_records(driver, params)
    data = get_beam_line_records(
        driver, params, sort=sort, page=page, per_page=per_page
    )
    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.get("/{beam_id}", response_model=BeamLineDetailResponse)
async def get_beam_line(
    request: Request,
    beam_id: int,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
):
    """Retrieve a single beam line by its ID.

    Returns the beam line data along with a ``links`` object that points to
    the related line items resource.  Raises ``404`` when no BeamLine with
    *beam_id* exists.
    """
    logger.info(f"Fetching beam line with ID: {beam_id}")

    # Check Redis
    if redis_client:
        key = f"beam_line:{beam_id}"
        data = await get_with_lock(
            redis_client, key, lambda: get_beam_line_record(driver, beam_id), logger
        )
    else:
        data = await get_beam_line_record(driver, beam_id)

    if not data:
        raise HTTPException(status_code=404, detail="Target item does not exist")

    # HTTP cache headers + ETag
    data_str = json.dumps(data, sort_keys=True)
    etag = f'"{hashlib.md5(data_str.encode()).hexdigest()}"'

    # Check if client has current version
    if request.headers.get("if-none-match") == etag:
        logger.info(
            f"Browser's cached value for beam line with ID {beam_id} matches retrieved value"
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
    "/{beam_id}",
    status_code=204,
    dependencies=[Depends(check_name_uniqueness)],
)
async def patch_beam_line(
    beam_id: int,
    payload: BeamLineUpdate,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
    # token: Annotated[str, Depends(require_admin)] = Depends(require_admin),
):
    """Partially update a beam line's name and/or description.

    Only the fields present in *payload* are changed; omitted fields are left
    untouched.  Returns ``204 No Content`` on success.  Raises ``404`` when
    the beam line does not exist, and ``409`` when the requested name is
    already taken by another node.
    """
    logger.info(f"Updating beam line with ID: {beam_id}")

    if not payload.model_dump():
        return None

    records = update_beam_line_record(driver, payload, beam_id)
    if not records:
        raise HTTPException(status_code=404, detail="Target item does not exist")

    # Invalidate redis cache
    if redis_client:
        key = f"beam_line:{beam_id}"
        await invalidate_redis_cache(redis_client, key, logger)

    return None


@router.delete("/{beam_id}", status_code=204)
async def delete_beam_line(
    beam_id: int,
    force: Annotated[bool, Query(...)] = False,
    driver: Driver = Depends(get_driver),
    logger: logging.Logger = Depends(get_logger),
    redis_client: redis.Redis | None = Depends(get_redis_client),
    # token: Annotated[str, Depends(require_admin)] = Depends(require_admin),
):
    """Delete a beam line by its ID.

    Returns ``204 No Content`` on success.  Raises ``404`` when the beam line
    does not exist.  Raises ``409`` when the beam line still has associated
    line items and *force* is ``False``; pass ``?force=true`` to detach-delete
    the node together with all its relationships.
    """
    logger.info(f"Deleting beam line with ID: {beam_id}, force: {force}")

    records = get_beam_line_relationships(driver, beam_id)
    if not records:
        return None

    linked_count = records[0]["linked_count"]
    if linked_count and not force:
        raise HTTPException(
            status_code=409,
            detail="Can't delete an item with line items; set force to true to override",
        )

    delete_beam_line_record(driver, beam_id)

    # Invalidate redis cache
    if redis_client:
        key = f"beam_line:{beam_id}"
        await invalidate_redis_cache(redis_client, key, logger)

    return None
