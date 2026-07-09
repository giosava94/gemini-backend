"""Tests for the beam-lines CRUD endpoints."""

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# POST /api/v1/beam-lines
# ---------------------------------------------------------------------------


class TestCreateBeamLine:
    def test_create_success(self, client, admin_headers):
        with (
            patch("app.routers.beam_lines.check_name_uniqueness", return_value=None),
            patch("app.routers.beam_lines.run_query", return_value=[{"id": 1}]),
        ):
            r = client.post(
                "/api/v1/beam-lines",
                json={"name": "LEBT", "description": "Low energy transport"},
                headers=admin_headers,
            )
        assert r.status_code == 201
        assert r.json() == {"id": 1}

    def test_create_conflict(self, client, admin_headers):
        with patch("app.routers.beam_lines.check_name_uniqueness", return_value=True):
            r = client.post(
                "/api/v1/beam-lines",
                json={"name": "LEBT"},
                headers=admin_headers,
            )
        assert r.status_code == 409

    def test_create_db_failure(self, client, admin_headers):
        with (
            patch("app.routers.beam_lines.exists_any_name", return_value=False),
            patch("app.routers.beam_lines.run_query", return_value=[]),
        ):
            r = client.post(
                "/api/v1/beam-lines",
                json={"name": "LEBT"},
                headers=admin_headers,
            )
        assert r.status_code == 500

    def test_create_empty_name_rejected(self, client, admin_headers):
        r = client.post(
            "/api/v1/beam-lines",
            json={"name": ""},
            headers=admin_headers,
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/beam-lines
# ---------------------------------------------------------------------------


class TestListBeamLines:
    def _make_record(self, bid, name, desc=None):
        node = MagicMock()
        node.__getitem__ = lambda s, k: {"id": bid, "name": name}[k]
        node.get = lambda k, d=None: desc if k == "description" else d
        return {"b": node}

    def test_list_empty(self, client):
        with patch(
            "app.routers.beam_lines.run_query",
            side_effect=[[{"total": 0}], []],
        ):
            r = client.get("/api/v1/beam-lines")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []
        assert body["page"] == 1
        assert body["per_page"] == 10

    def test_list_with_results(self, client):
        record = self._make_record(1, "LEBT")
        with patch(
            "app.routers.beam_lines.run_query",
            side_effect=[[{"total": 1}], [record]],
        ):
            r = client.get("/api/v1/beam-lines")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 1
        assert body["data"][0]["name"] == "LEBT"

    def test_list_pagination(self, client):
        with patch(
            "app.routers.beam_lines.run_query",
            side_effect=[[{"total": 0}], []],
        ):
            r = client.get("/api/v1/beam-lines?page=2&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 5

    def test_list_sort_by_name(self, client):
        with patch(
            "app.routers.beam_lines.run_query",
            side_effect=[[{"total": 0}], []],
        ):
            r = client.get("/api/v1/beam-lines?sort=name")
        assert r.status_code == 200

    def test_list_invalid_sort_key(self, client):
        r = client.get("/api/v1/beam-lines?sort=invalid")
        assert r.status_code == 422

    def test_list_name_filter(self, client):
        with patch(
            "app.routers.beam_lines.run_query",
            side_effect=[[{"total": 0}], []],
        ):
            r = client.get("/api/v1/beam-lines?name=leb")
        assert r.status_code == 200

    def test_list_invalid_page(self, client):
        r = client.get("/api/v1/beam-lines?page=0")
        assert r.status_code == 422

    def test_list_per_page_over_limit(self, client):
        r = client.get("/api/v1/beam-lines?per_page=101")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/beam-lines/{beam_id}
# ---------------------------------------------------------------------------


class TestGetBeamLine:
    def test_get_success(self, client):
        with patch(
            "app.routers.beam_lines.find_by_id",
            return_value={"id": 1, "name": "LEBT", "description": "desc"},
        ):
            r = client.get("/api/v1/beam-lines/1")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["id"] == 1
        assert body["data"]["name"] == "LEBT"
        assert "line_items" in body["links"]

    def test_get_not_found(self, client):
        with patch("app.routers.beam_lines.find_by_id", return_value=None):
            r = client.get("/api/v1/beam-lines/999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/beam-lines/{beam_id}
# ---------------------------------------------------------------------------


class TestPatchBeamLine:
    def test_patch_name_success(self, client, admin_headers):
        with (
            patch("app.routers.beam_lines.exists_any_name", return_value=False),
            patch(
                "app.routers.beam_lines.run_query", return_value=[{"b": MagicMock()}]
            ),
        ):
            r = client.patch(
                "/api/v1/beam-lines/1",
                json={"name": "LEBT-Renamed"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_name_conflict(self, client, admin_headers):
        with patch("app.routers.beam_lines.exists_any_name", return_value=True):
            r = client.patch(
                "/api/v1/beam-lines/1",
                json={"name": "Other"},
                headers=admin_headers,
            )
        assert r.status_code == 409

    def test_patch_not_found(self, client, admin_headers):
        with (
            patch("app.routers.beam_lines.exists_any_name", return_value=False),
            patch("app.routers.beam_lines.run_query", return_value=[]),
        ):
            r = client.patch(
                "/api/v1/beam-lines/999",
                json={"name": "X"},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_patch_no_fields_is_noop(self, client, admin_headers):
        """Empty payload with no fields to update returns 204 without hitting DB."""
        r = client.patch(
            "/api/v1/beam-lines/1",
            json={},
            headers=admin_headers,
        )
        # No DB calls needed — router returns None early
        assert r.status_code == 204

    def test_patch_description_only(self, client, admin_headers):
        with (
            patch("app.routers.beam_lines.exists_any_name", return_value=False),
            patch(
                "app.routers.beam_lines.run_query", return_value=[{"b": MagicMock()}]
            ),
        ):
            r = client.patch(
                "/api/v1/beam-lines/1",
                json={"description": "new desc"},
                headers=admin_headers,
            )
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# DELETE /api/v1/beam-lines/{beam_id}
# ---------------------------------------------------------------------------


class TestDeleteBeamLine:
    def test_delete_success_no_children(self, client, admin_headers):
        with patch(
            "app.routers.beam_lines.run_query",
            side_effect=[[{"linked_count": 0}], []],
        ):
            r = client.delete("/api/v1/beam-lines/1", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_conflict_has_children(self, client, admin_headers):
        with patch(
            "app.routers.beam_lines.run_query",
            return_value=[{"linked_count": 3}],
        ):
            r = client.delete("/api/v1/beam-lines/1", headers=admin_headers)
        assert r.status_code == 409

    def test_delete_force(self, client, admin_headers):
        with patch(
            "app.routers.beam_lines.run_query",
            side_effect=[[{"linked_count": 3}], []],
        ):
            r = client.delete("/api/v1/beam-lines/1?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_not_found(self, client, admin_headers):
        with patch("app.routers.beam_lines.run_query", return_value=[]):
            r = client.delete("/api/v1/beam-lines/999", headers=admin_headers)
        assert r.status_code == 404
