"""Tests for the non-line items CRUD endpoints."""

from unittest.mock import MagicMock, patch


BASE = "/api/v1/items"

VALID_PAYLOAD = {
    "name": "RACK-01",
    "kind": "Rack",
    "status": 0,
    "connections": [],
}


def _make_item_record(iid, name, kind="Rack", status=0, desc=None):
    node = MagicMock()
    node.__getitem__ = lambda s, k: {
        "id": iid,
        "name": name,
        "kind": kind,
        "status": status,
    }[k]
    node.get = lambda k, d=None: desc if k == "description" else d
    return {"i": node}


# ---------------------------------------------------------------------------
# POST /api/v1/items
# ---------------------------------------------------------------------------


class TestCreateItem:
    def test_create_success(self, client, admin_headers):
        with (
            patch("app.routers.items.exists_any_name", return_value=False),
            patch("app.routers.items.run_query", return_value=[{"id": 42}]),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 201
        assert r.json() == {"id": 42}

    def test_create_conflict(self, client, admin_headers):
        with patch("app.routers.items.exists_any_name", return_value=True):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 409

    def test_create_connection_not_found(self, client, admin_headers):
        with (
            patch("app.routers.items.exists_any_name", return_value=False),
            patch("app.routers.items.run_query", return_value=[{"all_exist": False}]),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "connections": [999]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_create_db_failure(self, client, admin_headers):
        with (
            patch("app.routers.items.exists_any_name", return_value=False),
            patch("app.routers.items.run_query", return_value=[]),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 500

    def test_create_invalid_kind(self, client, admin_headers):
        r = client.post(
            BASE,
            json={**VALID_PAYLOAD, "kind": "Unknown"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_create_empty_name_rejected(self, client, admin_headers):
        r = client.post(BASE, json={**VALID_PAYLOAD, "name": ""}, headers=admin_headers)
        assert r.status_code == 422

    def test_create_with_connections_success(self, client, admin_headers):
        with (
            patch("app.routers.items.exists_any_name", return_value=False),
            patch("app.routers.items._ids_exist", return_value=True),
            patch("app.routers.items.run_query", return_value=[{"id": 5}]),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "connections": [1, 2]},
                headers=admin_headers,
            )
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/items
# ---------------------------------------------------------------------------


class TestListItems:
    def test_list_empty(self, client):
        with patch(
            "app.routers.items.run_query",
            side_effect=[
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_with_results(self, client):
        record = _make_item_record(42, "RACK-01")
        with patch(
            "app.routers.items.run_query",
            side_effect=[
                [{"total": 1}],
                [record],
            ],
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 42

    def test_list_invalid_sort(self, client):
        r = client.get(f"{BASE}?sort=invalid")
        assert r.status_code == 422

    def test_list_sort_by_name(self, client):
        with patch(
            "app.routers.items.run_query",
            side_effect=[
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?sort=name")
        assert r.status_code == 200

    def test_list_sort_by_kind(self, client):
        with patch(
            "app.routers.items.run_query",
            side_effect=[
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?sort=kind")
        assert r.status_code == 200

    def test_list_name_filter(self, client):
        with patch(
            "app.routers.items.run_query",
            side_effect=[
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?name=rack")
        assert r.status_code == 200

    def test_list_pagination(self, client):
        with patch(
            "app.routers.items.run_query",
            side_effect=[
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?page=3&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 3
        assert body["per_page"] == 5


# ---------------------------------------------------------------------------
# GET /api/v1/items/{item_id}
# ---------------------------------------------------------------------------


class TestGetItem:
    def test_get_success(self, client):
        record = _make_item_record(42, "RACK-01")
        with patch("app.routers.items.run_query", return_value=[record]):
            r = client.get(f"{BASE}/42")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["id"] == 42
        assert "connections" in body["links"]

    def test_get_not_found(self, client):
        with patch("app.routers.items.run_query", return_value=[]):
            r = client.get(f"{BASE}/999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/items/{item_id}
# ---------------------------------------------------------------------------


class TestPatchItem:
    def test_patch_name_success(self, client, admin_headers):
        with (
            patch("app.routers.items.exists_any_name", return_value=False),
            patch("app.routers.items.run_query", return_value=[{"id": 42}]),
        ):
            r = client.patch(
                f"{BASE}/42",
                json={"name": "RACK-01-NEW"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_name_conflict(self, client, admin_headers):
        with patch("app.routers.items.exists_any_name", return_value=True):
            r = client.patch(
                f"{BASE}/42", json={"name": "Taken"}, headers=admin_headers
            )
        assert r.status_code == 409

    def test_patch_not_found(self, client, admin_headers):
        with (
            patch("app.routers.items.exists_any_name", return_value=False),
            patch("app.routers.items.run_query", return_value=[]),
        ):
            r = client.patch(f"{BASE}/999", json={"name": "X"}, headers=admin_headers)
        assert r.status_code == 404

    def test_patch_no_fields_noop(self, client, admin_headers):
        r = client.patch(f"{BASE}/42", json={}, headers=admin_headers)
        assert r.status_code == 204

    def test_patch_status(self, client, admin_headers):
        with (
            patch("app.routers.items.exists_any_name", return_value=False),
            patch("app.routers.items.run_query", return_value=[{"id": 42}]),
        ):
            r = client.patch(f"{BASE}/42", json={"status": 2}, headers=admin_headers)
        assert r.status_code == 204

    def test_patch_description(self, client, admin_headers):
        with (
            patch("app.routers.items.exists_any_name", return_value=False),
            patch("app.routers.items.run_query", return_value=[{"id": 42}]),
        ):
            r = client.patch(
                f"{BASE}/42",
                json={"description": "updated"},
                headers=admin_headers,
            )
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# DELETE /api/v1/items/{item_id}
# ---------------------------------------------------------------------------


class TestDeleteItem:
    def test_delete_success_no_links(self, client, admin_headers):
        with patch(
            "app.routers.items.run_query",
            side_effect=[
                [{"id": 42, "linked_count": 0}],
                [],
            ],
        ):
            r = client.delete(f"{BASE}/42", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_conflict_has_links(self, client, admin_headers):
        with patch(
            "app.routers.items.run_query", return_value=[{"id": 42, "linked_count": 1}]
        ):
            r = client.delete(f"{BASE}/42", headers=admin_headers)
        assert r.status_code == 409

    def test_delete_force(self, client, admin_headers):
        with patch(
            "app.routers.items.run_query",
            side_effect=[
                [{"id": 42, "linked_count": 1}],
                [],
            ],
        ):
            r = client.delete(f"{BASE}/42?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_not_found_silent(self, client, admin_headers):
        """Non-existent item returns 204 silently."""
        with patch(
            "app.routers.items.run_query",
            return_value=[{"id": None, "linked_count": 0}],
        ):
            r = client.delete(f"{BASE}/999", headers=admin_headers)
        assert r.status_code == 204
