from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import logging
from app.config import get_settings
from app.db import create_driver, close_driver, ensure_constraints
from app.routers.beam_lines import router as beam_line_router
from app.routers.line_items import router as line_item_router
from app.routers.line_item_adjacents import router as line_item_adjacents_router
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

    logger.info("Application startup complete")
    yield

    # Shutdown
    logger.info("Application shutting down")
    close_driver(driver)


app = FastAPI(title="Gemini Backend", version="0.1.0", lifespan=lifespan)
app.include_router(beam_line_router)
app.include_router(line_item_router)
app.include_router(line_item_adjacents_router)


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Get service's health status",
    tags=["health"],
)
def get_health(request: Request):
    """Inspect the service's health status and return a HealthResponse."""
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
