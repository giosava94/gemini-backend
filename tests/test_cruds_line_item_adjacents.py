"""Unit tests for app/cruds/line_item_adjacents.py.

All Neo4j DB calls (``run_query``) are patched so these tests run without
any live database.  The two pure-function helpers are tested without any
mocking at all.
"""

from unittest.mock import MagicMock, patch

from app.cruds.line_item_adjacents import (
    disconnect_adjacents,
    get_line_item_adjacent_relationships,
    get_total_line_item_adjacent_relationships,
    has_duplicate_adjacent_index_in_items,
    has_duplicate_adjacent_items,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver() -> MagicMock:
    return MagicMock()


def _make_node(**fields) -> MagicMock:
    node = MagicMock()
    node.__getitem__ = lambda _, k: fields[k]
    node.get = lambda k, default=None: fields.get(k, default)
    return node


# ---------------------------------------------------------------------------
# has_duplicate_adjacent_items  (pure function)
# ---------------------------------------------------------------------------


class TestHasDuplicateAdjacentItems:
    def test_empty_list_returns_false(self):
        """An empty list has no duplicates."""
        assert has_duplicate_adjacent_items([]) is False

    def test_single_item_returns_false(self):
        """A single entry cannot create a duplicate."""
        assert (
            has_duplicate_adjacent_items([{"id": 1, "position": "Previous"}]) is False
        )

    def test_same_id_same_position_is_duplicate(self):
        """Two entries with the same (id, position) pair is a duplicate."""
        items = [
            {"id": 1, "position": "Previous"},
            {"id": 1, "position": "Previous"},
        ]
        assert has_duplicate_adjacent_items(items) is True

    def test_same_id_different_position_no_duplicate(self):
        """Same ID but different positions are not considered duplicates."""
        items = [
            {"id": 1, "position": "Previous"},
            {"id": 1, "position": "Next"},
        ]
        assert has_duplicate_adjacent_items(items) is False

    def test_different_id_same_position_no_duplicate(self):
        """Different IDs with the same position are not duplicates."""
        items = [
            {"id": 1, "position": "Previous"},
            {"id": 2, "position": "Previous"},
        ]
        assert has_duplicate_adjacent_items(items) is False

    def test_duplicate_among_many(self):
        """Duplicate detected when buried among many distinct entries."""
        items = [
            {"id": 1, "position": "Previous"},
            {"id": 2, "position": "Next"},
            {"id": 3, "position": "Dual"},
            {"id": 2, "position": "Next"},  # duplicate
        ]
        assert has_duplicate_adjacent_items(items) is True

    def test_all_distinct_no_duplicate(self):
        """All distinct (id, position) pairs → no duplicate."""
        items = [
            {"id": 1, "position": "Previous"},
            {"id": 2, "position": "Previous"},
            {"id": 1, "position": "Next"},
        ]
        assert has_duplicate_adjacent_items(items) is False


# ---------------------------------------------------------------------------
# has_duplicate_adjacent_index_in_items  (pure function)
# ---------------------------------------------------------------------------


class TestHasDuplicateAdjacentIndexInItems:
    def test_empty_list_returns_false(self):
        assert has_duplicate_adjacent_index_in_items([]) is False

    def test_single_item_returns_false(self):
        assert (
            has_duplicate_adjacent_index_in_items(
                [{"position": "Previous", "index": 0}]
            )
            is False
        )

    def test_same_position_same_index_is_duplicate(self):
        items = [
            {"position": "Previous", "index": 0},
            {"position": "Previous", "index": 0},
        ]
        assert has_duplicate_adjacent_index_in_items(items) is True

    def test_different_positions_same_index_no_duplicate(self):
        items = [
            {"position": "Previous", "index": 0},
            {"position": "Next", "index": 0},
        ]
        assert has_duplicate_adjacent_index_in_items(items) is False

    def test_same_position_different_index_no_duplicate(self):
        items = [
            {"position": "Previous", "index": 0},
            {"position": "Previous", "index": 1},
        ]
        assert has_duplicate_adjacent_index_in_items(items) is False

    def test_none_index_is_skipped(self):
        """Entries where index is None are not checked for duplicates."""
        items = [
            {"position": "Previous", "index": None},
            {"position": "Previous", "index": None},
        ]
        assert has_duplicate_adjacent_index_in_items(items) is False

    def test_mixed_none_and_set_no_duplicate(self):
        items = [
            {"position": "Previous", "index": None},
            {"position": "Previous", "index": 0},
        ]
        assert has_duplicate_adjacent_index_in_items(items) is False

    def test_duplicate_among_many(self):
        items = [
            {"position": "Previous", "index": 0},
            {"position": "Next", "index": 1},
            {"position": "Previous", "index": 2},
            {"position": "Next", "index": 1},  # duplicate
        ]
        assert has_duplicate_adjacent_index_in_items(items) is True


# ---------------------------------------------------------------------------
# get_total_line_item_adjacent_relationships
# ---------------------------------------------------------------------------


class TestGetTotalLineItemAdjacentRelationships:
    def test_returns_count_from_record(self):
        """Returns the total from the first record."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[{"total": 3}]
        ):
            assert get_total_line_item_adjacent_relationships(driver, 1, 10, None) == 3

    def test_returns_zero_when_no_records(self):
        """Returns 0 when run_query comes back empty."""
        driver = _make_driver()
        with patch("app.cruds.line_item_adjacents.run_query", return_value=[]):
            assert get_total_line_item_adjacent_relationships(driver, 1, 10, None) == 0

    def test_passes_beam_and_item_ids(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_adjacent_relationships(driver, 2, 5, None)
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 2
        assert params["id"] == 5

    def test_passes_position_filter(self):
        """The position value is forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_adjacent_relationships(driver, 1, 10, "Previous")
        assert mock_rq.call_args[0][2]["position"] == "Previous"

    def test_passes_none_position(self):
        """None is forwarded as the position value when no filter is set."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_adjacent_relationships(driver, 1, 10, None)
        assert mock_rq.call_args[0][2]["position"] is None

    def test_query_uses_count_aggregate(self):
        """The Cypher query uses a COUNT aggregate."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_adjacent_relationships(driver, 1, 10, None)
        assert "count" in mock_rq.call_args[0][1].lower()

    def test_query_matches_previous_or_next(self):
        """The Cypher query matches PREVIOUS|NEXT relationships."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_adjacent_relationships(driver, 1, 10, None)
        query = mock_rq.call_args[0][1]
        assert "PREVIOUS" in query
        assert "NEXT" in query

    def test_query_scoped_through_beam_line(self):
        """The query is scoped through BeamLine → HAS_LINE_ITEM."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_adjacent_relationships(driver, 1, 10, None)
        query = mock_rq.call_args[0][1]
        assert "BeamLine" in query
        assert "HAS_LINE_ITEM" in query


# ---------------------------------------------------------------------------
# get_line_item_adjacent_relationships
# ---------------------------------------------------------------------------


class TestGetLineItemAdjacentRelationships:
    def _call(self, driver, records, sort=None, page=1, per_page=10, pos=None):
        with patch("app.cruds.line_item_adjacents.run_query", return_value=records):
            return get_line_item_adjacent_relationships(
                driver, 1, 10, pos, sort=sort, page=page, per_page=per_page
            )

    def test_returns_list_of_dicts(self):
        """Each record is mapped to a dict with id, name, description, position, index, link."""
        driver = _make_driver()
        adj_node = _make_node(id=20, name="QD02")
        adj_node.get = lambda k, d=None: "desc" if k == "description" else d
        record = {"adj": adj_node, "position": "Previous", "index": 0}
        result = self._call(driver, [record])
        assert result[0]["id"] == 20
        assert result[0]["name"] == "QD02"
        assert result[0]["description"] == "desc"
        assert result[0]["position"] == "Previous"
        assert result[0]["index"] == 0

    def test_empty_db_result_returns_empty_list(self):
        """An empty run_query result yields an empty list."""
        driver = _make_driver()
        assert self._call(driver, []) == []

    def test_link_url_format(self):
        """The link URL is /api/v1/beam-lines/{beam_id}/line-items/{adj_id}."""
        driver = _make_driver()
        adj_node = _make_node(id=20, name="X")
        adj_node.get = lambda k, d=None: d
        result = self._call(
            driver, [{"adj": adj_node, "position": "Previous", "index": None}]
        )
        assert result[0]["link"] == "/api/v1/beam-lines/1/line-items/20"

    def test_description_none_when_absent(self):
        """description is None when the node property is absent."""
        driver = _make_driver()
        adj_node = _make_node(id=20, name="X")
        adj_node.get = lambda k, d=None: d
        result = self._call(
            driver, [{"adj": adj_node, "position": "Next", "index": None}]
        )
        assert result[0]["description"] is None

    def test_index_none_when_absent(self):
        """index is None when the record carries no index value."""
        driver = _make_driver()
        adj_node = _make_node(id=20, name="X")
        adj_node.get = lambda k, d=None: d
        result = self._call(
            driver, [{"adj": adj_node, "position": "Next", "index": None}]
        )
        assert result[0]["index"] is None

    def test_pagination_skip_calculated_correctly(self):
        """skip = (page-1) * per_page is included in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_adjacent_relationships(
                driver, 1, 10, None, sort=None, page=3, per_page=5
            )
        params = mock_rq.call_args[0][2]
        assert params["skip"] == 10  # (3-1) * 5
        assert params["limit"] == 5

    def test_beam_and_item_ids_forwarded(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_adjacent_relationships(
                driver, 4, 7, None, sort=None, page=1, per_page=10
            )
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 4
        assert params["id"] == 7

    def test_position_filter_forwarded(self):
        """The position filter is forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_adjacent_relationships(
                driver, 1, 10, "Previous", sort=None, page=1, per_page=10
            )
        assert mock_rq.call_args[0][2]["position"] == "Previous"

    def test_sort_by_position_adds_order_clause(self):
        """sort=['position'] results in an ORDER BY clause in the query."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_adjacent_relationships(
                driver, 1, 10, None, sort=["position"], page=1, per_page=10
            )
        assert "ORDER BY" in mock_rq.call_args[0][1]

    def test_no_sort_omits_order_clause(self):
        """sort=None means no ORDER BY clause in the query."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_adjacent_relationships(
                driver, 1, 10, None, sort=None, page=1, per_page=10
            )
        assert "ORDER BY" not in mock_rq.call_args[0][1]

    def test_multiple_records_all_mapped(self):
        """All records returned by run_query appear in the output list."""
        driver = _make_driver()
        nodes = []
        for i, (name, pos) in enumerate(
            [("A", "Previous"), ("B", "Next"), ("C", "Dual")], start=1
        ):
            n = _make_node(id=i, name=name)
            n.get = lambda k, d=None: d
            nodes.append({"adj": n, "position": pos, "index": None})
        result = self._call(driver, nodes)
        assert len(result) == 3
        assert [r["name"] for r in result] == ["A", "B", "C"]

    def test_query_scoped_through_beam_line(self):
        """The query is scoped through BeamLine → HAS_LINE_ITEM."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            get_line_item_adjacent_relationships(
                driver, 1, 10, None, sort=None, page=1, per_page=10
            )
        query = mock_rq.call_args[0][1]
        assert "BeamLine" in query
        assert "HAS_LINE_ITEM" in query


# ---------------------------------------------------------------------------
# disconnect_adjacents
# ---------------------------------------------------------------------------


class TestDisconnectAdjacents:
    def test_calls_run_query_once(self):
        """run_query is called exactly once."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20])
        mock_rq.assert_called_once()

    def test_passes_beam_and_item_ids(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 3, 7, [20])
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 3
        assert params["id"] == 7

    def test_passes_target_ids(self):
        """The target items list is forwarded under 'target_ids' in the parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20, 21])
        assert mock_rq.call_args[0][2]["target_ids"] == [20, 21]

    def test_query_uses_delete(self):
        """The Cypher query uses DELETE to remove the relationships."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20])
        assert "DELETE" in mock_rq.call_args[0][1].upper()

    def test_query_uses_optional_match(self):
        """The query uses OPTIONAL MATCH for both directions of the relationship."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20])
        assert "OPTIONAL MATCH" in mock_rq.call_args[0][1]

    def test_query_uses_unwind(self):
        """The Cypher query uses UNWIND to iterate over the target IDs."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20])
        assert "UNWIND" in mock_rq.call_args[0][1].upper()

    def test_query_removes_both_directions(self):
        """The query removes PREVIOUS and NEXT relationships in both directions."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20])
        query = mock_rq.call_args[0][1]
        assert "PREVIOUS" in query
        assert "NEXT" in query

    def test_query_scoped_through_beam_line(self):
        """The query is scoped through BeamLine → HAS_LINE_ITEM."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20])
        query = mock_rq.call_args[0][1]
        assert "BeamLine" in query
        assert "HAS_LINE_ITEM" in query

    def test_returns_run_query_result(self):
        """The return value of run_query is passed back unchanged."""
        driver = _make_driver()
        with patch("app.cruds.line_item_adjacents.run_query", return_value=[]):
            assert disconnect_adjacents(driver, 1, 10, [20]) == []

    def test_passes_driver_to_run_query(self):
        """The driver is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20])
        assert mock_rq.call_args[0][0] is driver

    def test_multiple_target_ids_forwarded(self):
        """Multiple target IDs are all forwarded in the target_ids parameter."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_adjacents.run_query", return_value=[]
        ) as mock_rq:
            disconnect_adjacents(driver, 1, 10, [20, 21, 22])
        assert mock_rq.call_args[0][2]["target_ids"] == [20, 21, 22]
