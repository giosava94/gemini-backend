"""Tests for the line-item adjacents REST API endpoints.

These tests exercise the HTTP layer only — all CRUD functions and DB helpers
are patched so no real Neo4j instance is required.

Notes on router architecture:
- GET and DELETE use ``beam_line_and_line_item_exist`` (imported from
  ``app.cruds.line_item_connections``) — patch at
  ``app.routers.line_item_adjacents.beam_line_and_line_item_exist``.
- GET delegates listing to ``get_total_line_item_adjacent_relationships`` and
  ``get_line_item_adjacent_relationships`` from the CRUD module.
- DELETE delegates to ``disconnect_adjacents`` from the CRUD module.
- PUT and PATCH call ``run_query`` directly for inline existence / conflict
  checks — patch ``app.routers.line_item_adjacents.run_query``.
"""

from unittest.mock import MagicMock, patch

BASE = "/api/v1/beam-lines/1/line-items/10/adjacents"


def _adj_data(aid, name, position="Previous", index=None, desc=None):
    """Build a plain-dict adjacent record matching get_line_item_adjacent_relationships output."""
    return {
        "id": aid,
        "name": name,
        "description": desc,
        "position": position,
        "index": index,
        "link": f"/api/v1/beam-lines/1/line-items/{aid}",
    }


# ---------------------------------------------------------------------------
# GET …/adjacents
# ---------------------------------------------------------------------------


