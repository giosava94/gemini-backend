"""Unit tests for app/cruds/beam_lines.py.

All Neo4j DB calls (``run_query``) are patched so these tests run without
any live database.  Each test validates the query construction, parameter
forwarding, and return-value processing inside the CRUD layer.
"""

import asyncio
from unittest.mock import MagicMock, patch


from app.cruds.beam_lines import (
    create_beam_line_record,
    delete_beam_line_record,
    get_beam_line_record,
    get_beam_line_records,
    get_beam_line_relationships,
    get_total_beam_line_records,
    update_beam_line_record,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver() -> MagicMock:
    """Return a minimal MagicMock that stands in for a Neo4j Driver."""
    return MagicMock()


def _make_node(**fields) -> MagicMock:
    """Return a MagicMock that behaves like a Neo4j node.

    Supports both item access (``node["key"]``) and ``.get("key", default)``.
    """
    node = MagicMock()
    node.__getitem__ = lambda _, k: fields[k]
    node.get = lambda k, default=None: fields.get(k, default)
    return node


# ---------------------------------------------------------------------------
# create_beam_line_record
# ---------------------------------------------------------------------------


class TestCreateBeamLineRecord:
    def test_returns_run_query_result(self):
        """The function forwards the driver + query to run_query and returns its result."""
        driver = _make_driver()
        expected = [{"id": 1}]
        with patch("app.cruds.beam_lines.run_query", return_value=expected) as mock_rq:
            result = create_beam_line_record(
                driver, {"name": "LEBT", "description": "Low energy"}
            )
        assert result == expected
        mock_rq.assert_called_once()

    def test_passes_driver_as_first_arg(self):
        """run_query receives the driver as its first positional argument."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            create_beam_line_record(driver, {"name": "LEBT", "description": None})
        assert mock_rq.call_args[0][0] is driver

    def test_passes_payload_as_parameters(self):
        """Payload dict is forwarded as the parameters argument to run_query."""
        driver = _make_driver()
        payload = {"name": "MEBT", "description": "Medium energy"}
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            create_beam_line_record(driver, payload)
        _, _ = mock_rq.call_args[0][2], mock_rq.call_args[0][2]
        assert mock_rq.call_args[0][2] == payload

    def test_query_contains_merge_and_create(self):
        """The Cypher query string contains MERGE and CREATE keywords."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            create_beam_line_record(driver, {"name": "X", "description": None})
        query = mock_rq.call_args[0][1]
        assert "MERGE" in query
        assert "CREATE" in query

    def test_returns_empty_list_on_db_failure(self):
        """An empty list from run_query is passed back unchanged."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]):
            result = create_beam_line_record(driver, {"name": "X", "description": None})
        assert result == []


# ---------------------------------------------------------------------------
# get_total_beam_line_records
# ---------------------------------------------------------------------------


class TestGetTotalBeamLineRecords:
    def test_returns_count_from_record(self):
        """The total value from the first record is returned as an integer."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[{"total": 42}]):
            result = get_total_beam_line_records(driver, {"name": None})
        assert result == 42

    def test_returns_zero_when_no_records(self):
        """Returns 0 when run_query comes back empty."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]):
            result = get_total_beam_line_records(driver, {"name": None})
        assert result == 0

    def test_passes_params_to_run_query(self):
        """The params dict (including the name filter) is forwarded to run_query."""
        driver = _make_driver()
        params = {"name": "lebt"}
        with patch(
            "app.cruds.beam_lines.run_query", return_value=[{"total": 1}]
        ) as mock_rq:
            get_total_beam_line_records(driver, params)
        assert mock_rq.call_args[0][2] == params

    def test_query_contains_count(self):
        """The generated Cypher query uses a COUNT aggregate."""
        driver = _make_driver()
        with patch(
            "app.cruds.beam_lines.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_beam_line_records(driver, {"name": None})
        query = mock_rq.call_args[0][1].lower()
        assert "count" in query


# ---------------------------------------------------------------------------
# get_beam_line_records
# ---------------------------------------------------------------------------


class TestGetBeamLineRecords:
    def _call(self, driver, records, *, sort=None, page=1, per_page=10, name=None):
        with patch("app.cruds.beam_lines.run_query", return_value=records):
            return get_beam_line_records(
                driver, {"name": name}, sort=sort, page=page, per_page=per_page
            )

    def test_returns_list_of_dicts(self):
        """Each record is mapped to a dict with id, name, and description keys."""
        driver = _make_driver()
        node = _make_node(id=1, name="LEBT")
        node.get = lambda k, d=None: "Low energy" if k == "description" else d
        result = self._call(driver, [{"b": node}])
        assert result == [{"id": 1, "name": "LEBT", "description": "Low energy"}]

    def test_empty_db_result_returns_empty_list(self):
        """An empty run_query result yields an empty list."""
        driver = _make_driver()
        result = self._call(driver, [])
        assert result == []

    def test_description_none_when_absent(self):
        """description is None when the node does not carry that property."""
        driver = _make_driver()
        node = _make_node(id=2, name="MEBT")
        node.get = lambda k, d=None: d  # always returns default
        result = self._call(driver, [{"b": node}])
        assert result[0]["description"] is None

    def test_pagination_skip_calculated_correctly(self):
        """skip = (page-1) * per_page is included in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            get_beam_line_records(driver, {"name": None}, sort=None, page=3, per_page=5)
        params = mock_rq.call_args[0][2]
        assert params["skip"] == 10  # (3-1) * 5
        assert params["limit"] == 5

    def test_sort_by_name_adds_order_clause(self):
        """When sort=['name'], the ORDER BY clause appears in the query."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            get_beam_line_records(
                driver, {"name": None}, sort=["name"], page=1, per_page=10
            )
        query = mock_rq.call_args[0][1].lower()
        assert "order by" in query

    def test_no_sort_omits_order_clause(self):
        """When sort is None, the ORDER BY clause is absent from the query."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            get_beam_line_records(
                driver, {"name": None}, sort=None, page=1, per_page=10
            )
        query = mock_rq.call_args[0][1].lower()
        assert "order by" not in query

    def test_multiple_records_all_mapped(self):
        """All records returned by run_query are present in the output list."""
        driver = _make_driver()
        nodes = []
        for i, name in enumerate(["A", "B", "C"], start=1):
            n = _make_node(id=i, name=name)
            n.get = lambda k, d=None: d
            nodes.append({"b": n})
        result = self._call(driver, nodes)
        assert len(result) == 3
        assert [r["name"] for r in result] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# get_beam_line_record
