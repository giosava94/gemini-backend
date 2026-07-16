"""Tests for the line-item-kinds REST API endpoints.

These tests exercise the HTTP layer only — all CRUD functions are patched so
no real Neo4j instance is required.
"""

from unittest.mock import MagicMock, patch

BASE = "/api/v1/line-item-kinds"


# ---------------------------------------------------------------------------
# POST /api/v1/line-item-kinds
# ---------------------------------------------------------------------------


class TestCreateKind:
    def test_create_success(self, client, admin_headers):
        """201 and the kind name are returned when the name is unique."""
        with (
            patch(
                "app.routers.line_item_kinds.line_item_kind_exists", return_value=False
            ),
            patch(
                "app.routers.line_item_kinds.create_line_item_kind",
                return_value=[{"name": "Wien Filter"}],
            ),
        ):
            r = client.post(BASE, json={"name": "Wien Filter"}, headers=admin_headers)
        assert r.status_code == 201
        assert r.json() == {"name": "Wien Filter"}

    def test_create_conflict(self, client, admin_headers):
        """409 is returned when a kind with the same name already exists."""
        with patch(
            "app.routers.line_item_kinds.line_item_kind_exists", return_value=True
        ):
            r = client.post(BASE, json={"name": "Diagnostic"}, headers=admin_headers)
        assert r.status_code == 409

    def test_create_db_failure(self, client, admin_headers):
        """500 is raised when the CRUD function returns an empty list."""
        with (
            patch(
                "app.routers.line_item_kinds.line_item_kind_exists", return_value=False
            ),
            patch("app.routers.line_item_kinds.create_line_item_kind", return_value=[]),
        ):
            r = client.post(BASE, json={"name": "NewKind"}, headers=admin_headers)
        assert r.status_code == 500

    def test_create_empty_name_rejected(self, client, admin_headers):
        """422 is returned when name is an empty string (schema validation)."""
        r = client.post(BASE, json={"name": ""}, headers=admin_headers)
        assert r.status_code == 422

    def test_create_missing_name_rejected(self, client, admin_headers):
        """422 is returned when the required name field is absent."""
        r = client.post(BASE, json={}, headers=admin_headers)
        assert r.status_code == 422

    def test_create_calls_crud_with_correct_name(self, client, admin_headers):
        """The CRUD create function is called with the exact name from the request."""
        mock_create = MagicMock(return_value=[{"name": "My Kind"}])
        with (
            patch(
                "app.routers.line_item_kinds.line_item_kind_exists", return_value=False
            ),
            patch("app.routers.line_item_kinds.create_line_item_kind", mock_create),
        ):
            client.post(BASE, json={"name": "My Kind"}, headers=admin_headers)
        mock_create.assert_called_once()
        assert mock_create.call_args[0][1] == "My Kind"

    def test_create_preserves_case(self, client, admin_headers):
        """Kind names are stored with the exact casing supplied by the client."""
        with (
            patch(
                "app.routers.line_item_kinds.line_item_kind_exists", return_value=False
            ),
            patch(
                "app.routers.line_item_kinds.create_line_item_kind",
                return_value=[{"name": "ES Quadrupole"}],
            ),
        ):
            r = client.post(BASE, json={"name": "ES Quadrupole"}, headers=admin_headers)
        assert r.json()["name"] == "ES Quadrupole"


# ---------------------------------------------------------------------------
# GET /api/v1/line-item-kinds
# ---------------------------------------------------------------------------


class TestListKinds:
    def test_list_empty(self, client):
        """200 with empty data and total=0 when no kinds have been registered."""
        with patch(
            "app.routers.line_item_kinds.get_all_line_item_kinds", return_value=[]
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []

    def test_list_with_results(self, client):
        """200 with data list and total reflecting the number of kinds."""
        kinds = [{"name": "Diagnostic"}, {"name": "Wien Filter"}]
        with patch(
            "app.routers.line_item_kinds.get_all_line_item_kinds", return_value=kinds
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert body["data"] == kinds

    def test_list_total_matches_data_length(self, client):
        """The total field always equals the length of the data list."""
        kinds = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
        with patch(
            "app.routers.line_item_kinds.get_all_line_item_kinds", return_value=kinds
        ):
            r = client.get(BASE)
        body = r.json()
        assert body["total"] == len(body["data"])

    def test_list_returns_name_field(self, client):
        """Each item in data carries a 'name' key."""
        with patch(
            "app.routers.line_item_kinds.get_all_line_item_kinds",
            return_value=[{"name": "Diagnostic"}],
        ):
            r = client.get(BASE)
        assert "name" in r.json()["data"][0]


# ---------------------------------------------------------------------------
# DELETE /api/v1/line-item-kinds/{name}
# ---------------------------------------------------------------------------


class TestDeleteKind:
    def test_delete_success(self, client, admin_headers):
        """204 is returned when the kind exists and is not in use."""
        with (
            patch(
                "app.routers.line_item_kinds.line_item_kind_exists", return_value=True
            ),
            patch(
                "app.routers.line_item_kinds.line_item_kind_in_use", return_value=False
            ),
            patch("app.routers.line_item_kinds.delete_line_item_kind", return_value=[]),
        ):
            r = client.delete(f"{BASE}/Diagnostic", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_not_found(self, client, admin_headers):
        """404 is returned when the kind does not exist."""
        with patch(
            "app.routers.line_item_kinds.line_item_kind_exists", return_value=False
        ):
            r = client.delete(f"{BASE}/Unknown", headers=admin_headers)
        assert r.status_code == 404

    def test_delete_conflict_kind_in_use(self, client, admin_headers):
        """409 is returned when the kind is still referenced by line items."""
        with (
            patch(
                "app.routers.line_item_kinds.line_item_kind_exists", return_value=True
            ),
            patch(
                "app.routers.line_item_kinds.line_item_kind_in_use", return_value=True
            ),
        ):
            r = client.delete(f"{BASE}/Diagnostic", headers=admin_headers)
        assert r.status_code == 409

    def test_delete_calls_crud_once(self, client, admin_headers):
        """The CRUD delete function is called exactly once on a successful delete."""
        mock_delete = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.line_item_kinds.line_item_kind_exists", return_value=True
            ),
            patch(
                "app.routers.line_item_kinds.line_item_kind_in_use", return_value=False
            ),
            patch("app.routers.line_item_kinds.delete_line_item_kind", mock_delete),
        ):
            client.delete(f"{BASE}/Diagnostic", headers=admin_headers)
        mock_delete.assert_called_once()

    def test_delete_passes_correct_name(self, client, admin_headers):
        """The CRUD delete function receives the name from the URL path."""
        mock_delete = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.line_item_kinds.line_item_kind_exists", return_value=True
            ),
            patch(
                "app.routers.line_item_kinds.line_item_kind_in_use", return_value=False
            ),
            patch("app.routers.line_item_kinds.delete_line_item_kind", mock_delete),
        ):
            client.delete(f"{BASE}/Wien%20Filter", headers=admin_headers)
        assert mock_delete.call_args[0][1] == "Wien Filter"
