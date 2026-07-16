"""Tests for the line-items REST API endpoints.

These tests exercise the HTTP layer only — all CRUD functions and DB helpers
are patched so no real Neo4j or Redis instance is required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BASE = "/api/v1/beam-lines/1/line-items"

VALID_PAYLOAD = {
    "name": "QD01",
    "kind": "Diagnostic",
    "status": 0,
    "adjacents": [],
    "connections": [],
}


def _detail_payload(iid=10, beam_id=1, name="QD01", labels=None, aliases=None):
    """Build a fake detail response dict for get_line_item_record."""
    base_url = f"/api/v1/beam-lines/{beam_id}/line-items/{iid}"
    return {
        "links": {
            "adjacents": f"{base_url}/adjacents",
            "connections": f"{base_url}/connections",
        },
        "data": {
            "id": iid,
            "name": name,
            "description": None,
            "kind": "Diagnostic",
            "status": 0,
            "labels": labels or [],
            "aliases": aliases or [],
        },
    }


# ---------------------------------------------------------------------------
# POST /api/v1/beam-lines/{beam_id}/line-items
# ---------------------------------------------------------------------------


class TestCreateLineItem:
    def test_create_success(self, client, admin_headers):
        """201 and the new ID are returned when all preconditions pass."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index",
                return_value=False,
            ),
            patch("app.routers.line_items.adj_and_conn_items_exist", return_value=True),
            patch("app.routers.line_items.create", return_value=[{"id": 42}]),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 201
        assert r.json() == {"id": 42}

    def test_create_success_with_description(self, client, admin_headers):
        """201 is returned when an optional description is included."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index",
                return_value=False,
            ),
            patch("app.routers.line_items.adj_and_conn_items_exist", return_value=True),
            patch("app.routers.line_items.create", return_value=[{"id": 7}]),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "description": "A quadrupole"},
                headers=admin_headers,
            )
        assert r.status_code == 201
        assert r.json() == {"id": 7}

    def test_create_beam_not_found(self, client, admin_headers):
        """404 is returned when the parent beam line does not exist."""
        with patch("app.routers.line_items.beam_line_exists", return_value=False):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 404

    def test_create_name_conflict(self, client, admin_headers):
        """409 is returned when a node with the same name already exists."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=True),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 409

    def test_create_duplicate_adjacent_index(self, client, admin_headers):
        """400 is returned when two adjacents share the same (position, index)."""
        payload = {
            **VALID_PAYLOAD,
            "adjacents": [
                {"id": 5, "position": "Previous", "index": 0},
                {"id": 6, "position": "Previous", "index": 0},
            ],
        }
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index", return_value=True
            ),
        ):
            r = client.post(BASE, json=payload, headers=admin_headers)
        assert r.status_code == 400

    def test_create_adjacent_not_found(self, client, admin_headers):
        """404 is raised when adj_and_conn_items_exist returns False."""
        payload = {**VALID_PAYLOAD, "adjacents": [{"id": 999, "position": "Previous"}]}
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index",
                return_value=False,
            ),
            patch(
                "app.routers.line_items.adj_and_conn_items_exist", return_value=False
            ),
        ):
            r = client.post(BASE, json=payload, headers=admin_headers)
        assert r.status_code == 404

    def test_create_db_failure(self, client, admin_headers):
        """500 is raised when the CRUD create function returns an empty list."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index",
                return_value=False,
            ),
            patch("app.routers.line_items.adj_and_conn_items_exist", return_value=True),
            patch("app.routers.line_items.create", return_value=[]),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 500

    def test_create_invalid_kind(self, client, admin_headers):
        """422 is returned when an unsupported kind value is supplied."""
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "kind": "InvalidKind"},
                headers=admin_headers,
            )
        assert r.status_code == 422

    def test_create_empty_name_rejected(self, client, admin_headers):
        """422 is returned when name is an empty string."""
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.post(
                BASE, json={**VALID_PAYLOAD, "name": ""}, headers=admin_headers
            )
        assert r.status_code == 422

    def test_create_missing_name_rejected(self, client, admin_headers):
        """422 is returned when the required name field is absent."""
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "name"}
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.post(BASE, json=payload, headers=admin_headers)
        assert r.status_code == 422

    def test_create_with_labels(self, client, admin_headers):
        """Labels list is accepted and forwarded to the CRUD create function."""
        mock_create = MagicMock(return_value=[{"id": 42}])
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index",
                return_value=False,
            ),
            patch("app.routers.line_items.adj_and_conn_items_exist", return_value=True),
            patch("app.routers.line_items.create", mock_create),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "labels": ["magnet", "critical"]},
                headers=admin_headers,
            )
        assert r.status_code == 201
        passed_payload = mock_create.call_args[0][1]
        assert passed_payload["labels"] == ["magnet", "critical"]

    def test_create_with_aliases(self, client, admin_headers):
        """Aliases list is accepted and forwarded to the CRUD create function."""
        mock_create = MagicMock(return_value=[{"id": 42}])
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index",
                return_value=False,
            ),
            patch("app.routers.line_items.adj_and_conn_items_exist", return_value=True),
            patch("app.routers.line_items.create", mock_create),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "aliases": ["QD01-A", "Quad01"]},
                headers=admin_headers,
            )
        assert r.status_code == 201
        passed_payload = mock_create.call_args[0][1]
        assert passed_payload["aliases"] == ["QD01-A", "Quad01"]

    def test_create_with_connections_success(self, client, admin_headers):
        """201 is returned when all requested connection IDs exist."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index",
                return_value=False,
            ),
            patch("app.routers.line_items.adj_and_conn_items_exist", return_value=True),
            patch("app.routers.line_items.create", return_value=[{"id": 5}]),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "connections": [1, 2]},
                headers=admin_headers,
            )
        assert r.status_code == 201

    @pytest.mark.parametrize(
        "kind",
        [
            "Diagnostic",
            "ES Triplet",
            "ES Steerer",
            "ES Dipole",
            "ES Quadrupole",
            "MG Dipole",
            "MG Solenoid",
            "Ion Source",
            "Wien Filter",
        ],
    )
    def test_create_all_valid_kinds(self, client, admin_headers, kind):
        """Every valid kind value is accepted with 201."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.has_duplicate_adjacent_index",
                return_value=False,
            ),
            patch("app.routers.line_items.adj_and_conn_items_exist", return_value=True),
            patch("app.routers.line_items.create", return_value=[{"id": 1}]),
        ):
            r = client.post(
                BASE, json={**VALID_PAYLOAD, "kind": kind}, headers=admin_headers
            )
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/beam-lines/{beam_id}/line-items
# ---------------------------------------------------------------------------


class TestListLineItems:
    def test_list_empty(self, client):
        """Returns empty data list with correct pagination metadata."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.routers.line_items.get_total_line_item_records", return_value=0),
            patch("app.routers.line_items.get_line_item_records", return_value=[]),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []
        assert body["page"] == 1
        assert body["per_page"] == 10

    def test_list_beam_not_found(self, client):
        """404 is returned when the beam line does not exist."""
        with patch("app.routers.line_items.beam_line_exists", return_value=False):
            r = client.get(BASE)
        assert r.status_code == 404

    def test_list_with_results(self, client):
        """Data list and total reflect the values returned by CRUD functions."""
        records = [{"id": 10, "name": "QD01", "description": None}]
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.routers.line_items.get_total_line_item_records", return_value=1),
            patch("app.routers.line_items.get_line_item_records", return_value=records),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 10

    def test_list_multiple_results(self, client):
        """All returned records are present in the response data list."""
        records = [
            {"id": 10, "name": "QD01", "description": None},
            {"id": 11, "name": "QF01", "description": None},
        ]
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.routers.line_items.get_total_line_item_records", return_value=2),
            patch("app.routers.line_items.get_line_item_records", return_value=records),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2

    def test_list_pagination_params_reflected(self, client):
        """Custom page and per_page values are echoed back in the response."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.routers.line_items.get_total_line_item_records", return_value=0),
            patch("app.routers.line_items.get_line_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?page=2&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 5

    def test_list_invalid_sort(self, client):
        """An unsupported sort key triggers a 422 before any DB call."""
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.get(f"{BASE}?sort=invalid")
        assert r.status_code == 422

    def test_list_sort_by_name_and_kind(self, client):
        """Sorting by 'name' and 'kind' together is accepted and returns 200."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.routers.line_items.get_total_line_item_records", return_value=0),
            patch("app.routers.line_items.get_line_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?sort=name&sort=kind")
        assert r.status_code == 200

    def test_list_invalid_kind_filter(self, client):
        """An unrecognised kind value triggers a 422."""
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.get(f"{BASE}?kind=NotAKind")
        assert r.status_code == 422

    def test_list_status_filter(self, client):
        """Status filter is accepted and returns 200."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.routers.line_items.get_total_line_item_records", return_value=0),
            patch("app.routers.line_items.get_line_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?status=0")
        assert r.status_code == 200

    def test_list_alias_filter(self, client):
        """Alias substring filter is accepted and returns 200."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.routers.line_items.get_total_line_item_records", return_value=0),
            patch("app.routers.line_items.get_line_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?alias=quad")
        assert r.status_code == 200

    def test_list_name_filter(self, client):
        """Name substring filter is accepted and returns 200."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.routers.line_items.get_total_line_item_records", return_value=0),
            patch("app.routers.line_items.get_line_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?name=QD")
        assert r.status_code == 200

    def test_list_invalid_page(self, client):
        """page=0 is rejected with 422 by FastAPI's query validator."""
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.get(f"{BASE}?page=0")
        assert r.status_code == 422

    def test_list_per_page_over_limit(self, client):
        """per_page > 100 is rejected with 422 by FastAPI's query validator."""
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.get(f"{BASE}?per_page=101")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/beam-lines/{beam_id}/line-items/{item_id}
# ---------------------------------------------------------------------------


