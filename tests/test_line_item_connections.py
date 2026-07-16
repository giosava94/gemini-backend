"""Tests for the line-item connections REST API endpoints.

These tests exercise the HTTP layer only — all CRUD functions are patched so
no real Neo4j instance is required.
"""

from typing import Any
from unittest.mock import MagicMock, patch

BASE = "/api/v1/beam-lines/1/line-items/10/connections"


def _conn_record(cid: int, name: str, desc: str | None = None) -> dict[str, Any]:
    """Build a fake connected-item record matching get_line_item_connections output."""
    return {
        "id": cid,
        "name": name,
        "description": desc,
        "properties": {},
        "link": f"/api/v1/items/{cid}",
    }


# ---------------------------------------------------------------------------
# GET …/connections
# ---------------------------------------------------------------------------


class TestListLineItemConnections:
    def test_list_success(self, client):
        """200 with data and correct total is returned."""
        record = _conn_record(30, "RACK-01")
        record["properties"] = {"kind": "line", "position": 1}
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.get_total_line_item_connections",
                return_value=1,
            ),
            patch(
                "app.routers.line_item_connections.get_line_item_connections",
                return_value=[record],
            ),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 30
        assert body["data"][0]["link"] == "/api/v1/items/30"
        assert body["data"][0]["properties"] == {"kind": "line", "position": 1}

    def test_list_line_item_not_found(self, client):
        """404 is returned when the beam line or line item does not exist."""
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=False,
        ):
            r = client.get(BASE)
        assert r.status_code == 404

    def test_list_empty(self, client):
        """200 with empty data and total=0 when there are no connections."""
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.get_total_line_item_connections",
                return_value=0,
            ),
            patch(
                "app.routers.line_item_connections.get_line_item_connections",
                return_value=[],
            ),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []

    def test_list_pagination_params_reflected(self, client):
        """Custom page and per_page values are echoed back in the response."""
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.get_total_line_item_connections",
                return_value=0,
            ),
            patch(
                "app.routers.line_item_connections.get_line_item_connections",
                return_value=[],
            ),
        ):
            r = client.get(f"{BASE}?page=2&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 5

    def test_list_multiple_connections(self, client):
        """All returned records appear in the data list."""
        records = [_conn_record(1, "A"), _conn_record(2, "B")]
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.get_total_line_item_connections",
                return_value=2,
            ),
            patch(
                "app.routers.line_item_connections.get_line_item_connections",
                return_value=records,
            ),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2

    def test_list_invalid_page(self, client):
        """page=0 is rejected with 422."""
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.get(f"{BASE}?page=0")
        assert r.status_code == 422

    def test_list_per_page_over_limit(self, client):
        """per_page > 100 is rejected with 422."""
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.get(f"{BASE}?per_page=101")
        assert r.status_code == 422

    def test_list_link_url_format(self, client):
        """Each item in data has a link pointing to /api/v1/items/{id}."""
        records = [_conn_record(30, "RACK-01")]
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.get_total_line_item_connections",
                return_value=1,
            ),
            patch(
                "app.routers.line_item_connections.get_line_item_connections",
                return_value=records,
            ),
        ):
            r = client.get(BASE)
        assert r.json()["data"][0]["link"] == "/api/v1/items/30"

    def test_list_description_included(self, client):
        """Description from the record is included in the response."""
        records = [_conn_record(30, "RACK-01", desc="A rack unit")]
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.get_total_line_item_connections",
                return_value=1,
            ),
            patch(
                "app.routers.line_item_connections.get_line_item_connections",
                return_value=records,
            ),
        ):
            r = client.get(BASE)
        assert r.json()["data"][0]["description"] == "A rack unit"


# ---------------------------------------------------------------------------
# PUT …/connections
# ---------------------------------------------------------------------------