# ---------------------------------------------------------------------------


class TestGetBeamLineRecord:
    def test_returns_none_when_not_found(self):
        """Returns None when run_query yields no records."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]):
            result = asyncio.run(get_beam_line_record(driver, 999))
        assert result is None

    def test_returns_dict_with_links_and_data(self):
        """A found record is returned with 'links' and 'data' sub-dicts."""
        driver = _make_driver()
        node = MagicMock()
        node.get = lambda k, d=None: {
            "id": 1,
            "name": "LEBT",
            "description": "Low energy",
        }.get(k, d)
        with patch("app.cruds.beam_lines.run_query", return_value=[{"b": node}]):
            result = asyncio.run(get_beam_line_record(driver, 1))
        assert result is not None
        assert "links" in result
        assert "data" in result

    def test_data_contains_expected_fields(self):
        """The 'data' dict has id, name, and description keys."""
        driver = _make_driver()
        node = MagicMock()
        node.get = lambda k, d=None: {
            "id": 7,
            "name": "HEBT",
            "description": "High",
        }.get(k, d)
        with patch("app.cruds.beam_lines.run_query", return_value=[{"b": node}]):
            result = asyncio.run(get_beam_line_record(driver, 7))
        data = result["data"]
        assert data["id"] == 7
        assert data["name"] == "HEBT"
        assert data["description"] == "High"

    def test_links_contain_line_items_url(self):
        """The links dict includes a line_items URL containing the beam_id."""
        driver = _make_driver()
        node = MagicMock()
        node.get = lambda k, d=None: {"id": 5, "name": "X", "description": None}.get(
            k, d
        )
        with patch("app.cruds.beam_lines.run_query", return_value=[{"b": node}]):
            result = asyncio.run(get_beam_line_record(driver, 5))
        assert "5" in result["links"]["line_items"]

    def test_query_uses_correct_id_param(self):
        """The Cypher query is called with the correct id parameter."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            asyncio.run(get_beam_line_record(driver, 42))
        assert mock_rq.call_args[0][2] == {"id": 42}


