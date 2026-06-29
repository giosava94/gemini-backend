"""Shared pytest fixtures for the gemini-backend test suite.

All routes depend on a Neo4j driver stored in ``app.driver`` and a logger
stored in ``app.logger``.  Rather than spinning up a real database the tests
patch the db helper functions (``run_query``, ``find_by_id``,
``exists_any_name``) and inject a mock driver / logger so that every route
can be exercised without any external infrastructure.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Module-level patches applied for the whole session
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_db_setup():
    """Prevent the real Neo4j driver from being created during the lifespan.

    Patches ``create_driver``, ``close_driver``, and ``ensure_constraints``
    so the TestClient can start the application without a live database.
    """
    mock_driver = MagicMock()
    mock_driver.verify_connectivity.return_value = None

    with (
        patch("app.main.create_driver", return_value=mock_driver),
        patch("app.main.close_driver", return_value=None),
        patch("app.main.ensure_constraints", return_value=None),
    ):
        yield mock_driver


@pytest.fixture()
def client(mock_db_setup):
    """Return a TestClient with a fully booted app (lifespan executed)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_headers():
    """Return HTTP headers that satisfy the admin-token check."""
    return {
        "Authorization": "Bearer admin-token",
        "Content-Type": "application/json",
    }
