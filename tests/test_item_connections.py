"""Tests for the item connections REST API endpoints.

These tests exercise the HTTP layer only — all CRUD functions are patched so
no real Neo4j instance is required.
"""

from typing import Any
from unittest.mock import MagicMock, patch

CONN_BASE = "/api/v1/items/42/connections"
LI_CONN_BASE = "/api/v1/items/42/line-item-connections"


def _conn_record(cid: int, name: str, desc: str | None = None) -> dict[str, Any]:
    """Build a fake connected-item record for get_connected_items."""
    return {
        "id": cid,
        "name": name,
        "description": desc,
        "properties": {},
        "link": f"/api/v1/items/{cid}",
    }


def _li_conn_record(
    lid: int, name: str, beam_id: int = 1, desc: str | None = None
) -> dict[str, Any]:
    """Build a fake connected-line-item record for get_connected_line_items."""
    return {
        "id": lid,
        "name": name,
        "description": desc,
        "link": f"/api/v1/beam-lines/{beam_id}/line-items/{lid}",
    }


# ---------------------------------------------------------------------------
# PUT /api/v1/items/{item_id}/connections
# ---------------------------------------------------------------------------


class TestPutItemConnections:
    def test_put_success(self, client, admin_headers):
        """201 is returned when all items exist and there are no conflicts."""
        with (
            patch("app.routers.item_connections.conn_items_exist", return_value=True),
            patch("app.routers.item_connections.connect_item_records", return_value=[]),
        ):
            r = client.put(
                CONN_BASE,
                json={"items": [{"id": 10, "properties": {}}]},
                headers=admin_headers,
            )
        assert r.status_code == 201

    def test_put_accepts_connection_properties(self, client, admin_headers):
        """201 is returned and connection properties are forwarded to the CRUD layer."""
        mock_connect = MagicMock(return_value=[])
        with (
            patch("app.routers.item_connections.conn_items_exist", return_value=True),
            patch("app.routers.item_connections.connect_item_records", mock_connect),
        ):
            r = client.put(
                CONN_BASE,
                json={
                    "items": [{"id": 10, "properties": {"kind": "rack", "index": 3}}]
                },
                headers=admin_headers,
            )
        assert r.status_code == 201
        passed_connections = mock_connect.call_args[0][2]
        assert passed_connections == [
            {"id": 10, "properties": {"kind": "rack", "index": 3}}
        ]

    def test_put_self_reference(self, client, admin_headers):
        """400 is returned when an item tries to connect to itself."""
        r = client.put(
            CONN_BASE,
            json={"items": [{"id": 42, "properties": {}}]},
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_put_duplicate_items(self, client, admin_headers):
        """400 is returned when the same target ID appears more than once."""
        r = client.put(
            CONN_BASE,
            json={
                "items": [
                    {"id": 10, "properties": {}},
                    {"id": 10, "properties": {}},
                ]
            },
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_put_item_not_found(self, client, admin_headers):
        """404 is returned when the source or any target item does not exist."""
        with patch("app.routers.item_connections.conn_items_exist", return_value=False):
            r = client.put(
                CONN_BASE,
                json={"items": [{"id": 10, "properties": {}}]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_put_target_not_found(self, client, admin_headers):
        """404 is returned when conn_items_exist signals a missing target."""
        with patch("app.routers.item_connections.conn_items_exist", return_value=False):
            r = client.put(
                CONN_BASE,
                json={"items": [{"id": 999, "properties": {}}]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_put_multiple_connections(self, client, admin_headers):
        """201 is returned when multiple distinct targets are provided."""
        with (
            patch("app.routers.item_connections.conn_items_exist", return_value=True),
            patch("app.routers.item_connections.connect_item_records", return_value=[]),
        ):
            r = client.put(
                CONN_BASE,
                json={
                    "items": [
                        {"id": 1, "properties": {}},
                        {"id": 2, "properties": {}},
                    ]
                },
                headers=admin_headers,
            )
        assert r.status_code == 201

    def test_put_empty_items_rejected(self, client, admin_headers):
        """422 is returned when the items list is empty (schema min_length=1)."""
        r = client.put(
            CONN_BASE,
            json={"items": []},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_put_nested_properties_rejected(self, client, admin_headers):
        """422 is returned when properties contain nested dicts."""
        r = client.put(
            CONN_BASE,
            json={"items": [{"id": 10, "properties": {"nested": {"key": "value"}}}]},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_put_calls_connect_with_correct_item_id(self, client, admin_headers):
        """The source item_id is forwarded correctly to connect_item_records."""
        mock_connect = MagicMock(return_value=[])
        with (
            patch("app.routers.item_connections.conn_items_exist", return_value=True),
            patch("app.routers.item_connections.connect_item_records", mock_connect),
        ):
            client.put(
                CONN_BASE,
                json={"items": [{"id": 10, "properties": {}}]},
                headers=admin_headers,
            )
        assert mock_connect.call_args[0][1] == 42


# ---------------------------------------------------------------------------
# GET /api/v1/items/{item_id}/connections
# ---------------------------------------------------------------------------


class TestListItemConnections:
    def test_list_success(self, client):
        """200 with data and correct total is returned."""
        records = [_conn_record(10, "RACK-01")]
        records[0]["properties"] = {"kind": "rack", "index": 2}
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_items", return_value=1
            ),
            patch(
                "app.routers.item_connections.get_connected_items", return_value=records
            ),
        ):
            r = client.get(CONN_BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 10
        assert body["data"][0]["properties"] == {"kind": "rack", "index": 2}

    def test_list_item_not_found(self, client):
        """404 is returned when the item does not exist."""
        with patch("app.routers.item_connections.item_exists", return_value=False):
            r = client.get(CONN_BASE)
        assert r.status_code == 404

    def test_list_empty(self, client):
        """200 with empty data and total=0 is returned when there are no connections."""
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_items", return_value=0
            ),
            patch("app.routers.item_connections.get_connected_items", return_value=[]),
        ):
            r = client.get(CONN_BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []

    def test_list_pagination_params_reflected(self, client):
        """Custom page and per_page values are echoed back in the response."""
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_items", return_value=0
            ),
            patch("app.routers.item_connections.get_connected_items", return_value=[]),
        ):
            r = client.get(f"{CONN_BASE}?page=2&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 5

    def test_list_multiple_connections(self, client):
        """All returned records appear in the data list."""
        records = [_conn_record(1, "A"), _conn_record(2, "B")]
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_items", return_value=2
            ),
            patch(
                "app.routers.item_connections.get_connected_items", return_value=records
            ),
        ):
            r = client.get(CONN_BASE)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2

    def test_list_invalid_page(self, client):
        """page=0 is rejected with 422 by FastAPI's query validator."""
        r = client.get(f"{CONN_BASE}?page=0")
        assert r.status_code == 422

    def test_list_per_page_over_limit(self, client):
        """per_page > 100 is rejected with 422."""
        r = client.get(f"{CONN_BASE}?per_page=101")
        assert r.status_code == 422

    def test_list_link_url_format(self, client):
        """Each item in data has a link pointing to /api/v1/items/{id}."""
        records = [_conn_record(10, "RACK-01")]
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_items", return_value=1
            ),
            patch(
                "app.routers.item_connections.get_connected_items", return_value=records
            ),
        ):
            r = client.get(CONN_BASE)
        assert "/api/v1/items/10" in r.json()["data"][0]["link"]


# ---------------------------------------------------------------------------
# DELETE /api/v1/items/{item_id}/connections
# ---------------------------------------------------------------------------


class TestDeleteItemConnections:
    def test_delete_success(self, client, admin_headers):
        """204 is returned when the item exists and disconnection succeeds."""
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.disconnect_item_records", return_value=[]
            ),
        ):
            r = client.request(
                "DELETE",
                CONN_BASE,
                json={"items": [10]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_delete_item_not_found(self, client, admin_headers):
        """404 is returned when the item does not exist."""
        with patch("app.routers.item_connections.item_exists", return_value=False):
            r = client.request(
                "DELETE",
                CONN_BASE,
                json={"items": [10]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_delete_multiple_items(self, client, admin_headers):
        """204 is returned when disconnecting multiple items at once."""
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.disconnect_item_records", return_value=[]
            ),
        ):
            r = client.request(
                "DELETE",
                CONN_BASE,
                json={"items": [10, 11, 12]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_delete_duplicate_ids_deduped(self, client, admin_headers):
        """Duplicate IDs in the delete list are silently deduplicated (schema behaviour)."""
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.disconnect_item_records", return_value=[]
            ),
        ):
            r = client.request(
                "DELETE",
                CONN_BASE,
                json={"items": [10, 10]},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_delete_empty_items_rejected(self, client, admin_headers):
        """422 is returned when the items list is empty (schema min_length=1)."""
        r = client.request(
            "DELETE",
            CONN_BASE,
            json={"items": []},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_delete_calls_disconnect_with_correct_args(self, client, admin_headers):
        """disconnect_item_records is called with the correct item_id and target list."""
        mock_disconnect = MagicMock(return_value=[])
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.disconnect_item_records", mock_disconnect
            ),
        ):
            client.request(
                "DELETE",
                CONN_BASE,
                json={"items": [5, 6]},
                headers=admin_headers,
            )
        mock_disconnect.assert_called_once()
        assert mock_disconnect.call_args[0][1] == 42


# ---------------------------------------------------------------------------
# GET /api/v1/items/{item_id}/line-item-connections
# ---------------------------------------------------------------------------


class TestListItemLineItemConnections:
    def test_list_success(self, client):
        """200 with data and correct link URL is returned."""
        records = [_li_conn_record(5, "QD01", beam_id=1)]
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_line_items",
                return_value=1,
            ),
            patch(
                "app.routers.item_connections.get_connected_line_items",
                return_value=records,
            ),
        ):
            r = client.get(LI_CONN_BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 5
        assert "/beam-lines/1/line-items/5" in body["data"][0]["link"]

    def test_list_item_not_found(self, client):
        """404 is returned when the item does not exist."""
        with patch("app.routers.item_connections.item_exists", return_value=False):
            r = client.get(LI_CONN_BASE)
        assert r.status_code == 404

    def test_list_empty(self, client):
        """200 with empty data and total=0 is returned when no line items are connected."""
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_line_items",
                return_value=0,
            ),
            patch(
                "app.routers.item_connections.get_connected_line_items", return_value=[]
            ),
        ):
            r = client.get(LI_CONN_BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []

    def test_list_pagination_params_reflected(self, client):
        """Custom page and per_page values are echoed back in the response."""
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_line_items",
                return_value=0,
            ),
            patch(
                "app.routers.item_connections.get_connected_line_items", return_value=[]
            ),
        ):
            r = client.get(f"{LI_CONN_BASE}?page=2&per_page=20")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 20

    def test_list_multiple_line_items(self, client):
        """All returned line item records appear in the data list."""
        records = [
            _li_conn_record(5, "QD01", beam_id=1),
            _li_conn_record(6, "QF01", beam_id=1),
        ]
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_line_items",
                return_value=2,
            ),
            patch(
                "app.routers.item_connections.get_connected_line_items",
                return_value=records,
            ),
        ):
            r = client.get(LI_CONN_BASE)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2

    def test_list_link_url_contains_beam_and_item_ids(self, client):
        """The link URL includes both the beam_id and the line item id."""
        records = [_li_conn_record(7, "QD02", beam_id=3)]
        with (
            patch("app.routers.item_connections.item_exists", return_value=True),
            patch(
                "app.routers.item_connections.get_total_connected_line_items",
                return_value=1,
            ),
            patch(
                "app.routers.item_connections.get_connected_line_items",
                return_value=records,
            ),
        ):
            r = client.get(LI_CONN_BASE)
        link = r.json()["data"][0]["link"]
        assert "3" in link
        assert "7" in link

    def test_list_invalid_page(self, client):
        """page=0 is rejected with 422."""
        r = client.get(f"{LI_CONN_BASE}?page=0")
        assert r.status_code == 422

    def test_list_per_page_over_limit(self, client):
        """per_page > 100 is rejected with 422."""
        r = client.get(f"{LI_CONN_BASE}?per_page=101")
        assert r.status_code == 422
