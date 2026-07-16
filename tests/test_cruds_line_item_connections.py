"""Unit tests for app/cruds/line_item_connections.py.

All Neo4j DB calls (``run_query``) are patched so these tests run without
any live database.  Each test validates the query construction, parameter
forwarding, and return-value processing inside the CRUD layer.
"""

from unittest.mock import MagicMock, patch

from app.cruds.line_item_connections import (
    beam_line_and_line_item_exist,
    disconnect_line_item_connected_records,
    get_line_item_connections,
    get_total_line_item_connections,
    update_line_item_connected_records,
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
# beam_line_and_line_item_exist
# ---------------------------------------------------------------------------


class TestBeamLineAndLineItemExist:
    def test_returns_true_when_found(self):
        """Returns True when run_query returns a record."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[{"id": 10}]
        ):
            assert beam_line_and_line_item_exist(driver, beam_id=1, item_id=10) is True

    def test_returns_false_when_not_found(self):
        """Returns False when run_query returns an empty list."""
        driver = _make_driver()
        with patch("app.cruds.line_item_connections.run_query", return_value=[]):
            assert beam_line_and_line_item_exist(driver, beam_id=1, item_id=99) is False

    def test_passes_beam_and_item_ids(self):
        """Both beam_id and item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            beam_line_and_line_item_exist(driver, beam_id=3, item_id=7)
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 3
        assert params["id"] == 7

    def test_query_matches_beam_line_and_line_item(self):
        """The Cypher query matches both BeamLine and LineItem nodes."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            beam_line_and_line_item_exist(driver, beam_id=1, item_id=10)
        query = mock_rq.call_args[0][1]
        assert "BeamLine" in query
        assert "LineItem" in query

    def test_query_uses_has_line_item_relationship(self):
        """The Cypher query traverses the HAS_LINE_ITEM relationship."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            beam_line_and_line_item_exist(driver, beam_id=1, item_id=10)
        assert "HAS_LINE_ITEM" in mock_rq.call_args[0][1]

    def test_passes_driver_as_first_arg(self):
        """The driver is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            beam_line_and_line_item_exist(driver, beam_id=1, item_id=10)
        assert mock_rq.call_args[0][0] is driver


# ---------------------------------------------------------------------------
# get_total_line_item_connections
# ---------------------------------------------------------------------------


class TestGetTotalLineItemConnections:
    def test_returns_count_from_record(self):
        """Returns the total from the first record."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[{"total": 4}]
        ):
            assert (
                get_total_line_item_connections(driver, beam_id=1, line_item_id=10) == 4
            )

    def test_returns_zero_when_no_records(self):
        """Returns 0 when run_query comes back empty."""
        driver = _make_driver()
        with patch("app.cruds.line_item_connections.run_query", return_value=[]):
            assert (
                get_total_line_item_connections(driver, beam_id=1, line_item_id=10) == 0
            )

    def test_passes_beam_and_item_ids(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_connections(driver, beam_id=2, line_item_id=5)
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 2
        assert params["id"] == 5

    def test_query_counts_connected_items(self):
        """The Cypher query uses a COUNT aggregate targeting Item nodes."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_connections(driver, beam_id=1, line_item_id=10)
        query = mock_rq.call_args[0][1].lower()
        assert "count" in query

    def test_query_targets_connected_to_relationship(self):
        """The Cypher query uses the CONNECTED_TO relationship."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_connections(driver, beam_id=1, line_item_id=10)
        assert "CONNECTED_TO" in mock_rq.call_args[0][1]

    def test_query_scoped_to_beam_line(self):
        """The query is scoped through the BeamLine → HAS_LINE_ITEM path."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_connections(driver, beam_id=1, line_item_id=10)
        query = mock_rq.call_args[0][1]
        assert "BeamLine" in query
        assert "HAS_LINE_ITEM" in query


# ---------------------------------------------------------------------------
# get_line_item_connections
# ---------------------------------------------------------------------------


class TestGetLineItemConnections:
    def _call(self, driver, records, page=1, per_page=10):
        with patch("app.cruds.line_item_connections.run_query", return_value=records):
            return get_line_item_connections(
                driver, beam_id=1, line_item_id=10, page=page, per_page=per_page
            )

    def test_returns_list_of_dicts(self):
        """Each record is mapped to a dict with id, name, description, properties, link."""
        driver = _make_driver()
        conn_node = _make_node(id=30, name="RACK-01")
        conn_node.get = lambda k, d=None: "desc" if k == "description" else d
        record = {"conn": conn_node, "rel_props": {"kind": "line"}}
        result = self._call(driver, [record])
        assert result[0]["id"] == 30
        assert result[0]["name"] == "RACK-01"
        assert result[0]["description"] == "desc"
        assert result[0]["properties"] == {"kind": "line"}

    def test_empty_db_result_returns_empty_list(self):
        """An empty run_query result yields an empty list."""
        driver = _make_driver()
        assert self._call(driver, []) == []

    def test_link_url_contains_item_id(self):
        """The link URL is /api/v1/items/{conn_id}."""
        driver = _make_driver()
        conn_node = _make_node(id=30, name="X")
        conn_node.get = lambda k, d=None: d
        result = self._call(driver, [{"conn": conn_node, "rel_props": {}}])
        assert result[0]["link"] == "/api/v1/items/30"

    def test_null_rel_props_mapped_to_empty_dict(self):
        """A None value for rel_props is mapped to an empty dict in the output."""
        driver = _make_driver()
        conn_node = _make_node(id=5, name="X")
        conn_node.get = lambda k, d=None: d
        result = self._call(driver, [{"conn": conn_node, "rel_props": None}])
        assert result[0]["properties"] == {}

    def test_pagination_skip_calculated_correctly(self):
        """skip = (page-1) * per_page is included in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_connections(
                driver, beam_id=1, line_item_id=10, page=3, per_page=5
            )
        params = mock_rq.call_args[0][2]
        assert params["skip"] == 10  # (3-1) * 5
        assert params["limit"] == 5

    def test_beam_and_item_ids_forwarded(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_connections(
                driver, beam_id=4, line_item_id=7, page=1, per_page=10
            )
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 4
        assert params["id"] == 7

    def test_query_uses_connected_to(self):
        """The Cypher query uses the CONNECTED_TO relationship."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_connections(
                driver, beam_id=1, line_item_id=10, page=1, per_page=10
            )
        assert "CONNECTED_TO" in mock_rq.call_args[0][1]

    def test_query_scoped_through_beam_line(self):
        """The query is scoped through BeamLine → HAS_LINE_ITEM → LineItem."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_connections(
                driver, beam_id=1, line_item_id=10, page=1, per_page=10
            )
        query = mock_rq.call_args[0][1]
        assert "BeamLine" in query
        assert "HAS_LINE_ITEM" in query

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
        assert [r["name"] for r in result] == ["A", "B", "C"]

    def test_description_none_when_absent(self):
        """description is None when the node does not carry that property."""
        driver = _make_driver()
        conn_node = _make_node(id=1, name="X")
        conn_node.get = lambda k, d=None: d
        result = self._call(driver, [{"conn": conn_node, "rel_props": {}}])
        assert result[0]["description"] is None


# ---------------------------------------------------------------------------
# update_line_item_connected_records
# ---------------------------------------------------------------------------


class TestUpdateLineItemConnectedRecords:
    def test_returns_run_query_result(self):
        """The list returned by run_query is passed back unchanged."""
        driver = _make_driver()
        with patch("app.cruds.line_item_connections.run_query", return_value=[]):
            result = update_line_item_connected_records(
                driver, 1, 10, [{"id": 30, "properties": {}}]
            )
        assert result == []

    def test_calls_run_query_once(self):
        """run_query is called exactly once."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(
                driver, 1, 10, [{"id": 30, "properties": {}}]
            )
        mock_rq.assert_called_once()

    def test_passes_beam_and_item_ids(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(
                driver, 3, 7, [{"id": 30, "properties": {}}]
            )
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 3
        assert params["id"] == 7

    def test_passes_connections_list(self):
        """The connections list is forwarded under 'connections' in the parameters."""
        driver = _make_driver()
        connections = [{"id": 30, "properties": {"kind": "line"}}]
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(driver, 1, 10, connections)
        assert mock_rq.call_args[0][2]["connections"] == connections

    def test_query_uses_merge(self):
        """The Cypher query uses MERGE to create the relationship idempotently."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(
                driver, 1, 10, [{"id": 30, "properties": {}}]
            )
        assert "MERGE" in mock_rq.call_args[0][1]

    def test_query_uses_unwind(self):
        """The Cypher query uses UNWIND to iterate over connections."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(
                driver, 1, 10, [{"id": 30, "properties": {}}]
            )
        assert "UNWIND" in mock_rq.call_args[0][1].upper()

    def test_query_scoped_through_beam_line(self):
        """The query is scoped through BeamLine → HAS_LINE_ITEM → LineItem."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(
                driver, 1, 10, [{"id": 30, "properties": {}}]
            )
        query = mock_rq.call_args[0][1]
        assert "BeamLine" in query
        assert "HAS_LINE_ITEM" in query

    def test_query_targets_connected_to(self):
        """The Cypher query creates/updates the CONNECTED_TO relationship."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(
                driver, 1, 10, [{"id": 30, "properties": {}}]
            )
        assert "CONNECTED_TO" in mock_rq.call_args[0][1]

    def test_passes_driver_to_run_query(self):
        """The driver is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(driver, 1, 10, [])
        assert mock_rq.call_args[0][0] is driver

    def test_multiple_connections_forwarded(self):
        """Multiple connections in the list are all forwarded."""
        driver = _make_driver()
        connections = [
            {"id": 10, "properties": {}},
            {"id": 11, "properties": {"role": "primary"}},
        ]
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            update_line_item_connected_records(driver, 1, 5, connections)
        assert mock_rq.call_args[0][2]["connections"] == connections


