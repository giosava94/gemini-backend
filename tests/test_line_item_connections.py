"""Tests for the line-item connections endpoints."""

from unittest.mock import MagicMock, patch


BASE = "/api/v1/beam-lines/1/line-items/10/connections"


def _conn_record(cid, name, desc=None):
    node = MagicMock()
    node.__getitem__ = lambda s, k: {"id": cid, "name": name}[k]
    node.get = lambda k, d=None: desc if k == "description" else d
    return {"conn": node}


# ---------------------------------------------------------------------------
# GET  …/connections
# ---------------------------------------------------------------------------


class TestListLineItemConnections:
    def test_list_success(self, client):
        record = _conn_record(30, "RACK-01")
        with patch(
            "app.routers.line_item_connections.run_query",
            side_effect=[
                [{"id": 10}],  # item exists
                [{"total": 1}],  # count
                [record],  # data
            ],
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 30
        assert body["data"][0]["link"] == "/api/v1/items/30"

    def test_list_item_not_found(self, client):
        with patch("app.routers.line_item_connections.run_query", return_value=[]):
            r = client.get(BASE)
        assert r.status_code == 404

    def test_list_empty(self, client):
        with patch(
            "app.routers.line_item_connections.run_query",
            side_effect=[
                [{"id": 10}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_pagination(self, client):
        with patch(
            "app.routers.line_item_connections.run_query",
            side_effect=[
                [{"id": 10}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?page=2&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 5


# ---------------------------------------------------------------------------
# PUT  …/connections
# ---------------------------------------------------------------------------


class TestPutLineItemConnections:
    def test_put_success(self, client, admin_headers):
        with patch(
            "app.routers.line_item_connections.run_query",
            side_effect=[
                [{"id": 10}],  # line item exists
                [{"all_exist": True}],  # targets exist
                [],  # merge
            ],
        ):
            r = client.put(BASE, json={"items": [30]}, headers=admin_headers)
        assert r.status_code == 201

    def test_put_duplicate_items(self, client, admin_headers):
        r = client.put(BASE, json={"items": [30, 30]}, headers=admin_headers)
        assert r.status_code == 400

    def test_put_line_item_not_found(self, client, admin_headers):
        with patch("app.routers.line_item_connections.run_query", return_value=[]):
            r = client.put(BASE, json={"items": [30]}, headers=admin_headers)
        assert r.status_code == 404

    def test_put_target_not_found(self, client, admin_headers):
        with patch(
            "app.routers.line_item_connections.run_query",
            side_effect=[
                [{"id": 10}],
                [{"all_exist": False}],
            ],
        ):
            r = client.put(BASE, json={"items": [999]}, headers=admin_headers)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE  …/connections
# ---------------------------------------------------------------------------


class TestDeleteLineItemConnections:
    def test_delete_success(self, client, admin_headers):
        with patch(
            "app.routers.line_item_connections.run_query",
            side_effect=[
                [{"id": 10}],  # item exists
                [],  # delete
            ],
        ):
            r = client.request(
                "DELETE",
                BASE,
                json={"items": [30]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_delete_duplicate_ids(self, client, admin_headers):
        r = client.request(
            "DELETE",
            BASE,
            json={"items": [30, 30]},
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_delete_item_not_found(self, client, admin_headers):
        with patch("app.routers.line_item_connections.run_query", return_value=[]):
            r = client.request(
                "DELETE",
                BASE,
                json={"items": [30]},
                headers=admin_headers,
            )
        assert r.status_code == 404
