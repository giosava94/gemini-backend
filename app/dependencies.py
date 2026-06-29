from fastapi import Depends, Header, HTTPException, Request
from neo4j import Driver
from typing import Annotated
import logging


def get_driver_from_state(request: Request) -> Driver:
    """Retrieve the Neo4j driver stored on the FastAPI application state.

    :raises RuntimeError: If the driver has not been initialised yet.
    """
    if not hasattr(request.app, "driver"):
        raise RuntimeError("Neo4j driver is not initialized")
    return request.app.driver


async def get_driver(request: Request) -> Driver:
    """FastAPI dependency that returns the Neo4j driver from application state."""
    return get_driver_from_state(request)


def get_current_token(
    authorization: Annotated[str | None, Header(None)] = None,
) -> str | None:
    """Extract a Bearer token from the ``Authorization`` header.

    Returns the raw token string when the header is present and well-formed
    (``Bearer <token>``), or ``None`` otherwise.
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def require_admin(token: str | None = Depends(get_current_token)):
    """FastAPI dependency that enforces admin-level authentication.

    Raises ``401 Unauthorized`` when no token is present, and
    ``403 Forbidden`` when the token does not match the expected admin token.
    Returns the validated token string on success.
    """
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if token != "admin-token":
        raise HTTPException(status_code=403, detail="Not authorized")
    return token


def get_logger(request: Request) -> logging.Logger:
    """FastAPI dependency that returns the application logger from app state.

    :raises RuntimeError: If the logger has not been initialised yet.
    """
    if not hasattr(request.app, "logger"):
        raise RuntimeError("Logger is not initialized")
    return request.app.logger
