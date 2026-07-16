"""Unit tests for app/cruds/line_item_kinds.py.

All Neo4j DB calls (``run_query``) are patched so these tests run without
any live database.  Each test validates query construction, parameter
forwarding, and return-value processing.
"""

from unittest.mock import MagicMock, patch

from app.cruds.line_item_kinds import (
    create_line_item_kind,
    delete_line_item_kind,
    get_all_line_item_kinds,
    line_item_kind_exists,
    line_item_kind_in_use,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# create_line_item_kind
# ---------------------------------------------------------------------------


class TestCreateLineItemKind:
    def test_returns_run_query_result(self):
        """The list returned by run_query is passed back unchanged."""
        driver = _make_driver()
        expected = [{"name": "Wien Filter"}]
        with patch("app.cruds.line_item_kinds.run_query", return_value=expected):
            result = create_line_item_kind(driver, "Wien Filter")
        assert result == expected

    def test_returns_empty_on_db_failure(self):
        """An empty list from run_query is returned as-is."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]):
            assert create_line_item_kind(driver, "Diagnostic") == []

    def test_passes_driver_as_first_arg(self):
        """run_query receives the driver as its first positional argument."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            create_line_item_kind(driver, "X")
        assert mock_rq.call_args[0][0] is driver

    def test_passes_name_in_params(self):
        """The kind name is forwarded under 'name' in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            create_line_item_kind(driver, "ES Dipole")
        assert mock_rq.call_args[0][2] == {"name": "ES Dipole"}

    def test_query_contains_merge_and_create(self):
        """The Cypher query uses MERGE (counter) and CREATE (node) keywords."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            create_line_item_kind(driver, "X")
        query = mock_rq.call_args[0][1]
        assert "MERGE" in query
        assert "CREATE" in query

    def test_query_targets_line_item_kind_node(self):
        """The Cypher query creates a ``LineItemKind`` node."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            create_line_item_kind(driver, "X")
        assert "LineItemKind" in mock_rq.call_args[0][1]

    def test_query_returns_name(self):
        """The query returns ``k.name AS name``."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            create_line_item_kind(driver, "X")
        assert "name" in mock_rq.call_args[0][1].lower()


# ---------------------------------------------------------------------------
# get_all_line_item_kinds
# ---------------------------------------------------------------------------


class TestGetAllLineItemKinds:
    def test_returns_list_of_dicts(self):
        """Each record is mapped to a dict with a 'name' key."""
        driver = _make_driver()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda _, k: "Diagnostic" if k == "name" else None
        with patch("app.cruds.line_item_kinds.run_query", return_value=[mock_record]):
            result = get_all_line_item_kinds(driver)
        assert result == [{"name": "Diagnostic"}]

    def test_returns_empty_list_when_no_kinds(self):
        """Returns an empty list when run_query yields no records."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]):
            assert get_all_line_item_kinds(driver) == []

    def test_query_targets_line_item_kind_nodes(self):
        """The Cypher query matches ``LineItemKind`` nodes."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            get_all_line_item_kinds(driver)
        assert "LineItemKind" in mock_rq.call_args[0][1]

    def test_query_includes_order_by(self):
        """The Cypher query sorts results alphabetically."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            get_all_line_item_kinds(driver)
        assert "ORDER BY" in mock_rq.call_args[0][1]

    def test_no_params_passed_to_run_query(self):
        """``get_all_line_item_kinds`` does not pass any query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            get_all_line_item_kinds(driver)
        # run_query called with only driver + query, no parameters dict
        assert len(mock_rq.call_args[0]) == 2

    def test_multiple_records_all_mapped(self):
        """All records returned by run_query appear in the output list."""
        driver = _make_driver()
        names = ["Diagnostic", "Wien Filter", "Ion Source"]
        records = []
        for name in names:
            rec = MagicMock()
            rec.__getitem__ = lambda _, k, n=name: n if k == "name" else None
            records.append(rec)
        with patch("app.cruds.line_item_kinds.run_query", return_value=records):
            result = get_all_line_item_kinds(driver)
        assert [r["name"] for r in result] == names


# ---------------------------------------------------------------------------
# delete_line_item_kind
# ---------------------------------------------------------------------------


class TestDeleteLineItemKind:
    def test_calls_run_query_once(self):
        """run_query is called exactly once."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            delete_line_item_kind(driver, "Diagnostic")
        mock_rq.assert_called_once()

    def test_passes_name_in_params(self):
        """The kind name is forwarded under 'name' in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            delete_line_item_kind(driver, "Wien Filter")
        assert mock_rq.call_args[0][2] == {"name": "Wien Filter"}

    def test_query_uses_delete(self):
        """The Cypher query uses DELETE to remove the node."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            delete_line_item_kind(driver, "X")
        assert "DELETE" in mock_rq.call_args[0][1].upper()

    def test_returns_run_query_result(self):
        """The return value of run_query is passed back unchanged."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]):
            assert delete_line_item_kind(driver, "X") == []

    def test_passes_driver_to_run_query(self):
        """The driver is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            delete_line_item_kind(driver, "X")
        assert mock_rq.call_args[0][0] is driver

    def test_query_targets_line_item_kind(self):
        """The Cypher query matches ``LineItemKind`` nodes."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]) as mock_rq:
            delete_line_item_kind(driver, "X")
        assert "LineItemKind" in mock_rq.call_args[0][1]


# ---------------------------------------------------------------------------
# line_item_kind_exists
# ---------------------------------------------------------------------------


class TestLineItemKindExists:
    def test_returns_true_when_found(self):
        """Returns True when run_query reports the kind exists."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"exists": True}],
        ):
            assert line_item_kind_exists(driver, "Diagnostic") is True

    def test_returns_false_when_not_found(self):
        """Returns False when run_query reports the kind does not exist."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"exists": False}],
        ):
            assert line_item_kind_exists(driver, "Unknown") is False

    def test_returns_false_on_empty_result(self):
        """Returns False when run_query returns an empty list."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]):
            assert line_item_kind_exists(driver, "X") is False

    def test_passes_name_in_params(self):
        """The kind name is forwarded under 'name' in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"exists": False}],
        ) as mock_rq:
            line_item_kind_exists(driver, "ES Triplet")
        assert mock_rq.call_args[0][2] == {"name": "ES Triplet"}

    def test_query_targets_line_item_kind(self):
        """The Cypher query matches ``LineItemKind`` nodes."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"exists": False}],
        ) as mock_rq:
            line_item_kind_exists(driver, "X")
        assert "LineItemKind" in mock_rq.call_args[0][1]

    def test_query_uses_count(self):
        """The Cypher query uses count to check existence."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"exists": False}],
        ) as mock_rq:
            line_item_kind_exists(driver, "X")
        assert "count" in mock_rq.call_args[0][1].lower()


