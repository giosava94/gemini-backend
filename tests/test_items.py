"""Tests for the items REST API endpoints.

These tests exercise the HTTP layer only — all CRUD functions and DB helpers
are patched so no real Neo4j or Redis instance is required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BASE = "/api/v1/items"

VALID_PAYLOAD = {
    "name": "RACK-01",
    "kind": "Rack",
    "status": 0,
    "connections": [],
}


def _make_item_node(
    iid, name, kind="Rack", status=0, desc=None, labels=None, aliases=None
):
    """Return a MagicMock that behaves like a Neo4j Item node."""
    labels = labels if labels is not None else []
    aliases = aliases if aliases is not None else []
    node = MagicMock()
    node.__getitem__ = lambda s, k: {
        "id": iid,
        "name": name,
        "kind": kind,
        "status": status,
        "labels": labels,
        "aliases": aliases,
    }[k]
    node.get = lambda k, d=None: {
        "description": desc,
        "labels": labels,
        "aliases": aliases,
    }.get(k, d)
    return node


def _make_item_record(
    iid, name, kind="Rack", status=0, desc=None, labels=None, aliases=None
):
    return {"i": _make_item_node(iid, name, kind, status, desc, labels, aliases)}


# ---------------------------------------------------------------------------
# POST /api/v1/items
# ---------------------------------------------------------------------------


class TestCreateItem:
    def test_create_success(self, client, admin_headers):
        """201 and the new ID are returned when name is unique and no connections."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.conn_items_exist", return_value=True),
            patch("app.routers.items.create", return_value=[{"id": 42}]),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 201
        assert r.json() == {"id": 42}

    def test_create_success_with_description(self, client, admin_headers):
        """201 is returned when an optional description is included."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.conn_items_exist", return_value=True),
            patch("app.routers.items.create", return_value=[{"id": 7}]),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "description": "A rack unit"},
                headers=admin_headers,
            )
        assert r.status_code == 201
        assert r.json() == {"id": 7}

    def test_create_conflict(self, client, admin_headers):
        """409 is returned when a node with the same name already exists."""
        with patch("app.dependencies.exists_any_name", return_value=True):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 409

    def test_create_connection_not_found(self, client, admin_headers):
        """404 is raised when conn_items_exist signals missing connections."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.conn_items_exist", return_value=False),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "connections": [999]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_create_db_failure(self, client, admin_headers):
        """500 is raised when the CRUD create function returns an empty list."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.conn_items_exist", return_value=True),
            patch("app.routers.items.create", return_value=[]),
        ):
            r = client.post(BASE, json=VALID_PAYLOAD, headers=admin_headers)
        assert r.status_code == 500

    def test_create_invalid_kind(self, client, admin_headers):
        """422 is returned when an unsupported kind value is supplied."""
        r = client.post(
            BASE,
            json={**VALID_PAYLOAD, "kind": "Unknown"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_create_empty_name_rejected(self, client, admin_headers):
        """422 is returned when name is an empty string."""
        r = client.post(BASE, json={**VALID_PAYLOAD, "name": ""}, headers=admin_headers)
        assert r.status_code == 422

    def test_create_missing_name_rejected(self, client, admin_headers):
        """422 is returned when the required name field is absent."""
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "name"}
        r = client.post(BASE, json=payload, headers=admin_headers)
        assert r.status_code == 422

    def test_create_with_labels(self, client, admin_headers):
        """Labels list is accepted and forwarded to the CRUD layer."""
        mock_create = MagicMock(return_value=[{"id": 42}])
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.conn_items_exist", return_value=True),
            patch("app.routers.items.create", mock_create),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "labels": ["rack", "service"]},
                headers=admin_headers,
            )
        assert r.status_code == 201
        passed_payload = mock_create.call_args[0][1]
        assert passed_payload["labels"] == ["rack", "service"]

    def test_create_with_aliases(self, client, admin_headers):
        """Aliases list is accepted and forwarded to the CRUD layer."""
        mock_create = MagicMock(return_value=[{"id": 42}])
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.conn_items_exist", return_value=True),
            patch("app.routers.items.create", mock_create),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "aliases": ["RACK-01-A", "RACK-GROUP"]},
                headers=admin_headers,
            )
        assert r.status_code == 201
        passed_payload = mock_create.call_args[0][1]
        assert passed_payload["aliases"] == ["RACK-01-A", "RACK-GROUP"]

    def test_create_with_connections_success(self, client, admin_headers):
        """201 is returned when all requested connection IDs exist."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.conn_items_exist", return_value=True),
            patch("app.routers.items.create", return_value=[{"id": 5}]),
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
            "MTBX",
            "Rack",
            "BACCO",
            "Primary_Pump",
            "Turbomolecular_Pump",
            "Flange",
            "Line",
            "Box",
        ],
    )
    def test_create_all_valid_kinds(self, client, admin_headers, kind):
        """Every valid kind value is accepted with 201."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.conn_items_exist", return_value=True),
            patch("app.routers.items.create", return_value=[{"id": 1}]),
        ):
            r = client.post(
                BASE,
                json={**VALID_PAYLOAD, "kind": kind},
                headers=admin_headers,
            )
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/items
# ---------------------------------------------------------------------------


class TestListItems:
    def test_list_empty(self, client):
        """Returns empty data list with correct pagination metadata."""
        with (
            patch("app.routers.items.get_total_item_records", return_value=0),
            patch("app.routers.items.get_item_records", return_value=[]),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []
        assert body["page"] == 1
        assert body["per_page"] == 10

    def test_list_with_results(self, client):
        """Data list and total reflect the values returned by CRUD functions."""
        records = [{"id": 42, "name": "RACK-01", "description": None}]
        with (
            patch("app.routers.items.get_total_item_records", return_value=1),
            patch("app.routers.items.get_item_records", return_value=records),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 42
        assert body["data"][0]["name"] == "RACK-01"

    def test_list_multiple_results(self, client):
        """All returned records are present in the response data list."""
        records = [
            {"id": 1, "name": "RACK-01", "description": None},
            {"id": 2, "name": "MTBX-01", "description": "A box"},
        ]
        with (
            patch("app.routers.items.get_total_item_records", return_value=2),
            patch("app.routers.items.get_item_records", return_value=records),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2

    def test_list_pagination_params_reflected(self, client):
        """Custom page and per_page values are echoed back in the response."""
        with (
            patch("app.routers.items.get_total_item_records", return_value=0),
            patch("app.routers.items.get_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?page=3&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 3
        assert body["per_page"] == 5

    def test_list_invalid_sort(self, client):
        """An unsupported sort key triggers a 422 before any DB call."""
        r = client.get(f"{BASE}?sort=invalid")
        assert r.status_code == 422

    def test_list_sort_by_name(self, client):
        """Sorting by 'name' is accepted and returns 200."""
        with (
            patch("app.routers.items.get_total_item_records", return_value=0),
            patch("app.routers.items.get_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?sort=name")
        assert r.status_code == 200

    def test_list_sort_by_kind(self, client):
        """Sorting by 'kind' is accepted and returns 200."""
        with (
            patch("app.routers.items.get_total_item_records", return_value=0),
            patch("app.routers.items.get_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?sort=kind")
        assert r.status_code == 200

    def test_list_name_filter(self, client):
        """Name substring filter is accepted and returns 200."""
        with (
            patch("app.routers.items.get_total_item_records", return_value=0),
            patch("app.routers.items.get_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?name=rack")
        assert r.status_code == 200

    def test_list_alias_filter(self, client):
        """Alias substring filter is accepted and returns 200."""
        with (
            patch("app.routers.items.get_total_item_records", return_value=0),
            patch("app.routers.items.get_item_records", return_value=[]),
        ):
            r = client.get(f"{BASE}?alias=rack")
        assert r.status_code == 200

    def test_list_invalid_page(self, client):
        """page=0 is rejected with 422 by FastAPI's query validator."""
        r = client.get(f"{BASE}?page=0")
        assert r.status_code == 422

    def test_list_per_page_over_limit(self, client):
        """per_page > 100 is rejected with 422 by FastAPI's query validator."""
        r = client.get(f"{BASE}?per_page=101")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/items/{item_id}