# ---------------------------------------------------------------------------
# update_beam_line_record
# ---------------------------------------------------------------------------


class TestUpdateBeamLineRecord:
    def test_returns_run_query_result(self):
        """The list returned by run_query is passed back unchanged."""
        driver = _make_driver()
        expected = [{"b": MagicMock()}]
        with patch("app.cruds.beam_lines.run_query", return_value=expected):
            result = update_beam_line_record(driver, {"name": "NEW"}, beam_id=1)
        assert result == expected

    def test_returns_empty_list_when_not_found(self):
        """An empty list signals that no node was matched."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]):
            result = update_beam_line_record(driver, {"name": "X"}, beam_id=999)
        assert result == []

    def test_query_includes_name_set_clause(self):
        """SET clause includes b.name when name is in payload."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            update_beam_line_record(driver, {"name": "NEW"}, beam_id=1)
        query = mock_rq.call_args[0][1]
        assert "b.name" in query

    def test_query_includes_description_set_clause(self):
        """SET clause includes b.description when description is in payload."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            update_beam_line_record(driver, {"description": "desc"}, beam_id=1)
        query = mock_rq.call_args[0][1]
        assert "b.description" in query

    def test_query_includes_both_set_clauses(self):
        """Both b.name and b.description appear when both fields are provided."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            update_beam_line_record(
                driver, {"name": "N", "description": "D"}, beam_id=1
            )
        query = mock_rq.call_args[0][1]
        assert "b.name" in query
        assert "b.description" in query

    def test_beam_id_passed_as_id_parameter(self):
        """The beam_id is included in the parameters as 'id'."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            update_beam_line_record(driver, {"name": "X"}, beam_id=7)
        params = mock_rq.call_args[0][2]
        assert params["id"] == 7


# ---------------------------------------------------------------------------
# get_beam_line_relationships
# ---------------------------------------------------------------------------


class TestGetBeamLineRelationships:
    def test_returns_run_query_result(self):
        """The raw run_query list is returned as-is."""
        driver = _make_driver()
        expected = [{"linked_count": 3}]
        with patch("app.cruds.beam_lines.run_query", return_value=expected):
            result = get_beam_line_relationships(driver, 1)
        assert result == expected

    def test_passes_correct_id_parameter(self):
        """The beam_id is forwarded in the parameters dict under 'id'."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            get_beam_line_relationships(driver, 99)
        assert mock_rq.call_args[0][2] == {"id": 99}

    def test_query_uses_optional_match(self):
        """The query contains OPTIONAL MATCH to handle missing nodes gracefully."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            get_beam_line_relationships(driver, 1)
        query = mock_rq.call_args[0][1].upper()
        assert "OPTIONAL MATCH" in query

    def test_returns_empty_when_no_node(self):
        """An empty list is returned when run_query finds nothing."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]):
            result = get_beam_line_relationships(driver, 999)
        assert result == []


# ---------------------------------------------------------------------------
# delete_beam_line_record
# ---------------------------------------------------------------------------


class TestDeleteBeamLineRecord:
    def test_calls_run_query_once(self):
        """run_query is called exactly once with the correct beam_id."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            delete_beam_line_record(driver, 1)
        mock_rq.assert_called_once()

    def test_passes_correct_id_parameter(self):
        """The beam_id is passed under the 'id' key in parameters."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            delete_beam_line_record(driver, 42)
        assert mock_rq.call_args[0][2] == {"id": 42}

    def test_query_contains_detach_delete(self):
        """The Cypher query uses DETACH DELETE to remove the node and its edges."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            delete_beam_line_record(driver, 1)
        query = mock_rq.call_args[0][1].upper()
        assert "DETACH DELETE" in query

    def test_returns_run_query_result(self):
        """The return value of run_query is passed back to the caller."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]):
            result = delete_beam_line_record(driver, 1)
        assert result == []

    def test_passes_driver_to_run_query(self):
        """The driver instance is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch("app.cruds.beam_lines.run_query", return_value=[]) as mock_rq:
            delete_beam_line_record(driver, 1)
        assert mock_rq.call_args[0][0] is driver