class TestPutLineItemConnections:
    def test_put_success(self, client, admin_headers):
        """201 is returned when all items exist and there are no conflicts."""
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.conn_items_exist", return_value=True
            ),
            patch(
                "app.routers.line_item_connections.update_line_item_connected_records",
                return_value=[],
            ),
        ):
            r = client.put(
                BASE,
                json={"items": [{"id": 30, "properties": {}}]},
                headers=admin_headers,
            )
        assert r.status_code == 201

    def test_put_accepts_connection_properties(self, client, admin_headers):
        """201 is returned and connection properties are forwarded to the CRUD layer."""
        mock_update = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.conn_items_exist", return_value=True
            ),
            patch(
                "app.routers.line_item_connections.update_line_item_connected_records",
                mock_update,
            ),
        ):
            r = client.put(
                BASE,
                json={
                    "items": [{"id": 30, "properties": {"kind": "line", "position": 2}}]
                },
                headers=admin_headers,
            )
        assert r.status_code == 201
        passed_connections = mock_update.call_args[0][3]
        assert passed_connections == [
            {"id": 30, "properties": {"kind": "line", "position": 2}}
        ]

    def test_put_duplicate_items(self, client, admin_headers):
        """400 is returned when the same target ID appears more than once."""
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.put(
                BASE,
                json={
                    "items": [
                        {"id": 30, "properties": {}},
                        {"id": 30, "properties": {}},
                    ]
                },
                headers=admin_headers,
            )
        assert r.status_code == 400

    def test_put_line_item_not_found(self, client, admin_headers):
        """404 is returned when the beam line or line item does not exist."""
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=False,
        ):
            r = client.put(
                BASE,
                json={"items": [{"id": 30, "properties": {}}]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_put_target_not_found(self, client, admin_headers):
        """404 is returned when conn_items_exist signals a missing target."""
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.conn_items_exist", return_value=False
            ),
        ):
            r = client.put(
                BASE,
                json={"items": [{"id": 999, "properties": {}}]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_put_multiple_connections(self, client, admin_headers):
        """201 is returned when multiple distinct targets are provided."""
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.conn_items_exist", return_value=True
            ),
            patch(
                "app.routers.line_item_connections.update_line_item_connected_records",
                return_value=[],
            ),
        ):
            r = client.put(
                BASE,
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
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.put(BASE, json={"items": []}, headers=admin_headers)
        assert r.status_code == 422

    def test_put_nested_properties_rejected(self, client, admin_headers):
        """422 is returned when connection properties contain nested dicts."""
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.put(
                BASE,
                json={"items": [{"id": 30, "properties": {"nested": {"key": "val"}}}]},
                headers=admin_headers,
            )
        assert r.status_code == 422

    def test_put_calls_update_with_correct_ids(self, client, admin_headers):
        """update_line_item_connected_records receives the correct beam_id and item_id."""
        mock_update = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.conn_items_exist", return_value=True
            ),
            patch(
                "app.routers.line_item_connections.update_line_item_connected_records",
                mock_update,
            ),
        ):
            client.put(
                BASE,
                json={"items": [{"id": 30, "properties": {}}]},
                headers=admin_headers,
            )
        args = mock_update.call_args[0]
        assert args[1] == 1  # beam_id
        assert args[2] == 10  # item_id


# ---------------------------------------------------------------------------
# DELETE …/connections
# ---------------------------------------------------------------------------


class TestDeleteLineItemConnections:
    def test_delete_success(self, client, admin_headers):
        """204 is returned when the line item exists and disconnection succeeds."""
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.disconnect_line_item_connected_records",
                return_value=[],
            ),
        ):
            r = client.request(
                "DELETE", BASE, json={"items": [30]}, headers=admin_headers
            )
        assert r.status_code == 204

    def test_delete_line_item_not_found(self, client, admin_headers):
        """404 is returned when the beam line or line item does not exist."""
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=False,
        ):
            r = client.request(
                "DELETE", BASE, json={"items": [30]}, headers=admin_headers
            )
        assert r.status_code == 404

    def test_delete_multiple_items(self, client, admin_headers):
        """204 is returned when disconnecting multiple items at once."""
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.disconnect_line_item_connected_records",
                return_value=[],
            ),
        ):
            r = client.request(
                "DELETE", BASE, json={"items": [10, 11, 12]}, headers=admin_headers
            )
        assert r.status_code == 204

    def test_delete_duplicate_ids_deduped(self, client, admin_headers):
        """Duplicate IDs are silently deduplicated by the schema (ListIntNoDuplicates)."""
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.disconnect_line_item_connected_records",
                return_value=[],
            ),
        ):
            r = client.request(
                "DELETE", BASE, json={"items": [30, 30]}, headers=admin_headers
            )
        assert r.status_code == 204

    def test_delete_empty_items_rejected(self, client, admin_headers):
        """422 is returned when the items list is empty (schema min_length=1)."""
        with patch(
            "app.routers.line_item_connections.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.request(
                "DELETE", BASE, json={"items": []}, headers=admin_headers
            )
        assert r.status_code == 422

    def test_delete_calls_disconnect_with_correct_args(self, client, admin_headers):
        """disconnect_line_item_connected_records is called with beam_id, item_id and targets."""
        mock_disconnect = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.disconnect_line_item_connected_records",
                mock_disconnect,
            ),
        ):
            client.request(
                "DELETE", BASE, json={"items": [5, 6]}, headers=admin_headers
            )
        mock_disconnect.assert_called_once()
        args = mock_disconnect.call_args[0]
        assert args[1] == 1  # beam_id
        assert args[2] == 10  # item_id

    def test_delete_called_once(self, client, admin_headers):
        """The CRUD disconnect function is called exactly once."""
        mock_disconnect = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.line_item_connections.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_connections.disconnect_line_item_connected_records",
                mock_disconnect,
            ),
        ):
            client.request("DELETE", BASE, json={"items": [30]}, headers=admin_headers)
        mock_disconnect.assert_called_once()