class TestGetLineItem:
    def test_get_success(self, client):
        """200 with links and data is returned for an existing line item."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_record",
                new=AsyncMock(return_value=_detail_payload()),
            ),
        ):
            r = client.get(f"{BASE}/10")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["id"] == 10
        assert "adjacents" in body["links"]
        assert "connections" in body["links"]

    def test_get_not_found(self, client):
        """404 is returned when the CRUD function resolves to None."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_record",
                new=AsyncMock(return_value=None),
            ),
        ):
            r = client.get(f"{BASE}/999")
        assert r.status_code == 404

    def test_get_beam_not_found(self, client):
        """404 is returned when the parent beam line does not exist."""
        with patch("app.routers.line_items.beam_line_exists", return_value=False):
            r = client.get(f"{BASE}/10")
        assert r.status_code == 404

    def test_get_returns_labels(self, client):
        """Labels list from the CRUD result appears in the response data."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_record",
                new=AsyncMock(
                    return_value=_detail_payload(labels=["magnet", "critical"])
                ),
            ),
        ):
            r = client.get(f"{BASE}/10")
        assert r.status_code == 200
        assert r.json()["data"]["labels"] == ["magnet", "critical"]

    def test_get_returns_aliases(self, client):
        """Aliases list from the CRUD result appears in the response data."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_record",
                new=AsyncMock(return_value=_detail_payload(aliases=["Q-01", "Quad01"])),
            ),
        ):
            r = client.get(f"{BASE}/10")
        assert r.status_code == 200
        assert r.json()["data"]["aliases"] == ["Q-01", "Quad01"]

    def test_get_etag_header_present(self, client):
        """ETag header is set on a successful 200 response."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_record",
                new=AsyncMock(return_value=_detail_payload()),
            ),
        ):
            r = client.get(f"{BASE}/10")
        assert r.status_code == 200
        assert "etag" in r.headers

    def test_get_304_when_etag_matches(self, client):
        """304 Not Modified is returned when If-None-Match matches the ETag."""
        payload = _detail_payload()
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_record",
                new=AsyncMock(return_value=payload),
            ),
        ):
            r1 = client.get(f"{BASE}/10")
            etag = r1.headers["etag"]

        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_record",
                new=AsyncMock(return_value=payload),
            ),
        ):
            r2 = client.get(f"{BASE}/10", headers={"If-None-Match": etag})
        assert r2.status_code == 304

    def test_get_links_url_contains_ids(self, client):
        """The adjacents and connections links contain both beam_id and item_id."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_record",
                new=AsyncMock(return_value=_detail_payload(iid=99, beam_id=1)),
            ),
        ):
            r = client.get(f"{BASE}/99")
        assert r.status_code == 200
        body = r.json()
        assert "99" in body["links"]["adjacents"]
        assert "99" in body["links"]["connections"]


