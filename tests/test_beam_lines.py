"""Tests for the beam-lines REST API endpoints.

These tests exercise the HTTP layer only — all CRUD functions and DB helpers
are patched so no real Neo4j or Redis instance is required.
"""

from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# POST /api/v1/beam-lines
# ---------------------------------------------------------------------------


class TestCreateBeamLine:
    def test_create_success(self, client, admin_headers):
        """201 and the new ID are returned when the name is unique."""
        with (
            patch("app.routers.beam_lines.check_name_uniqueness", return_value=None),
            patch(
                "app.routers.beam_lines.create_beam_line_record",
                return_value=[{"id": 1}],
            ),
        ):
            r = client.post(
                "/api/v1/beam-lines",
                json={"name": "LEBT", "description": "Low energy transport"},
                headers=admin_headers,
            )
        assert r.status_code == 201
        assert r.json() == {"id": 1}

    def test_create_success_without_description(self, client, admin_headers):
        """201 is returned even when the optional description is omitted."""
        with (
            patch("app.routers.beam_lines.check_name_uniqueness", return_value=None),
            patch(
                "app.routers.beam_lines.create_beam_line_record",
                return_value=[{"id": 2}],
            ),
        ):
            r = client.post(
                "/api/v1/beam-lines",
                json={"name": "MEBT"},
                headers=admin_headers,
            )
        assert r.status_code == 201
        assert r.json() == {"id": 2}

    def test_create_conflict(self, client, admin_headers):
        """409 is returned when a node with the same name already exists."""
        with patch("app.dependencies.exists_any_name", return_value=True):
            r = client.post(
                "/api/v1/beam-lines",
                json={"name": "LEBT"},
                headers=admin_headers,
            )
        assert r.status_code == 409

    def test_create_db_failure(self, client, admin_headers):
        """500 is raised when the CRUD function returns an empty list."""
        with (
            patch("app.routers.beam_lines.check_name_uniqueness", return_value=None),
            patch("app.routers.beam_lines.create_beam_line_record", return_value=[]),
        ):
            r = client.post(
                "/api/v1/beam-lines",
                json={"name": "LEBT"},
                headers=admin_headers,
            )
        assert r.status_code == 500

    def test_create_empty_name_rejected(self, client, admin_headers):
        """422 is returned when name is an empty string (schema validation)."""
        r = client.post(
            "/api/v1/beam-lines",
            json={"name": ""},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_create_missing_name_rejected(self, client, admin_headers):
        """422 is returned when the required name field is absent."""
        r = client.post(
            "/api/v1/beam-lines",
            json={"description": "No name provided"},
            headers=admin_headers,
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/beam-lines
# ---------------------------------------------------------------------------


class TestListBeamLines:
    def test_list_empty(self, client):
        """Returns an empty data list with correct pagination metadata."""
        with (
            patch("app.routers.beam_lines.get_total_beam_line_records", return_value=0),
            patch("app.routers.beam_lines.get_beam_line_records", return_value=[]),
        ):
            r = client.get("/api/v1/beam-lines")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []
        assert body["page"] == 1
        assert body["per_page"] == 10

    def test_list_with_results(self, client):
        """Data list is populated and pagination totals reflect the DB count."""
        records = [{"id": 1, "name": "LEBT", "description": None}]
        with (
            patch("app.routers.beam_lines.get_total_beam_line_records", return_value=1),
            patch("app.routers.beam_lines.get_beam_line_records", return_value=records),
        ):
            r = client.get("/api/v1/beam-lines")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 1
        assert body["data"][0]["name"] == "LEBT"

    def test_list_multiple_results(self, client):
        """All returned records appear in the response data list."""
        records = [
            {"id": 1, "name": "LEBT", "description": None},
            {"id": 2, "name": "MEBT", "description": "Medium energy"},
        ]
        with (
            patch("app.routers.beam_lines.get_total_beam_line_records", return_value=2),
            patch("app.routers.beam_lines.get_beam_line_records", return_value=records),
        ):
            r = client.get("/api/v1/beam-lines")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert len(body["data"]) == 2

    def test_list_pagination_params_reflected(self, client):
        """Custom page and per_page values are echoed back in the response."""
        with (
            patch("app.routers.beam_lines.get_total_beam_line_records", return_value=0),
            patch("app.routers.beam_lines.get_beam_line_records", return_value=[]),
        ):
            r = client.get("/api/v1/beam-lines?page=2&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 5

    def test_list_sort_by_name(self, client):
        """Sorting by the 'name' key is accepted and returns 200."""
        with (
            patch("app.routers.beam_lines.get_total_beam_line_records", return_value=0),
            patch("app.routers.beam_lines.get_beam_line_records", return_value=[]),
        ):
            r = client.get("/api/v1/beam-lines?sort=name")
        assert r.status_code == 200

    def test_list_invalid_sort_key(self, client):
        """An unsupported sort key triggers a 422 before any DB call."""
        r = client.get("/api/v1/beam-lines?sort=invalid")
        assert r.status_code == 422

    def test_list_name_filter(self, client):
        """Name substring filter is accepted and returns 200."""
        with (
            patch("app.routers.beam_lines.get_total_beam_line_records", return_value=0),
            patch("app.routers.beam_lines.get_beam_line_records", return_value=[]),
        ):
            r = client.get("/api/v1/beam-lines?name=leb")
        assert r.status_code == 200

    def test_list_invalid_page(self, client):
        """page=0 is rejected with 422 by FastAPI's query validator."""
        r = client.get("/api/v1/beam-lines?page=0")
        assert r.status_code == 422

    def test_list_per_page_over_limit(self, client):
        """per_page > 100 is rejected with 422 by FastAPI's query validator."""
        r = client.get("/api/v1/beam-lines?per_page=101")
        assert r.status_code == 422

    def test_list_description_included_in_items(self, client):
        """When the record carries a description it is present in the response."""
        records = [{"id": 3, "name": "HEBT", "description": "High energy transport"}]
        with (
            patch("app.routers.beam_lines.get_total_beam_line_records", return_value=1),
            patch("app.routers.beam_lines.get_beam_line_records", return_value=records),
        ):
            r = client.get("/api/v1/beam-lines")
        assert r.status_code == 200
        assert r.json()["data"][0]["description"] == "High energy transport"


# ---------------------------------------------------------------------------
# GET /api/v1/beam-lines/{beam_id}
# ---------------------------------------------------------------------------


class TestGetBeamLine:
    def test_get_success(self, client):
        """200 plus links and data are returned for an existing beam line."""
        with patch(
            "app.routers.beam_lines.get_beam_line_record",
            new=AsyncMock(
                return_value={
                    "links": {"line_items": "/api/v1/beam-lines/1/line-items"},
                    "data": {"id": 1, "name": "LEBT", "description": "desc"},
                }
            ),
        ):
            r = client.get("/api/v1/beam-lines/1")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["id"] == 1
        assert body["data"]["name"] == "LEBT"
        assert "line_items" in body["links"]

    def test_get_not_found(self, client):
        """404 is returned when the CRUD function resolves to None."""
        with patch(
            "app.routers.beam_lines.get_beam_line_record",
            new=AsyncMock(return_value=None),
        ):
            r = client.get("/api/v1/beam-lines/999")
        assert r.status_code == 404

    def test_get_etag_header_present(self, client):
        """ETag header is set on a successful response."""
        with patch(
            "app.routers.beam_lines.get_beam_line_record",
            new=AsyncMock(
                return_value={
                    "links": {"line_items": "/api/v1/beam-lines/1/line-items"},
                    "data": {"id": 1, "name": "LEBT", "description": None},
                }
            ),
        ):
            r = client.get("/api/v1/beam-lines/1")
        assert r.status_code == 200
        assert "etag" in r.headers

    def test_get_304_when_etag_matches(self, client):
        """304 Not Modified is returned when If-None-Match matches the ETag."""
        payload = {
            "links": {"line_items": "/api/v1/beam-lines/1/line-items"},
            "data": {"id": 1, "name": "LEBT", "description": None},
        }
        with patch(
            "app.routers.beam_lines.get_beam_line_record",
            new=AsyncMock(return_value=payload),
        ):
            # First request — collect the ETag
            r1 = client.get("/api/v1/beam-lines/1")
            etag = r1.headers["etag"]

        with patch(
            "app.routers.beam_lines.get_beam_line_record",
            new=AsyncMock(return_value=payload),
        ):
            # Second request — send the ETag back
            r2 = client.get("/api/v1/beam-lines/1", headers={"If-None-Match": etag})
        assert r2.status_code == 304

    def test_get_links_url_format(self, client):
        """The line_items link contains the correct beam_id in the URL."""
        with patch(
            "app.routers.beam_lines.get_beam_line_record",
            new=AsyncMock(
                return_value={
                    "links": {"line_items": "/api/v1/beam-lines/42/line-items"},
                    "data": {"id": 42, "name": "X", "description": None},
                }
            ),
        ):
            r = client.get("/api/v1/beam-lines/42")
        assert r.status_code == 200
        assert "42" in r.json()["links"]["line_items"]


# ---------------------------------------------------------------------------
# PATCH /api/v1/beam-lines/{beam_id}
# ---------------------------------------------------------------------------


class TestPatchBeamLine:
    def test_patch_name_success(self, client, admin_headers):
        """204 is returned when the name update succeeds."""
        with (
            patch("app.routers.beam_lines.check_name_uniqueness", return_value=None),
            patch(
                "app.routers.beam_lines.update_beam_line_record",
                return_value=[{"b": MagicMock()}],
            ),
        ):
            r = client.patch(
                "/api/v1/beam-lines/1",
                json={"name": "LEBT-Renamed"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_description_only(self, client, admin_headers):
        """204 is returned when only the description is updated."""
        with (
            patch("app.routers.beam_lines.check_name_uniqueness", return_value=None),
            patch(
                "app.routers.beam_lines.update_beam_line_record",
                return_value=[{"b": MagicMock()}],
            ),
        ):
            r = client.patch(
                "/api/v1/beam-lines/1",
                json={"description": "new desc"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_both_fields(self, client, admin_headers):
        """204 is returned when both name and description are updated together."""
        with (
            patch("app.routers.beam_lines.check_name_uniqueness", return_value=None),
            patch(
                "app.routers.beam_lines.update_beam_line_record",
                return_value=[{"b": MagicMock()}],
            ),
        ):
            r = client.patch(
                "/api/v1/beam-lines/1",
                json={"name": "NEW", "description": "new desc"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_name_conflict(self, client, admin_headers):
        """409 is returned when a node with the same name already exists."""
        with patch("app.dependencies.exists_any_name", return_value=True):
            r = client.patch(
                "/api/v1/beam-lines/1",
                json={"name": "Other"},
                headers=admin_headers,
            )
        assert r.status_code == 409

    def test_patch_not_found(self, client, admin_headers):
        """404 is returned when the CRUD function returns an empty list."""
        with (
            patch("app.routers.beam_lines.check_name_uniqueness", return_value=None),
            patch("app.routers.beam_lines.update_beam_line_record", return_value=[]),
        ):
            r = client.patch(
                "/api/v1/beam-lines/999",
                json={"name": "X"},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_patch_no_fields_is_noop(self, client, admin_headers):
        """Empty payload with no fields returns 204 without hitting the DB."""
        r = client.patch(
            "/api/v1/beam-lines/1",
            json={},
            headers=admin_headers,
        )
        assert r.status_code == 204

    def test_patch_empty_name_rejected(self, client, admin_headers):
        """An empty string for name is rejected with 422 by schema validation."""
        r = client.patch(
            "/api/v1/beam-lines/1",
            json={"name": ""},
            headers=admin_headers,
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/v1/beam-lines/{beam_id}
# ---------------------------------------------------------------------------


class TestDeleteBeamLine:
    def test_delete_success_no_children(self, client, admin_headers):
        """204 is returned when the beam line has no linked line items."""
        with (
            patch(
                "app.routers.beam_lines.get_beam_line_relationships",
                return_value=[{"linked_count": 0}],
            ),
            patch("app.routers.beam_lines.delete_beam_line_record", return_value=[]),
        ):
            r = client.delete("/api/v1/beam-lines/1", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_conflict_has_children(self, client, admin_headers):
        """409 is returned when the beam line has linked items and force=False."""
        with patch(
            "app.routers.beam_lines.get_beam_line_relationships",
            return_value=[{"linked_count": 3}],
        ):
            r = client.delete("/api/v1/beam-lines/1", headers=admin_headers)
        assert r.status_code == 409

    def test_delete_force_with_children(self, client, admin_headers):
        """204 is returned when force=True even if children exist."""
        with (
            patch(
                "app.routers.beam_lines.get_beam_line_relationships",
                return_value=[{"linked_count": 3}],
            ),
            patch("app.routers.beam_lines.delete_beam_line_record", return_value=[]),
        ):
            r = client.delete("/api/v1/beam-lines/1?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_not_found(self, client, admin_headers):
        """204 is returned when get_beam_line_relationships returns empty (no node).

        The router returns early with None (204) when records is falsy, mirroring
        the OPTIONAL MATCH behaviour where a missing node yields no records.
        """
        with patch(
            "app.routers.beam_lines.get_beam_line_relationships",
            return_value=[],
        ):
            r = client.delete("/api/v1/beam-lines/999", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_force_no_children(self, client, admin_headers):
        """204 is returned with force=True even when there are no children."""
        with (
            patch(
                "app.routers.beam_lines.get_beam_line_relationships",
                return_value=[{"linked_count": 0}],
            ),
            patch("app.routers.beam_lines.delete_beam_line_record", return_value=[]),
        ):
            r = client.delete("/api/v1/beam-lines/1?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_calls_crud_functions(self, client, admin_headers):
        """The CRUD delete function is called exactly once on a successful delete."""
        mock_delete = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.beam_lines.get_beam_line_relationships",
                return_value=[{"linked_count": 0}],
            ),
            patch("app.routers.beam_lines.delete_beam_line_record", mock_delete),
        ):
            client.delete("/api/v1/beam-lines/5", headers=admin_headers)
        mock_delete.assert_called_once()
