from fastapi import FastAPI
from app.schemas import HealthResponse, StatusEnum
from datetime import datetime, timezone

app = FastAPI(title="Gemini Backend", version="0.1.0")


@app.get("/api/v1/health", response_model=HealthResponse, summary="Get service's health status")
def get_health():
    """Inspect the service's health status and return a HealthResponse."""
    resp = HealthResponse(
        status=StatusEnum.HEALTHY,
        details={"message": "Service is running"},
        timestamp=datetime.now(timezone.utc),
    )
    return resp