# ---------------------------------------------------------------------------
# PATCH /api/v1/beam-lines/{beam_id}/line-items/{item_id}
# ---------------------------------------------------------------------------


class TestPatchLineItem:
    def test_patch_name_success(self, client, admin_headers):
        """204 is returned when a name update succeeds."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.update_line_item_record",
                return_value=[{"id": 10}],
            ),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"name": "QD01-Renamed"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_name_conflict(self, client, admin_headers):
        """409 is returned when a node with the requested name already exists."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=True),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"name": "Taken"},
                headers=admin_headers,
            )
        assert r.status_code == 409

    def test_patch_not_found(self, client, admin_headers):
        """404 is returned when the CRUD function returns an empty list."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.line_items.update_line_item_record", return_value=[]),
        ):
            r = client.patch(
                f"{BASE}/999",
                json={"name": "X"},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_patch_beam_not_found(self, client, admin_headers):
        """404 is returned when the parent beam line does not exist."""
        with patch("app.routers.line_items.beam_line_exists", return_value=False):
            r = client.patch(f"{BASE}/10", json={"name": "X"}, headers=admin_headers)
        assert r.status_code == 404

    def test_patch_no_fields_noop(self, client, admin_headers):
        """Empty payload returns 204 without hitting the DB."""
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.patch(f"{BASE}/10", json={}, headers=admin_headers)
        assert r.status_code == 204

    def test_patch_status(self, client, admin_headers):
        """204 is returned when only status is updated."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.update_line_item_record",
                return_value=[{"id": 10}],
            ),
        ):
            r = client.patch(f"{BASE}/10", json={"status": 1}, headers=admin_headers)
        assert r.status_code == 204

    def test_patch_kind(self, client, admin_headers):
        """204 is returned when only kind is updated."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.update_line_item_record",
                return_value=[{"id": 10}],
            ),
        ):
            r = client.patch(
                f"{BASE}/10", json={"kind": "Diagnostic"}, headers=admin_headers
            )
        assert r.status_code == 204

    def test_patch_labels(self, client, admin_headers):
        """204 is returned when labels are updated."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.update_line_item_record",
                return_value=[{"id": 10}],
            ),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"labels": ["alignment", "high-priority"]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_aliases(self, client, admin_headers):
        """204 is returned when aliases are updated."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.update_line_item_record",
                return_value=[{"id": 10}],
            ),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"aliases": ["Q-01-A", "QuadA"]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_empty_name_rejected(self, client, admin_headers):
        """422 is returned when name is an empty string."""
        with patch("app.routers.line_items.beam_line_exists", return_value=True):
            r = client.patch(f"{BASE}/10", json={"name": ""}, headers=admin_headers)
        assert r.status_code == 422

    def test_patch_description(self, client, admin_headers):
        """204 is returned when only description is updated."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch("app.dependencies.exists_any_name", return_value=False),
            patch(
                "app.routers.line_items.update_line_item_record",
                return_value=[{"id": 10}],
            ),
        ):
            r = client.patch(
                f"{BASE}/10",
                json={"description": "updated desc"},
                headers=admin_headers,
            )
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# DELETE /api/v1/beam-lines/{beam_id}/line-items/{item_id}
# ---------------------------------------------------------------------------


