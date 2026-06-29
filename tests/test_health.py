"""Tests for the /api/v1/health endpoint."""

from app.main import app


def test_health_healthy(client):
    """Returns HEALTHY when the driver connectivity check succeeds."""
    # The mock driver verify_connectivity does nothing (no exception) by default
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "HEALTHY"
    assert body["details"] == {"message": "Service is running"}
    assert "timestamp" in body


def test_health_not_healthy(client):
    """Returns NOT_HEALTHY when the driver connectivity check raises."""
    app.driver.verify_connectivity.side_effect = Exception("connection refused")
    try:
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "NOT_HEALTHY"
        assert "Connection with the database is down" in body["details"]["message"]
        assert "connection refused" in body["details"]["error"]
    finally:
        app.driver.verify_connectivity.side_effect = None