class TestListAdjacents:
    def test_list_success(self, client):
        """200 with data and correct total is returned."""
        records = [_adj_data(20, "QD02", "Previous")]
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.get_total_line_item_adjacent_relationships",
                return_value=1,
            ),
            patch(
                "app.routers.line_item_adjacents.get_line_item_adjacent_relationships",
                return_value=records,
            ),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == 20
        assert body["data"][0]["position"] == "Previous"

    def test_list_item_not_found(self, client):
        """404 is returned when the beam line or line item does not exist."""
        with patch(
            "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
            return_value=False,
        ):
            r = client.get(BASE)
        assert r.status_code == 404

    def test_list_empty(self, client):
        """200 with empty data and total=0 when there are no adjacents."""
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.get_total_line_item_adjacent_relationships",
                return_value=0,
            ),
            patch(
                "app.routers.line_item_adjacents.get_line_item_adjacent_relationships",
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
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.get_total_line_item_adjacent_relationships",
                return_value=0,
            ),
            patch(
                "app.routers.line_item_adjacents.get_line_item_adjacent_relationships",
                return_value=[],
            ),
        ):
            r = client.get(f"{BASE}?page=2&per_page=5")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 5

    def test_list_invalid_sort_key(self, client):
        """422 is returned for an unsupported sort key."""
        with patch(
            "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.get(f"{BASE}?sort=invalid")
        assert r.status_code == 422

    def test_list_sort_by_position(self, client):
        """Sorting by 'position' is accepted and returns 200."""
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.get_total_line_item_adjacent_relationships",
                return_value=0,
            ),
            patch(
                "app.routers.line_item_adjacents.get_line_item_adjacent_relationships",
                return_value=[],
            ),
        ):
            r = client.get(f"{BASE}?sort=position")
        assert r.status_code == 200

    def test_list_filter_by_position(self, client):
        """Filtering by a valid position value returns 200."""
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.get_total_line_item_adjacent_relationships",
                return_value=0,
            ),
            patch(
                "app.routers.line_item_adjacents.get_line_item_adjacent_relationships",
                return_value=[],
            ),
        ):
            r = client.get(f"{BASE}?position=previous")
        assert r.status_code == 200

    def test_list_invalid_position(self, client):
        """422 is returned for an unrecognised position filter value."""
        with patch(
            "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.get(f"{BASE}?position=invalid")
        assert r.status_code == 422

    def test_list_multiple_results(self, client):
        """All returned records appear in the data list."""
        records = [
            _adj_data(20, "QD02", "Previous"),
            _adj_data(21, "QF01", "Next"),
        ]
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.get_total_line_item_adjacent_relationships",
                return_value=2,
            ),
            patch(
                "app.routers.line_item_adjacents.get_line_item_adjacent_relationships",
                return_value=records,
            ),
        ):
            r = client.get(BASE)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2

    def test_list_link_url_format(self, client):
        """Each adjacent record has a link pointing to the correct beam-line/line-item URL."""
        records = [_adj_data(20, "QD02")]
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.get_total_line_item_adjacent_relationships",
                return_value=1,
            ),
            patch(
                "app.routers.line_item_adjacents.get_line_item_adjacent_relationships",
                return_value=records,
            ),
        ):
            r = client.get(BASE)
        link = r.json()["data"][0]["link"]
        assert "beam-lines" in link
        assert "20" in link

    def test_list_invalid_page(self, client):
        """page=0 is rejected with 422."""
        with patch(
            "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.get(f"{BASE}?page=0")
        assert r.status_code == 422

    def test_list_per_page_over_limit(self, client):
        """per_page > 100 is rejected with 422."""
        with patch(
            "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.get(f"{BASE}?per_page=101")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# PUT …/adjacents
# ---------------------------------------------------------------------------


class TestPutAdjacents:
    """PUT calls run_query directly for the existence and conflict checks."""

    def test_put_success(self, client, admin_headers):
        """201 is returned when targets exist and there are no index conflicts."""
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
                json={"items": [{"id": 20, "position": "Previous"}]},
                headers=admin_headers,
            )
        assert r.status_code == 201

    def test_put_self_reference(self, client, admin_headers):
        """400 is returned when an item tries to be adjacent to itself."""
        r = client.put(
            BASE,
            json={"items": [{"id": 10, "position": "Previous"}]},
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_put_duplicate_items(self, client, admin_headers):
        """400 is returned when the same (id, position) pair appears more than once."""
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
        """400 is returned when two items share the same (position, index) pair."""
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
        """404 is returned when the target existence check fails."""
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

    def test_put_targets_query_empty(self, client, admin_headers):
        """404 is returned when the existence query returns no records."""
        with patch("app.routers.line_item_adjacents.run_query", return_value=[]):
            r = client.put(
                BASE,
                json={"items": [{"id": 999, "position": "Next"}]},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_put_index_conflict(self, client, admin_headers):
        """400 is returned when the conflict check detects a duplicate index."""
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
        """201 is returned when the Dual position is used."""
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

    def test_put_multiple_items_success(self, client, admin_headers):
        """201 is returned when multiple distinct adjacents are provided."""
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
                json={
                    "items": [
                        {"id": 20, "position": "Previous"},
                        {"id": 21, "position": "Next"},
                    ]
                },
                headers=admin_headers,
            )
        assert r.status_code == 201

    def test_put_empty_items_rejected(self, client, admin_headers):
        """422 is returned when the items list is empty (schema min_length=1)."""
        r = client.put(BASE, json={"items": []}, headers=admin_headers)
        assert r.status_code == 422

    def test_put_invalid_position_rejected(self, client, admin_headers):
        """422 is returned when an invalid position string is supplied."""
        r = client.put(
            BASE,
            json={"items": [{"id": 20, "position": "BadPos"}]},
            headers=admin_headers,
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE …/adjacents
# ---------------------------------------------------------------------------


class TestDeleteAdjacents:
    def test_delete_success(self, client, admin_headers):
        """204 is returned when the item exists and disconnection succeeds."""
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.disconnect_adjacents", return_value=[]
            ),
        ):
            r = client.request(
                "DELETE", BASE, json={"items": [20]}, headers=admin_headers
            )
        assert r.status_code == 204

    def test_delete_item_not_found(self, client, admin_headers):
        """404 is returned when the beam line or line item does not exist."""
        with patch(
            "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
            return_value=False,
        ):
            r = client.request(
                "DELETE", BASE, json={"items": [20]}, headers=admin_headers
            )
        assert r.status_code == 404

    def test_delete_multiple_items(self, client, admin_headers):
        """204 is returned when disconnecting multiple adjacents at once."""
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.disconnect_adjacents", return_value=[]
            ),
        ):
            r = client.request(
                "DELETE", BASE, json={"items": [20, 21, 22]}, headers=admin_headers
            )
        assert r.status_code == 204

    def test_delete_duplicate_ids_deduped(self, client, admin_headers):
        """Duplicate IDs are silently deduplicated by the schema (ListIntNoDuplicates)."""
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.disconnect_adjacents", return_value=[]
            ),
        ):
            r = client.request(
                "DELETE", BASE, json={"items": [20, 20]}, headers=admin_headers
            )
        assert r.status_code == 204

    def test_delete_empty_items_rejected(self, client, admin_headers):
        """422 is returned when the items list is empty (schema min_length=1)."""
        with patch(
            "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
            return_value=True,
        ):
            r = client.request(
                "DELETE", BASE, json={"items": []}, headers=admin_headers
            )
        assert r.status_code == 422

    def test_delete_calls_disconnect_with_correct_args(self, client, admin_headers):
        """disconnect_adjacents receives the correct beam_id, item_id, and target list."""
        mock_disconnect = MagicMock(return_value=[])
        with (
            patch(
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.disconnect_adjacents", mock_disconnect
            ),
        ):
            client.request(
                "DELETE", BASE, json={"items": [20, 21]}, headers=admin_headers
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
                "app.routers.line_item_adjacents.beam_line_and_line_item_exist",
                return_value=True,
            ),
            patch(
                "app.routers.line_item_adjacents.disconnect_adjacents", mock_disconnect
            ),
        ):
            client.request("DELETE", BASE, json={"items": [20]}, headers=admin_headers)
        mock_disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# PATCH …/adjacents/{adj_id}
