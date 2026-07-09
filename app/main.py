"""FastAPI application entry-point.

Creates the ``app`` instance, registers all routers, and wires up the
lifespan context manager that initialises (and tears down) the Neo4j driver
and the application logger.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import logging

import redis.asyncio as redis
from app.config import get_settings
from app.db import create_driver, close_driver, ensure_constraints
from app.routers.beam_lines import router as beam_line_router
from app.routers.line_items import router as line_item_router
from app.routers.line_item_adjacents import router as line_item_adjacents_router
from app.routers.line_item_connections import router as line_item_connections_router
from app.routers.items import router as item_router
from app.routers.item_connections import router as item_connections_router
from app.schemas import HealthResponse, StatusEnum
from datetime import datetime, timezone


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown."""
    # Startup
    settings = get_settings()

    # Initialize logger
    logger = logging.getLogger("gemini_backend")
    logger.setLevel(settings.log_level.upper())
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    app.logger = logger  # pyright: ignore[reportAttributeAccessIssue]
    logger.info("Application starting up...")

    # Initialize database driver
    driver = create_driver()
    ensure_constraints(driver)
    app.driver = driver  # pyright: ignore[reportAttributeAccessIssue]

    # Initialize Redis client
    redis_client = None
    if settings.redis_enabled:
        redis_client = redis.Redis(host=settings.redis_host, decode_responses=True)
        try:
            await redis_client.ping()
            logger.info("Redis client initialized and connected")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            redis_client = None
    app.redis_client = redis_client  # pyright: ignore[reportAttributeAccessIssue]

    logger.info("Application startup complete")
    yield

    # Shutdown
    logger.info("Application shutting down")

    close_driver(driver)

    if redis_client:
        await redis_client.close()


app = FastAPI(title="Gemini Backend", version="0.1.0", lifespan=lifespan)
app.include_router(beam_line_router)
app.include_router(line_item_router)
app.include_router(line_item_adjacents_router)
app.include_router(line_item_connections_router)
app.include_router(item_router)
app.include_router(item_connections_router)


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Get service's health status",
    tags=["health"],
)
def get_health(request: Request):
    """Return the service health status.

    Pings the Neo4j database to verify connectivity.  Returns
    ``HEALTHY`` when the database is reachable, ``NOT_HEALTHY`` otherwise.

    Args:
        request: The incoming FastAPI request, used to access the shared
            Neo4j driver attached to ``request.app.driver``.

    Returns:
        HealthResponse: Current status, optional detail message, and a
        UTC timestamp.

    Example response (healthy)::

        {
            "status": "HEALTHY",
            "details": {"message": "Service is running"},
            "timestamp": "2024-01-01T00:00:00Z"
        }

    Example response (unhealthy)::

        {
            "status": "NOT_HEALTHY",
            "details": {
                "message": "Connection with the database is down",
                "error": "<exception detail>"
            },
            "timestamp": "2024-01-01T00:00:00Z"
        }
    """
    try:
        driver = request.app.driver
        driver.verify_connectivity()
        resp = HealthResponse(
            status=StatusEnum.HEALTHY,
            details={"message": "Service is running"},
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as error:
        resp = HealthResponse(
            status=StatusEnum.NOT_HEALTHY,
            details={
                "message": "Connection with the database is down",
                "error": str(error),
            },
            timestamp=datetime.now(timezone.utc),
        )
    return resp
