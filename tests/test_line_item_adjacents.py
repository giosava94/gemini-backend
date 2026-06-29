"""Tests for the line-item adjacents endpoints."""

from unittest.mock import MagicMock, patch


BASE = "/api/v1/beam-lines/1/line-items/10/adjacents"


def _adj_record(aid, name, position, index=None, desc=None):
    """Build a fake Neo4j record for an adjacent line item."""
    node = MagicMock()
    node.__getitem__ = lambda s, k: {"id": aid, "name": name}[k]
    node.get = lambda k, d=None: desc if k == "description" else d
    return {"adj": node, "position": position, "index": index}


# ---------------------------------------------------------------------------
# GET  …/adjacents
# ---------------------------------------------------------------------------


class TestListAdjacents:
    def test_list_success(self, client):
        record = _adj_record(20, "QD02", "Previous")
        with patch(
            "app.routers.line_item_adjacents.run_query",
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
        assert body["data"][0]["id"] == 20
        assert body["data"][0]["position"] == "Previous"

    def test_list_item_not_found(self, client):
        with patch("app.routers.line_item_adjacents.run_query", return_value=[]):
            r = client.get(BASE)
        assert r.status_code == 404

    def test_list_invalid_sort_key(self, client):
        with patch(
            "app.routers.line_item_adjacents.run_query", return_value=[{"id": 10}]
        ):
            r = client.get(f"{BASE}?sort=invalid")
        assert r.status_code == 422

    def test_list_filter_by_position(self, client):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"id": 10}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?position=previous")
        assert r.status_code == 200

    def test_list_invalid_position(self, client):
        with patch(
            "app.routers.line_item_adjacents.run_query", return_value=[{"id": 10}]
        ):
            r = client.get(f"{BASE}?position=invalid")
        assert r.status_code == 422

    def test_list_sort_by_position(self, client):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"id": 10}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?sort=position")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# PUT  …/adjacents
# ---------------------------------------------------------------------------


class TestPutAdjacents:
    def test_put_success(self, client, admin_headers):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"all_targets_exist": True}],  # targets exist check
                [{"has_conflict": False}],  # conflict check
                [],  # create
            ],
        ):
            r = client.put(
                BASE,
                json={"items": [{"id": 20, "position": "Previous"}]},
                headers=admin_headers,
            )
        assert r.status_code == 201

    def test_put_self_reference(self, client, admin_headers):
        r = client.put(
            BASE,
            json={"items": [{"id": 10, "position": "Previous"}]},
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_put_duplicate_items(self, client, admin_headers):
        r = client.put(
            BASE,
            json={
                "items": [
                    {"id": 20, "position": "Previous"},
                    {"id": 20, "position": "Previous"},
                ]
            },
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_put_duplicate_index(self, client, admin_headers):
        r = client.put(
            BASE,
            json={
                "items": [
                    {"id": 20, "position": "Previous", "index": 0},
                    {"id": 21, "position": "Previous", "index": 0},
                ]
            },
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_put_targets_not_found(self, client, admin_headers):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            return_value=[{"all_targets_exist": False}],
        ):
            r = client.put(
                BASE,
                json={"items": [{"id": 999, "position": "Next"}]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_put_index_conflict(self, client, admin_headers):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"all_targets_exist": True}],
                [{"has_conflict": True}],
            ],
        ):
            r = client.put(
                BASE,
                json={"items": [{"id": 20, "position": "Previous", "index": 0}]},
                headers=admin_headers,
            )
        assert r.status_code == 400

    def test_put_dual_position(self, client, admin_headers):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"all_targets_exist": True}],
                [{"has_conflict": False}],
                [],
            ],
        ):
            r = client.put(
                BASE,
                json={"items": [{"id": 20, "position": "Dual"}]},
                headers=admin_headers,
            )
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# DELETE  …/adjacents
# ---------------------------------------------------------------------------


class TestDeleteAdjacents:
    def test_delete_success(self, client, admin_headers):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"id": 10}],  # item exists
                [],  # delete
            ],
        ):
            r = client.request(
                "DELETE",
                BASE,
                json={"items": [20]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_delete_item_not_found(self, client, admin_headers):
        with patch("app.routers.line_item_adjacents.run_query", return_value=[]):
            r = client.request(
                "DELETE",
                BASE,
                json={"items": [20]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_delete_duplicate_ids(self, client, admin_headers):
        r = client.request(
            "DELETE",
            BASE,
            json={"items": [20, 20]},
            headers=admin_headers,
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# PATCH  …/adjacents/{adj_id}
# ---------------------------------------------------------------------------


class TestPatchAdjacent:
    def test_patch_success(self, client, admin_headers):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"current_id": 10, "adj_id": 20}],  # existence check
                [],  # update
            ],
        ):
            r = client.patch(
                f"{BASE}/20",
                json={"position": "Next"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_not_found(self, client, admin_headers):
        with patch("app.routers.line_item_adjacents.run_query", return_value=[]):
            r = client.patch(
                f"{BASE}/999",
                json={"position": "Next"},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_patch_index_conflict(self, client, admin_headers):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"current_id": 10, "adj_id": 20}],
                [{"has_conflict": True}],
            ],
        ):
            r = client.patch(
                f"{BASE}/20",
                json={"position": "Previous", "index": 0},
                headers=admin_headers,
            )
        assert r.status_code == 400

    def test_patch_with_index_no_conflict(self, client, admin_headers):
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"current_id": 10, "adj_id": 20}],
                [{"has_conflict": False}],
                [],
            ],
        ):
            r = client.patch(
                f"{BASE}/20",
                json={"position": "Previous", "index": 1},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_invalid_position(self, client, admin_headers):
        r = client.patch(
            f"{BASE}/20",
            json={"position": "BadPos"},
            headers=admin_headers,
        )
        assert r.status_code == 422
