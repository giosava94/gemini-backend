"""Tests for the line-items CRUD endpoints."""

from unittest.mock import MagicMock, patch


BASE = "/api/v1/beam-lines/1/line-items"

VALID_PAYLOAD = {
    "name": "QD01",
    "kind": "Diagnostic",
    "status": 0,
    "adjacents": [],
    "connections": [],
}


def _make_li_record(
    lid,
    name,
    kind="Diagnostic",
    status=0,
    desc=None,
    labels=None,
):
    """Build a fake Neo4j record dict for a LineItem node."""
    labels = labels if labels is not None else []
    node = MagicMock()
    node.__getitem__ = lambda s, k: {
        "id": lid,
        "name": name,
        "kind": kind,
        "status": status,
        "labels": labels,
    }[k]
    node.get = lambda k, d=None: {"description": desc, "labels": labels}.get(k, d)
    return {"li": node}


# ---------------------------------------------------------------------------
# POST  /api/v1/beam-lines/{beam_id}/line-items
# ---------------------------------------------------------------------------


class TestCreateLineItem:
    def test_create_success(self, client, admin_headers):
        with (
            patch(
                "app.routers.line_items.run_query",
                side_effect=[
                    [{"id": 1}],  # beam line exists
                    [{"id": 42}],  # create query
                ],
            ),
            patch("app.routers.line_items.exists_any_name", return_value=False),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 201
        assert r.json() == {"id": 42}

    def test_create_beam_not_found(self, client, admin_headers):
        with patch("app.routers.line_items.run_query", return_value=[]):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 404

    def test_create_name_conflict(self, client, admin_headers):
        with (
            patch("app.routers.line_items.run_query", return_value=[{"id": 1}]),
            patch("app.routers.line_items.exists_any_name", return_value=True),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 409

    def test_create_duplicate_adjacent_index(self, client, admin_headers):
        payload = {
            **VALID_PAYLOAD,
            "adjacents": [
                {"id": 5, "position": "Previous", "index": 0},
                {"id": 6, "position": "Previous", "index": 0},
            ],
        }
        with (
            patch("app.routers.line_items.run_query", return_value=[{"id": 1}]),
            patch("app.routers.line_items.exists_any_name", return_value=False),
        ):
            r = client.post(BASE, json=payload, headers=admin_headers)
        assert r.status_code == 400

    def test_create_adjacent_not_found(self, client, admin_headers):
        payload = {**VALID_PAYLOAD, "adjacents": [{"id": 999, "position": "Previous"}]}
        with (
            patch(
                "app.routers.line_items.run_query",
                side_effect=[
                    [{"id": 1}],  # beam line exists
                    [],  # _line_item_ids_exist returns empty
                ],
            ),
            patch("app.routers.line_items.exists_any_name", return_value=False),
        ):
            r = client.post(BASE, json=payload, headers=admin_headers)
        assert r.status_code == 404

    def test_create_db_failure(self, client, admin_headers):
        with (
            patch(
                "app.routers.line_items.run_query",
                side_effect=[
                    [{"id": 1}],  # beam line exists
                    [],  # create returns empty
                ],
            ),
            patch("app.routers.line_items.exists_any_name", return_value=False),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 500

    def test_create_invalid_kind(self, client, admin_headers):
        r = client.post(
            BASE,
            json={**VALID_PAYLOAD, "kind": "InvalidKind"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_create_with_labels(self, client, admin_headers):
        payload = {**VALID_PAYLOAD, "labels": ["magnet", "critical"]}
        with (
            patch("app.routers.line_items.exists_any_name", return_value=False),
            patch("app.routers.line_items.run_query") as run_query_mock,
        ):
            run_query_mock.side_effect = [[{"id": 1}], [{"id": 42}]]
            r = client.post(BASE, json=payload, headers=admin_headers)

        assert r.status_code == 201
        assert r.json() == {"id": 42}
        assert run_query_mock.call_count == 2
        assert run_query_mock.call_args_list[1][0][2]["labels"] == [
            "magnet",
            "critical",
        ]

    def test_create_with_aliases(self, client, admin_headers):
        payload = {**VALID_PAYLOAD, "aliases": ["QD01-A", "Quad01"]}
        with (
            patch("app.routers.line_items.exists_any_name", return_value=False),
            patch("app.routers.line_items.run_query") as run_query_mock,
        ):
            run_query_mock.side_effect = [[{"id": 1}], [{"id": 42}]]
            r = client.post(BASE, json=payload, headers=admin_headers)

        assert r.status_code == 201
        assert r.json() == {"id": 42}
        assert run_query_mock.call_count == 2
        assert run_query_mock.call_args_list[1][0][2]["aliases"] == [
            "QD01-A",
            "Quad01",
        ]


# ---------------------------------------------------------------------------
# GET /api/v1/beam-lines/{beam_id}/line-items
# ---------------------------------------------------------------------------


class TestListLineItems:
    def test_list_empty(self, client):
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],  # beam exists
                [{"total": 0}],  # count
                [],  # data
            ],
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []

    def test_list_beam_not_found(self, client):
        with patch("app.routers.line_items.run_query", return_value=[]):
            r = client.get(BASE)
        assert r.status_code == 404

    def test_list_with_results(self, client):
        record = _make_li_record(10, "QD01")
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],
                [{"total": 1}],
                [record],
            ],
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 10

    def test_list_invalid_sort(self, client):
        with patch("app.routers.line_items.run_query", return_value=[{"id": 1}]):
            r = client.get(f"{BASE}?sort=invalid")
        assert r.status_code == 422

    def test_list_sort_by_name_and_kind(self, client):
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?sort=name&sort=kind")
        assert r.status_code == 200

    def test_list_invalid_kind_filter(self, client):
        with patch("app.routers.line_items.run_query", return_value=[{"id": 1}]):
            r = client.get(f"{BASE}?kind=NotAKind")
        assert r.status_code == 422

    def test_list_status_filter(self, client):
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?status=0")
        assert r.status_code == 200

    def test_list_alias_filter(self, client):
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],
                [{"total": 0}],
                [],
            ],
        ):
            r = client.get(f"{BASE}?alias=quad")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/beam-lines/{beam_id}/line-items/{item_id}