class TestDeleteLineItem:
    def test_delete_success_no_links(self, client, admin_headers):
        """204 is returned when the item has no linked relationships."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_relationships",
                return_value=[{"id": 10, "linked_count": 0}],
            ),
            patch("app.routers.line_items.delete_line_item_record", return_value=[]),
        ):
            r = client.delete(f"{BASE}/10", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_conflict_has_links(self, client, admin_headers):
        """409 is returned when the item has relationships and force=False."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_relationships",
                return_value=[{"id": 10, "linked_count": 2}],
            ),
        ):
            r = client.delete(f"{BASE}/10", headers=admin_headers)
        assert r.status_code == 409

    def test_delete_force_with_links(self, client, admin_headers):
        """204 is returned with force=True even when relationships exist."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_relationships",
                return_value=[{"id": 10, "linked_count": 3}],
            ),
            patch("app.routers.line_items.delete_line_item_record", return_value=[]),
        ):
            r = client.delete(f"{BASE}/10?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_beam_not_found(self, client, admin_headers):
        """404 is returned when the parent beam line does not exist."""
        with patch("app.routers.line_items.beam_line_exists", return_value=False):
            r = client.delete(f"{BASE}/10", headers=admin_headers)
        assert r.status_code == 404

    def test_delete_item_not_found_silent(self, client, admin_headers):
        """204 is returned silently when the item itself does not exist."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_relationships",
                return_value=[],
            ),
        ):
            r = client.delete(f"{BASE}/999", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_force_no_links(self, client, admin_headers):
        """204 is returned with force=True even when there are no relationships."""
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_relationships",
                return_value=[{"id": 10, "linked_count": 0}],
            ),
            patch("app.routers.line_items.delete_line_item_record", return_value=[]),
        ):
            r = client.delete(f"{BASE}/10?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_calls_delete_record(self, client, admin_headers):
        """The CRUD delete function is called exactly once on a successful delete."""
        mock_delete = MagicMock(return_value=[])
        with (
            patch("app.routers.line_items.beam_line_exists", return_value=True),
            patch(
                "app.routers.line_items.get_line_item_relationships",
                return_value=[{"id": 5, "linked_count": 0}],
            ),
            patch("app.routers.line_items.delete_line_item_record", mock_delete),
        ):
            client.delete(f"{BASE}/5", headers=admin_headers)
        mock_delete.assert_called_once()
