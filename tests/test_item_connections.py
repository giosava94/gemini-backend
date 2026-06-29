"""Tests for the non-line item connections endpoints."""

from unittest.mock import MagicMock, patch


CONN_BASE = "/api/v1/items/42/connections"
LI_CONN_BASE = "/api/v1/items/42/line-item-connections"


def _conn_record(cid, name, desc=None):
    node = MagicMock()
    node.__getitem__ = lambda s, k: {"id": cid, "name": name}[k]
    node.get = lambda k, d=None: desc if k == "description" else d
    return {"conn": node, "conn_labels": ["Item"]}


def _li_conn_record(lid, name, beam_id=1, desc=None):
    node = MagicMock()
    node.__getitem__ = lambda s, k: {"id": lid, "name": name}[k]
    node.get = lambda k, d=None: desc if k == "description" else d
    return {"li": node, "beam_id": beam_id}


# ---------------------------------------------------------------------------
# PUT  /api/v1/items/{item_id}/connections
# ---------------------------------------------------------------------------


class TestPutItemConnections:
    def test_put_success(self, client, admin_headers):
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],  # item exists
                [{"all_exist": True}],  # targets exist
                [],  # merge
            ],
        ):
            r = client.put(CONN_BASE, json={"items": [10]}, headers=admin_headers)
        assert r.status_code == 201

    def test_put_self_reference(self, client, admin_headers):
        r = client.put(CONN_BASE, json={"items": [42]}, headers=admin_headers)
        assert r.status_code == 400

    def test_put_duplicate_items(self, client, admin_headers):
        r = client.put(CONN_BASE, json={"items": [10, 10]}, headers=admin_headers)
        assert r.status_code == 400

    def test_put_item_not_found(self, client, admin_headers):
        with patch("app.routers.item_connections.run_query", return_value=[]):
            r = client.put(CONN_BASE, json={"items": [10]}, headers=admin_headers)
        assert r.status_code == 404

    def test_put_target_not_found(self, client, admin_headers):
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],
                [{"all_exist": False}],
            ],
        ):
            r = client.put(CONN_BASE, json={"items": [999]}, headers=admin_headers)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET  /api/v1/items/{item_id}/connections
# ---------------------------------------------------------------------------


class TestListItemConnections:
    def test_list_success(self, client):
        record = _conn_record(10, "RACK-01")
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],
                [{"total": 1}],
                [record],
            ],
        ):
            r = client.get(CONN_BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 10

    def test_list_item_not_found(self, client):
        with patch("app.routers.item_connections.run_query", return_value=[]):
            r = client.get(CONN_BASE)
        assert r.status_code == 404

    def test_list_empty(self, client):
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(CONN_BASE)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_pagination(self, client):
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{CONN_BASE}?page=2&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 5


# ---------------------------------------------------------------------------
# DELETE  /api/v1/items/{item_id}/connections
# ---------------------------------------------------------------------------


class TestDeleteItemConnections:
    def test_delete_success(self, client, admin_headers):
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],
                [],
            ],
        ):
            r = client.request(
                "DELETE",
                CONN_BASE,
                json={"items": [10]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_delete_duplicate_ids(self, client, admin_headers):
        r = client.request(
            "DELETE",
            CONN_BASE,
            json={"items": [10, 10]},
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_delete_item_not_found(self, client, admin_headers):
        with patch("app.routers.item_connections.run_query", return_value=[]):
            r = client.request(
                "DELETE",
                CONN_BASE,
                json={"items": [10]},
                headers=admin_headers,
            )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET  /api/v1/items/{item_id}/line-item-connections
# ---------------------------------------------------------------------------


class TestListItemLineItemConnections:
    def test_list_success(self, client):
        record = _li_conn_record(5, "QD01", beam_id=1)
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],
                [{"total": 1}],
                [record],
            ],
        ):
            r = client.get(LI_CONN_BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 5
        assert "/beam-lines/1/line-items/5" in body["data"][0]["link"]

    def test_list_item_not_found(self, client):
        with patch("app.routers.item_connections.run_query", return_value=[]):
            r = client.get(LI_CONN_BASE)
        assert r.status_code == 404

    def test_list_empty(self, client):
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(LI_CONN_BASE)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_pagination(self, client):
        with patch(
            "app.routers.item_connections.run_query",
            side_effect=[
                [{"id": 42}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{LI_CONN_BASE}?page=2&per_page=20")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 20
