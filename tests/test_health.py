from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_endpoint():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("HEALTHY", "NOT_HEALTHY")
    assert isinstance(body["details"], dict)
    assert "timestamp" in body