# ---------------------------------------------------------------------------


class TestPatchAdjacent:
    """PATCH calls run_query directly for existence and conflict checks."""

    def test_patch_success(self, client, admin_headers):
        """204 is returned when the adjacent exists and the new position is valid."""
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"current_id": 10, "adj_id": 20}],
                [],
            ],
        ):
            r = client.patch(
                f"{BASE}/20",
                json={"position": "Next"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_not_found(self, client, admin_headers):
        """404 is returned when the existence check returns no records."""
        with patch("app.routers.line_item_adjacents.run_query", return_value=[]):
            r = client.patch(
                f"{BASE}/999",
                json={"position": "Next"},
                headers=admin_headers,
            )
        assert r.status_code == 404

    def test_patch_index_conflict(self, client, admin_headers):
        """400 is returned when another adjacent already holds the requested index."""
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
        """204 is returned when an index is supplied and the conflict check passes."""
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
        """422 is returned when an invalid position string is supplied."""
        r = client.patch(
            f"{BASE}/20",
            json={"position": "BadPos"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_patch_dual_position(self, client, admin_headers):
        """204 is returned when the Dual position is used."""
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"current_id": 10, "adj_id": 20}],
                [],
            ],
        ):
            r = client.patch(
                f"{BASE}/20",
                json={"position": "Dual"},
                headers=admin_headers,
            )
        assert r.status_code == 204

    def test_patch_no_index_skips_conflict_check(self, client, admin_headers):
        """When no index is supplied the conflict check query is never called."""
        with patch(
            "app.routers.line_item_adjacents.run_query",
            side_effect=[
                [{"current_id": 10, "adj_id": 20}],  # existence check only
                [],  # update query
            ],
        ) as mock_rq:
            r = client.patch(
                f"{BASE}/20",
                json={"position": "Next"},
                headers=admin_headers,
            )
        assert r.status_code == 204
        assert mock_rq.call_count == 2  # existence + update, no conflict query