# ---------------------------------------------------------------------------
# disconnect_line_item_connected_records
# ---------------------------------------------------------------------------


class TestDisconnectLineItemConnectedRecords:
    def test_calls_run_query_once(self):
        """run_query is called exactly once."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            disconnect_line_item_connected_records(driver, 1, 10, [30])
        mock_rq.assert_called_once()

    def test_passes_beam_and_item_ids(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            disconnect_line_item_connected_records(driver, 2, 5, [30])
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 2
        assert params["id"] == 5

    def test_passes_target_ids(self):
        """The items list is forwarded under 'target_ids' in the parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            disconnect_line_item_connected_records(driver, 1, 10, [30, 31])
        assert mock_rq.call_args[0][2]["target_ids"] == [30, 31]

    def test_query_uses_delete(self):
        """The Cypher query uses DELETE to remove the relationship."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            disconnect_line_item_connected_records(driver, 1, 10, [30])
        assert "DELETE" in mock_rq.call_args[0][1].upper()

    def test_query_filters_by_target_ids(self):
        """The query filters by the target_ids parameter."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            disconnect_line_item_connected_records(driver, 1, 10, [30])
        assert "target_ids" in mock_rq.call_args[0][1]

    def test_query_scoped_through_beam_line(self):
        """The query is scoped through BeamLine → HAS_LINE_ITEM → LineItem."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            disconnect_line_item_connected_records(driver, 1, 10, [30])
        query = mock_rq.call_args[0][1]
        assert "BeamLine" in query
        assert "HAS_LINE_ITEM" in query

    def test_returns_run_query_result(self):
        """The return value of run_query is passed back unchanged."""
        driver = _make_driver()
        with patch("app.cruds.line_item_connections.run_query", return_value=[]):
            assert disconnect_line_item_connected_records(driver, 1, 10, [30]) == []

    def test_passes_driver_to_run_query(self):
        """The driver is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_connections.run_query", return_value=[]
        ) as mock_rq:
            disconnect_line_item_connected_records(driver, 1, 10, [30])
        assert mock_rq.call_args[0][0] is driver
