from fastapi import Depends, Header, HTTPException, Request
from neo4j import Driver
from typing import Annotated
import logging


def get_driver_from_state(request: Request) -> Driver:
    """Retrieve the Neo4j driver from app state."""
    if not hasattr(request.app, "driver"):
        raise RuntimeError("Neo4j driver is not initialized")
    return request.app.driver


async def get_driver(request: Request) -> Driver:
    """Async dependency to get the Neo4j driver."""
    return get_driver_from_state(request)


def get_current_token(
    authorization: Annotated[str | None, Header(None)] = None,
) -> str | None:
    """Simple Authorization header extractor. Expects 'Bearer <token>' or None."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def require_admin(token: str | None = Depends(get_current_token)):
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if token != "admin-token":
        raise HTTPException(status_code=403, detail="Not authorized")
    return token


def get_logger(request: Request) -> logging.Logger:
    """Retrieve the application logger from app state."""
    if not hasattr(request.app, "logger"):
        raise RuntimeError("Logger is not initialized")
    return request.app.logger