# ---------------------------------------------------------------------------
# line_item_kind_in_use
# ---------------------------------------------------------------------------


class TestLineItemKindInUse:
    def test_returns_true_when_in_use(self):
        """Returns True when at least one LineItem references the kind."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"in_use": True}],
        ):
            assert line_item_kind_in_use(driver, "Diagnostic") is True

    def test_returns_false_when_not_in_use(self):
        """Returns False when no LineItem references the kind."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"in_use": False}],
        ):
            assert line_item_kind_in_use(driver, "Diagnostic") is False

    def test_returns_false_on_empty_result(self):
        """Returns False when run_query returns an empty list."""
        driver = _make_driver()
        with patch("app.cruds.line_item_kinds.run_query", return_value=[]):
            assert line_item_kind_in_use(driver, "X") is False

    def test_passes_name_in_params(self):
        """The kind name is forwarded under 'name' in the query parameters."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"in_use": False}],
        ) as mock_rq:
            line_item_kind_in_use(driver, "MG Dipole")
        assert mock_rq.call_args[0][2] == {"name": "MG Dipole"}

    def test_query_targets_line_item_nodes(self):
        """The Cypher query matches ``LineItem`` nodes (not ``LineItemKind``)."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"in_use": False}],
        ) as mock_rq:
            line_item_kind_in_use(driver, "X")
        assert "LineItem" in mock_rq.call_args[0][1]

    def test_query_uses_count(self):
        """The Cypher query uses count to check for references."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_item_kinds.run_query",
            return_value=[{"in_use": False}],
        ) as mock_rq:
            line_item_kind_in_use(driver, "X")
        assert "count" in mock_rq.call_args[0][1].lower()
