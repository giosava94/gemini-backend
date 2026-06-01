from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from typing import Annotated
from app.db import run_query, find_by_id, exists_name
from app.schemas import (
    BeamLineCreate,
    BeamLineData,
    BeamLineDetailResponse,
    BeamLineListResponse,
    BeamLineUpdate,
)
from app.dependencies import get_driver

router = APIRouter(prefix="/api/v1/beam-lines", tags=["beam-lines"])


@router.post("", status_code=201)
def create_beam_line(
    payload: BeamLineCreate,
    driver: Driver = Depends(get_driver),
    # token: str = Depends(require_admin),
):
    """Create a new beam line."""
    name = payload.name
    if exists_name(driver, name):
        raise HTTPException(
            status_code=409, detail="Item with this name already exists"
        )
    query = (
        "MERGE (c:Counter {name: 'beamline'}) "
        "ON CREATE SET c.value = 0 "
        "SET c.value = c.value + 1 "
        "WITH c.value AS nextId "
        "CREATE (b:BeamLine {id: nextId, name: $name, description: $description}) "
        "RETURN b.id AS id"
    )
    records = run_query(
        driver, query, {"name": name, "description": payload.description}
    )
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
):
    """List beam lines with pagination and filtering."""
    if sort:
        for key in sort:
            if key != "name":
                raise HTTPException(status_code=422, detail=f"Invalid sort key: {key}")

    where_clause = "WHERE ($name IS NULL OR toLower(b.name) CONTAINS toLower($name))"
    count_query = f"MATCH (b:BeamLine) {where_clause} RETURN count(b) AS total"
    total_records = run_query(driver, count_query, {"name": name})
    total = total_records[0]["total"] if total_records else 0
    order_clause = "ORDER BY toLower(b.name)" if sort and "name" in sort else ""
    query = (
        f"MATCH (b:BeamLine) {where_clause} "
        f"RETURN b {order_clause} SKIP $skip LIMIT $limit"
    )
    skip = (page - 1) * per_page
    records = run_query(driver, query, {"name": name, "skip": skip, "limit": per_page})
    data = [
        BeamLineData(
            id=record["b"]["id"],
            name=record["b"]["name"],
            description=record["b"].get("description"),
        )
        for record in records
    ]
    return {"page": page, "per_page": per_page, "total": total, "data": data}


@router.get("/{beam_id}", response_model=BeamLineDetailResponse)
def get_beam_line(beam_id: int, driver: Driver = Depends(get_driver)):
    """Retrieve a specific beam line."""
    item = find_by_id(driver, beam_id)
    if not item:
        raise HTTPException(status_code=404, detail="Target item does not exist")
    links = {"line_items": f"/api/v1/beam-lines/{beam_id}/line-items"}
    data = {
        "id": item["id"],
        "name": item["name"],
        "description": item.get("description"),
    }
    return {"links": links, "data": data}


@router.delete("/{beam_id}", status_code=204)
def delete_beam_line(
    beam_id: int,
    force: Annotated[bool, Query(...)] = False,
    driver: Driver = Depends(get_driver),
    # token: Annotated[str, Depends(require_admin)] = Depends(require_admin),
):
    """Delete a beam line."""
    query = (
        "MATCH (b:BeamLine {id: $id}) "
        "OPTIONAL MATCH (b)-[r:HAS_LINE_ITEM]->(:LineItem) "
        "RETURN count(r) AS linked_count"
    )
    records = run_query(driver, query, {"id": beam_id})
    if not records:
        raise HTTPException(status_code=404, detail="Target item does not exist")
    linked_count = records[0]["linked_count"]
    if linked_count and not force:
        raise HTTPException(
            status_code=409,
            detail="Can't delete an item with line items; set force to true to override",
        )
    run_query(driver, "MATCH (b:BeamLine {id: $id}) DETACH DELETE b", {"id": beam_id})
    return None


@router.patch("/{beam_id}", status_code=204)
def patch_beam_line(
    beam_id: int,
    payload: BeamLineUpdate,
    driver: Driver = Depends(get_driver),
    # token: Annotated[str, Depends(require_admin)] = Depends(require_admin),
):
    """Update a beam line."""
    if payload.name and exists_name(driver, payload.name, exclude_id=beam_id):
        raise HTTPException(
            status_code=409, detail="An item with the same name already exists"
        )
    update_clauses: list[str] = []
    parameters: dict[str, object] = {"id": beam_id}
    if payload.name is not None:
        update_clauses.append("b.name = $name")
        parameters["name"] = payload.name
    if payload.description is not None:
        update_clauses.append("b.description = $description")
        parameters["description"] = payload.description
    if not update_clauses:
        return None
    query = f"MATCH (b:BeamLine {{id: $id}}) SET {', '.join(update_clauses)} RETURN b"
    records = run_query(driver, query, parameters)
    if not records:
        raise HTTPException(status_code=404, detail="Target item does not exist")
    return None