# ---------------------------------------------------------------------------


class TestGetItem:
    def _detail_payload(self, iid=42, name="RACK-01", labels=None, aliases=None):
        return {
            "links": {"connections": f"/api/v1/items/{iid}/connections"},
            "data": {
                "id": iid,
                "name": name,
                "description": None,
                "kind": "Rack",
                "status": 0,
                "labels": labels or [],
                "aliases": aliases or [],
            },
        }

    def test_get_success(self, client):
        """200 with links and data is returned for an existing item."""
        with patch(
            "app.routers.items.get_item_record",
            new=AsyncMock(return_value=self._detail_payload()),
        ):
            r = client.get(f"{BASE}/42")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["id"] == 42
        assert "connections" in body["links"]

    def test_get_not_found(self, client):
        """404 is returned when the CRUD function resolves to None."""
        with patch(
            "app.routers.items.get_item_record",
            new=AsyncMock(return_value=None),
        ):
            r = client.get(f"{BASE}/999")
        assert r.status_code == 404

    def test_get_returns_labels(self, client):
        """Labels list from the CRUD result is present in the response."""
        with patch(
            "app.routers.items.get_item_record",
            new=AsyncMock(
                return_value=self._detail_payload(labels=["rack", "service"])
            ),
        ):
            r = client.get(f"{BASE}/42")
        assert r.status_code == 200
        assert r.json()["data"]["labels"] == ["rack", "service"]

    def test_get_returns_aliases(self, client):
        """Aliases list from the CRUD result is present in the response."""
        with patch(
            "app.routers.items.get_item_record",
            new=AsyncMock(
                return_value=self._detail_payload(aliases=["R-1", "RackOne"])
            ),
        ):
            r = client.get(f"{BASE}/42")
        assert r.status_code == 200
        assert r.json()["data"]["aliases"] == ["R-1", "RackOne"]

    def test_get_etag_header_present(self, client):
        """ETag header is set on a successful 200 response."""
        with patch(
            "app.routers.items.get_item_record",
            new=AsyncMock(return_value=self._detail_payload()),
        ):
            r = client.get(f"{BASE}/42")
        assert r.status_code == 200
        assert "etag" in r.headers

    def test_get_304_when_etag_matches(self, client):
        """304 Not Modified is returned when If-None-Match matches the ETag."""
        payload = self._detail_payload()
        with patch(
            "app.routers.items.get_item_record",
            new=AsyncMock(return_value=payload),
        ):
            r1 = client.get(f"{BASE}/42")
            etag = r1.headers["etag"]

        with patch(
            "app.routers.items.get_item_record",
            new=AsyncMock(return_value=payload),
        ):
            r2 = client.get(f"{BASE}/42", headers={"If-None-Match": etag})
        assert r2.status_code == 304

    def test_get_links_url_contains_item_id(self, client):
        """The connections link URL contains the correct item_id."""
        with patch(
            "app.routers.items.get_item_record",
            new=AsyncMock(return_value=self._detail_payload(iid=99)),
        ):
            r = client.get(f"{BASE}/99")
        assert r.status_code == 200
        assert "99" in r.json()["links"]["connections"]


