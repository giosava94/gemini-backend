from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import create_driver, close_driver, ensure_constraints
from app.routers.beam_lines import router as beam_line_router
from app.schemas import HealthResponse, StatusEnum
from datetime import datetime, timezone


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown."""
    # Startup
    driver = create_driver()
    ensure_constraints(driver)
    app.driver = driver # pyright: ignore[reportAttributeAccessIssue]
    yield
    # Shutdown
    close_driver(driver)


app = FastAPI(title="Gemini Backend", version="0.1.0", lifespan=lifespan)
app.include_router(beam_line_router)


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Get service's health status",
)
def get_health():
    """Inspect the service's health status and return a HealthResponse."""
    resp = HealthResponse(
        status=StatusEnum.HEALTHY,
        details={"message": "Service is running"},
        timestamp=datetime.now(timezone.utc),
    )
    return resp