# ---------------------------------------------------------------------------


class TestGetLineItem:
    def test_get_success(self, client):
        record = _make_li_record(10, "QD01")
        with patch("app.routers.line_items.run_query", return_value=[record]):
            r = client.get(f"{BASE}/10")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["id"] == 10
        assert "adjacents" in body["links"]
        assert "connections" in body["links"]

    def test_get_returns_labels(self, client):
        record = _make_li_record(10, "QD01", labels=["magnet", "critical"])
        with patch("app.routers.line_items.run_query", return_value=[record]):
            r = client.get(f"{BASE}/10")
        assert r.status_code == 200
        assert r.json()["data"]["labels"] == ["magnet", "critical"]

    def test_get_returns_aliases(self, client):
        node = MagicMock()
        node.__getitem__ = lambda s, k: {
            "id": 10,
            "name": "QD01",
            "kind": "Diagnostic",
            "status": 0,
            "labels": [],
            "aliases": ["Q-01", "Quad01"],
        }[k]
        node.get = lambda k, d=None: {
            "description": None,
            "labels": [],
            "aliases": ["Q-01", "Quad01"],
        }.get(k, d)
        record = {"li": node}
        with patch("app.routers.line_items.run_query", return_value=[record]):
            r = client.get(f"{BASE}/10")
        assert r.status_code == 200
        assert r.json()["data"]["aliases"] == ["Q-01", "Quad01"]

    def test_get_not_found(self, client):
        with patch("app.routers.line_items.run_query", return_value=[]):
            r = client.get(f"{BASE}/999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/beam-lines/{beam_id}/line-items/{item_id}
# ---------------------------------------------------------------------------


class TestPatchLineItem:
    def test_patch_success(self, client, admin_headers):
        with (
            patch("app.routers.line_items.exists_any_name", return_value=False),
            patch("app.routers.line_items.run_query", return_value=[{"id": 10}]),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"name": "QD01-Renamed"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_name_conflict(self, client, admin_headers):
        with patch("app.routers.line_items.exists_any_name", return_value=True):
            r = client.patch(
                f"{BASE}/10",
                json={"name": "Taken"},
                headers=admin_headers,
            )
        assert r.status_code == 409

    def test_patch_not_found(self, client, admin_headers):
        with (
            patch("app.routers.line_items.exists_any_name", return_value=False),
            patch("app.routers.line_items.run_query", return_value=[]),
        ):
            r = client.patch(
                f"{BASE}/999",
                json={"name": "X"},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_patch_no_fields_noop(self, client, admin_headers):
        r = client.patch(f"{BASE}/10", json={}, headers=admin_headers)
        assert r.status_code == 204

    def test_patch_status(self, client, admin_headers):
        with (
            patch("app.routers.line_items.exists_any_name", return_value=False),
            patch("app.routers.line_items.run_query", return_value=[{"id": 10}]),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"status": 1},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_kind(self, client, admin_headers):
        with (
            patch("app.routers.line_items.exists_any_name", return_value=False),
            patch("app.routers.line_items.run_query", return_value=[{"id": 10}]),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"kind": "Diagnostic"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_labels(self, client, admin_headers):
        with (
            patch("app.routers.line_items.exists_any_name", return_value=False),
            patch("app.routers.line_items.run_query", return_value=[{"id": 10}]),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"labels": ["alignment", "high-priority"]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_aliases(self, client, admin_headers):
        with (
            patch("app.routers.line_items.exists_any_name", return_value=False),
            patch("app.routers.line_items.run_query", return_value=[{"id": 10}]),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"aliases": ["Q-01-A", "QuadA"]},
                headers=admin_headers,
            )
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# DELETE /api/v1/beam-lines/{beam_id}/line-items/{item_id}
# ---------------------------------------------------------------------------


class TestDeleteLineItem:
    def test_delete_success_no_links(self, client, admin_headers):
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],  # beam exists
                [{"id": 10, "linked_count": 0}],  # item check
                [],  # detach delete
            ],
        ):
            r = client.delete(f"{BASE}/10", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_conflict_has_links(self, client, admin_headers):
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],
                [{"id": 10, "linked_count": 2}],
            ],
        ):
            r = client.delete(f"{BASE}/10", headers=admin_headers)
        assert r.status_code == 409

    def test_delete_force(self, client, admin_headers):
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],
                [{"id": 10, "linked_count": 2}],
                [],
            ],
        ):
            r = client.delete(f"{BASE}/10?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_beam_not_found(self, client, admin_headers):
        with patch("app.routers.line_items.run_query", return_value=[]):
            r = client.delete(f"{BASE}/10", headers=admin_headers)
        assert r.status_code == 404

    def test_delete_item_not_found_silent(self, client, admin_headers):
        """When item doesn't exist the endpoint returns 204 silently."""
        with patch(
            "app.routers.line_items.run_query",
            side_effect=[
                [{"id": 1}],  # beam exists
                [],  # item not found
            ],
        ):
            r = client.delete(f"{BASE}/999", headers=admin_headers)
        assert r.status_code == 204