# ---------------------------------------------------------------------------
# PATCH /api/v1/items/{item_id}
# ---------------------------------------------------------------------------


class TestPatchItem:
    def test_patch_name_success(self, client, admin_headers):
        """204 is returned when a name update succeeds."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.update_item_record", return_value=[{"id": 42}]),
        ):
            r = client.patch(
                f"{BASE}/42",
                json={"name": "RACK-01-NEW"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_name_conflict(self, client, admin_headers):
        """409 is returned when a node with the requested name already exists."""
        with patch("app.dependencies.exists_any_name", return_value=True):
            r = client.patch(
                f"{BASE}/42", json={"name": "Taken"}, headers=admin_headers
            )
        assert r.status_code == 409

    def test_patch_not_found(self, client, admin_headers):
        """404 is returned when the CRUD function returns an empty list."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.update_item_record", return_value=[]),
        ):
            r = client.patch(f"{BASE}/999", json={"name": "X"}, headers=admin_headers)
        assert r.status_code == 404

    def test_patch_no_fields_noop(self, client, admin_headers):
        """Empty payload returns 204 without hitting the DB."""
        r = client.patch(f"{BASE}/42", json={}, headers=admin_headers)
        assert r.status_code == 204

    def test_patch_status(self, client, admin_headers):
        """204 is returned when only status is updated."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.update_item_record", return_value=[{"id": 42}]),
        ):
            r = client.patch(f"{BASE}/42", json={"status": 2}, headers=admin_headers)
        assert r.status_code == 204

    def test_patch_description(self, client, admin_headers):
        """204 is returned when only description is updated."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.update_item_record", return_value=[{"id": 42}]),
        ):
            r = client.patch(
                f"{BASE}/42",
                json={"description": "updated"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_labels(self, client, admin_headers):
        """204 is returned when labels are updated."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.update_item_record", return_value=[{"id": 42}]),
        ):
            r = client.patch(
                f"{BASE}/42",
                json={"labels": ["rack", "service"]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_aliases(self, client, admin_headers):
        """204 is returned when aliases are updated."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.update_item_record", return_value=[{"id": 42}]),
        ):
            r = client.patch(
                f"{BASE}/42",
                json={"aliases": ["R-1", "RackOneUpdated"]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_empty_name_rejected(self, client, admin_headers):
        """422 is returned when name is an empty string."""
        r = client.patch(f"{BASE}/42", json={"name": ""}, headers=admin_headers)
        assert r.status_code == 422

    def test_patch_all_fields(self, client, admin_headers):
        """204 is returned when multiple fields are updated in one request."""
        with (
            patch("app.dependencies.exists_any_name", return_value=False),
            patch("app.routers.items.update_item_record", return_value=[{"id": 42}]),
        ):
            r = client.patch(
                f"{BASE}/42",
                json={
                    "name": "RACK-UPDATED",
                    "description": "desc",
                    "status": 1,
                    "labels": ["l"],
                    "aliases": ["a"],
                },
                headers=admin_headers,
            )
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# DELETE /api/v1/items/{item_id}
# ---------------------------------------------------------------------------


class TestDeleteItem:
    def test_delete_success_no_links(self, client, admin_headers):
        """204 is returned when the item has no connected relationships."""
        with (
            patch(
                "app.routers.items.get_item_relationships",
                return_value=[{"id": 42, "linked_count": 0}],
            ),
            patch("app.routers.items.delete_item_record", return_value=[]),
        ):
            r = client.delete(f"{BASE}/42", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_conflict_has_links(self, client, admin_headers):
        """409 is returned when the item has connections and force=False."""
        with patch(
            "app.routers.items.get_item_relationships",
            return_value=[{"id": 42, "linked_count": 1}],
        ):
            r = client.delete(f"{BASE}/42", headers=admin_headers)
        assert r.status_code == 409

    def test_delete_force_with_links(self, client, admin_headers):
        """204 is returned with force=True even when connections exist."""
        with (
            patch(
                "app.routers.items.get_item_relationships",
                return_value=[{"id": 42, "linked_count": 3}],
            ),
            patch("app.routers.items.delete_item_record", return_value=[]),
        ):
            r = client.delete(f"{BASE}/42?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_not_found_silent(self, client, admin_headers):
        """204 is returned silently when the item does not exist (empty records)."""
        with patch("app.routers.items.get_item_relationships", return_value=[]):
            r = client.delete(f"{BASE}/999", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_force_no_links(self, client, admin_headers):
        """204 is returned with force=True when no connections exist either."""
        with (
            patch(
                "app.routers.items.get_item_relationships",
                return_value=[{"id": 42, "linked_count": 0}],
            ),
            patch("app.routers.items.delete_item_record", return_value=[]),
        ):
            r = client.delete(f"{BASE}/42?force=true", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_calls_delete_record(self, client, admin_headers):
        """The CRUD delete function is called exactly once on a successful delete."""
        mock_delete = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.items.get_item_relationships",
                return_value=[{"id": 5, "linked_count": 0}],
            ),
            patch("app.routers.items.delete_item_record", mock_delete),
        ):
            client.delete(f"{BASE}/5", headers=admin_headers)
        mock_delete.assert_called_once()
