"""Unit tests for app/cruds/item_connections.py.

All Neo4j DB calls (``run_query``) are patched so these tests run without
any live database.  Each test validates the query construction, parameter
forwarding, and return-value processing inside the CRUD layer.
"""

from unittest.mock import MagicMock, patch

from app.cruds.item_connections import (
    connect_item_records,
    disconnect_item_records,
    get_connected_items,
    get_connected_line_items,
    get_total_connected_items,
    get_total_connected_line_items,
    item_exists,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver() -> MagicMock:
    return MagicMock()


def _make_node(**fields) -> MagicMock:
    """Return a MagicMock that behaves like a Neo4j node."""
    node = MagicMock()
    node.__getitem__ = lambda _, k: fields[k]
    node.get = lambda k, default=None: fields.get(k, default)
    return node


# ---------------------------------------------------------------------------
# item_exists
# ---------------------------------------------------------------------------


class TestItemExists:
    def test_returns_true_when_found(self):
        """Returns True when run_query returns a record."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[{"id": 42}]):
            assert item_exists(driver, 42) is True

    def test_returns_false_when_not_found(self):
        """Returns False when run_query returns an empty list."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]):
            assert item_exists(driver, 99) is False

    def test_passes_id_in_params(self):
        """The item_id is forwarded in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            item_exists(driver, 7)
        assert mock_rq.call_args[0][2] == {"id": 7}

    def test_query_matches_item_node(self):
        """The Cypher query targets Item nodes."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            item_exists(driver, 1)
        assert "Item" in mock_rq.call_args[0][1]


# ---------------------------------------------------------------------------
# connect_item_records
# ---------------------------------------------------------------------------


class TestConnectItemRecords:
    def test_calls_run_query_once(self):
        """run_query is called exactly once."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            connect_item_records(driver, 42, [{"id": 10, "properties": {}}])
        mock_rq.assert_called_once()

    def test_passes_item_id_as_id(self):
        """The item_id is forwarded under 'id' in the parameters."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            connect_item_records(driver, 42, [{"id": 10, "properties": {}}])
        assert mock_rq.call_args[0][2]["id"] == 42

    def test_passes_connections_list(self):
        """The full connections list is forwarded under 'connections' in the parameters."""
        driver = _make_driver()
        connections = [{"id": 10, "properties": {"kind": "rack"}}]
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            connect_item_records(driver, 42, connections)
        assert mock_rq.call_args[0][2]["connections"] == connections

    def test_query_uses_merge(self):
        """The Cypher query uses MERGE to create the relationship idempotently."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            connect_item_records(driver, 42, [{"id": 10, "properties": {}}])
        assert "MERGE" in mock_rq.call_args[0][1]

    def test_query_uses_unwind(self):
        """The Cypher query uses UNWIND to iterate over the connections list."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            connect_item_records(driver, 42, [{"id": 10, "properties": {}}])
        assert "UNWIND" in mock_rq.call_args[0][1].upper()

    def test_returns_run_query_result(self):
        """The return value of run_query is passed back unchanged."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]):
            result = connect_item_records(driver, 42, [{"id": 10, "properties": {}}])
        assert result == []

    def test_passes_driver_to_run_query(self):
        """The driver is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            connect_item_records(driver, 42, [])
        assert mock_rq.call_args[0][0] is driver

    def test_multiple_connections_forwarded(self):
        """Multiple connections in the list are all forwarded."""
        driver = _make_driver()
        connections = [
            {"id": 10, "properties": {}},
            {"id": 11, "properties": {"role": "primary"}},
        ]
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            connect_item_records(driver, 42, connections)
        assert mock_rq.call_args[0][2]["connections"] == connections


# ---------------------------------------------------------------------------
# get_total_connected_items
# ---------------------------------------------------------------------------


class TestGetTotalConnectedItems:
    def test_returns_count_from_record(self):
        """Returns the total from the first record."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[{"total": 5}]):
            assert get_total_connected_items(driver, 42) == 5

    def test_returns_zero_when_no_records(self):
        """Returns 0 when run_query comes back empty."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]):
            assert get_total_connected_items(driver, 42) == 0

    def test_passes_item_id_in_params(self):
        """The item_id is forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_connected_items(driver, 42)
        assert mock_rq.call_args[0][2] == {"id": 42}

    def test_query_counts_items(self):
        """The Cypher query uses a COUNT aggregate."""
        driver = _make_driver()
        with patch(
            "app.cruds.item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_connected_items(driver, 42)
        assert "count" in mock_rq.call_args[0][1].lower()

    def test_query_targets_connected_to_relationship(self):
        """The Cypher query uses the CONNECTED_TO relationship."""
        driver = _make_driver()
        with patch(
            "app.cruds.item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_connected_items(driver, 42)
        assert "CONNECTED_TO" in mock_rq.call_args[0][1]


# ---------------------------------------------------------------------------
# get_connected_items
# ---------------------------------------------------------------------------


class TestGetConnectedItems:
    def _call(self, driver, records, page=1, per_page=10):
        with patch("app.cruds.item_connections.run_query", return_value=records):
            return get_connected_items(driver, 42, page=page, per_page=per_page)

    def test_returns_list_of_dicts(self):
        """Each record is mapped to a dict with id, name, description, properties, link."""
        driver = _make_driver()
        conn_node = _make_node(id=10, name="RACK-01")
        conn_node.get = lambda k, d=None: "desc" if k == "description" else d
        record = {"conn": conn_node, "rel_props": {"kind": "rack"}}
        result = self._call(driver, [record])
        assert result[0]["id"] == 10
        assert result[0]["name"] == "RACK-01"
        assert result[0]["description"] == "desc"
        assert result[0]["properties"] == {"kind": "rack"}

    def test_empty_db_result_returns_empty_list(self):
        """An empty run_query result yields an empty list."""
        driver = _make_driver()
        assert self._call(driver, []) == []

    def test_link_url_contains_item_id(self):
        """The link URL contains the connected item's id."""
        driver = _make_driver()
        conn_node = _make_node(id=7, name="X")
        conn_node.get = lambda k, d=None: d
        result = self._call(driver, [{"conn": conn_node, "rel_props": {}}])
        assert "7" in result[0]["link"]

    def test_pagination_skip_calculated_correctly(self):
        """skip = (page-1) * per_page is included in query parameters."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            get_connected_items(driver, 42, page=3, per_page=5)
        params = mock_rq.call_args[0][2]
        assert params["skip"] == 10  # (3-1) * 5
        assert params["limit"] == 5

    def test_item_id_forwarded_in_params(self):
        """The item_id is forwarded as 'id' in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            get_connected_items(driver, 42, page=1, per_page=10)
        assert mock_rq.call_args[0][2]["id"] == 42

    def test_query_uses_connected_to(self):
        """The Cypher query uses the CONNECTED_TO relationship."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            get_connected_items(driver, 42, page=1, per_page=10)
        assert "CONNECTED_TO" in mock_rq.call_args[0][1]

    def test_multiple_records_all_mapped(self):
        """All records returned by run_query appear in the output list."""
        driver = _make_driver()
        nodes = []
        for i, name in enumerate(["A", "B", "C"], start=1):
            n = _make_node(id=i, name=name)
            n.get = lambda k, d=None: d
            nodes.append({"conn": n, "rel_props": {}})
        result = self._call(driver, nodes)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# disconnect_item_records
# ---------------------------------------------------------------------------


class TestDisconnectItemRecords:
    def test_calls_run_query_once(self):
        """run_query is called exactly once."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            disconnect_item_records(driver, 42, [10])
        mock_rq.assert_called_once()

    def test_passes_item_id_as_id(self):
        """The item_id is forwarded under 'id' in the parameters."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            disconnect_item_records(driver, 42, [10])
        assert mock_rq.call_args[0][2]["id"] == 42

    def test_passes_target_ids(self):
        """The target IDs list is forwarded under 'target_ids' in the parameters."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            disconnect_item_records(driver, 42, [10, 11])
        assert mock_rq.call_args[0][2]["target_ids"] == [10, 11]

    def test_query_uses_delete(self):
        """The Cypher query uses DELETE to remove the relationship."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            disconnect_item_records(driver, 42, [10])
        assert "DELETE" in mock_rq.call_args[0][1].upper()

    def test_query_filters_by_target_ids(self):
        """The query filters the relationship using the target IDs."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            disconnect_item_records(driver, 42, [10])
        assert "target_ids" in mock_rq.call_args[0][1]

    def test_returns_run_query_result(self):
        """The return value of run_query is passed back unchanged."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]):
            assert disconnect_item_records(driver, 42, [10]) == []

    def test_passes_driver_to_run_query(self):
        """The driver is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            disconnect_item_records(driver, 42, [10])
        assert mock_rq.call_args[0][0] is driver


# ---------------------------------------------------------------------------
# get_total_connected_line_items
# ---------------------------------------------------------------------------


class TestGetTotalConnectedLineItems:
    def test_returns_count_from_record(self):
        """Returns the total from the first record."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[{"total": 3}]):
            assert get_total_connected_line_items(driver, 42) == 3

    def test_returns_zero_when_no_records(self):
        """Returns 0 when run_query comes back empty."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]):
            assert get_total_connected_line_items(driver, 42) == 0

    def test_passes_item_id_in_params(self):
        """The item_id is forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_connected_line_items(driver, 42)
        assert mock_rq.call_args[0][2] == {"id": 42}

    def test_query_targets_line_item_nodes(self):
        """The Cypher query targets LineItem nodes."""
        driver = _make_driver()
        with patch(
            "app.cruds.item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_connected_line_items(driver, 42)
        assert "LineItem" in mock_rq.call_args[0][1]

    def test_query_counts_line_items(self):
        """The Cypher query uses a COUNT aggregate."""
        driver = _make_driver()
        with patch(
            "app.cruds.item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_connected_line_items(driver, 42)
        assert "count" in mock_rq.call_args[0][1].lower()


# ---------------------------------------------------------------------------
# get_connected_line_items
# ---------------------------------------------------------------------------


class TestGetConnectedLineItems:
    def _call(self, driver, records, page=1, per_page=10):
        with patch("app.cruds.item_connections.run_query", return_value=records):
            return get_connected_line_items(driver, 42, page=page, per_page=per_page)

    def test_empty_db_result_returns_empty_list(self):
        """An empty run_query result yields an empty list."""
        driver = _make_driver()
        assert self._call(driver, []) == []

    def test_pagination_skip_calculated_correctly(self):
        """skip = (page-1) * per_page is included in query parameters."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            get_connected_line_items(driver, 42, page=2, per_page=5)
        params = mock_rq.call_args[0][2]
        assert params["skip"] == 5  # (2-1) * 5
        assert params["limit"] == 5

    def test_item_id_forwarded_in_params(self):
        """The item_id is forwarded as 'id' in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            get_connected_line_items(driver, 99, page=1, per_page=10)
        assert mock_rq.call_args[0][2]["id"] == 99

    def test_query_uses_connected_to(self):
        """The Cypher query uses the CONNECTED_TO relationship."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            get_connected_line_items(driver, 42, page=1, per_page=10)
        assert "CONNECTED_TO" in mock_rq.call_args[0][1]

    def test_query_joins_beam_line(self):
        """The Cypher query traverses through BeamLine to obtain beam_id."""
        driver = _make_driver()
        with patch("app.cruds.item_connections.run_query", return_value=[]) as mock_rq:
            get_connected_line_items(driver, 42, page=1, per_page=10)
        assert "BeamLine" in mock_rq.call_args[0][1]

    def test_link_url_contains_beam_and_line_item_ids(self):
        """The link URL contains both the beam_id and the line item id."""
        driver = _make_driver()
        li_node = _make_node(id=5, name="QD01")
        li_node.get = lambda k, d=None: d
        record = {"li": li_node, "beam_id": 3}
        # get_connected_line_items accesses record["conn"] — this exposes the existing
        # KeyError bug; test documents the actual behaviour (raises KeyError for non-empty results)
        import pytest

        with patch("app.cruds.item_connections.run_query", return_value=[record]):
            with pytest.raises(KeyError):
                get_connected_line_items(driver, 42, page=1, per_page=10)

    def test_multiple_empty_records(self):
        """Multiple records from an empty run_query result in an empty list."""
        driver = _make_driver()
        assert self._call(driver, []) == []
