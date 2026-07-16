"""Unit tests for app/cruds/line_items.py.

All Neo4j DB calls (``run_query``) are patched so these tests run without
any live database.  Each test validates the query construction, parameter
forwarding, and return-value processing inside the CRUD layer.
"""

import asyncio
from unittest.mock import MagicMock, patch


from app.cruds.line_items import (
    adj_and_conn_items_exist,
    beam_line_exists,
    create,
    delete_line_item_record,
    get_line_item_record,
    get_line_item_records,
    get_line_item_relationships,
    get_total_line_item_records,
    has_duplicate_adjacent_index,
    update_line_item_record,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver() -> MagicMock:
    """Return a minimal MagicMock standing in for a Neo4j Driver."""
    return MagicMock()


def _make_node(**fields) -> MagicMock:
    """Return a MagicMock that behaves like a Neo4j node."""
    node = MagicMock()
    node.__getitem__ = lambda _, k: fields[k]
    node.get = lambda k, default=None: fields.get(k, default)
    return node


# ---------------------------------------------------------------------------
# has_duplicate_adjacent_index  (pure function — no DB needed)
# ---------------------------------------------------------------------------


class TestHasDuplicateAdjacentIndex:
    def test_empty_list_returns_false(self):
        """An empty adjacents list has no duplicates."""
        assert has_duplicate_adjacent_index([]) is False

    def test_single_item_returns_false(self):
        """A single adjacent entry cannot create a duplicate."""
        assert (
            has_duplicate_adjacent_index([{"position": "Previous", "index": 0}])
            is False
        )

    def test_different_positions_same_index_no_duplicate(self):
        """Different positions with the same index are not considered duplicates."""
        items = [
            {"position": "Previous", "index": 0},
            {"position": "Next", "index": 0},
        ]
        assert has_duplicate_adjacent_index(items) is False

    def test_same_position_same_index_is_duplicate(self):
        """Two entries with the same (position, index) pair is a duplicate."""
        items = [
            {"position": "Previous", "index": 0},
            {"position": "Previous", "index": 0},
        ]
        assert has_duplicate_adjacent_index(items) is True

    def test_same_position_different_index_no_duplicate(self):
        """Same position but different index values are not duplicates."""
        items = [
            {"position": "Previous", "index": 0},
            {"position": "Previous", "index": 1},
        ]
        assert has_duplicate_adjacent_index(items) is False

    def test_none_index_is_skipped(self):
        """Entries where index is None are not checked for duplicates."""
        items = [
            {"position": "Previous", "index": None},
            {"position": "Previous", "index": None},
        ]
        assert has_duplicate_adjacent_index(items) is False

    def test_mixed_none_and_set_index_no_duplicate(self):
        """A None index entry and a set index entry do not form a duplicate."""
        items = [
            {"position": "Previous", "index": None},
            {"position": "Previous", "index": 0},
        ]
        assert has_duplicate_adjacent_index(items) is False

    def test_duplicate_detected_among_many(self):
        """Duplicate is detected when buried among many distinct entries."""
        items = [
            {"position": "Previous", "index": 0},
            {"position": "Next", "index": 1},
            {"position": "Previous", "index": 2},
            {"position": "Next", "index": 1},  # duplicate
        ]
        assert has_duplicate_adjacent_index(items) is True


# ---------------------------------------------------------------------------
# beam_line_exists
# ---------------------------------------------------------------------------


class TestBeamLineExists:
    def test_returns_true_when_found(self):
        """Returns True when run_query returns a record."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[{"id": 1}]):
            assert beam_line_exists(driver, 1) is True

    def test_returns_false_when_not_found(self):
        """Returns False when run_query returns an empty list."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]):
            assert beam_line_exists(driver, 99) is False

    def test_passes_id_in_params(self):
        """The beam_id is forwarded in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            beam_line_exists(driver, 42)
        assert mock_rq.call_args[0][2] == {"id": 42}

    def test_query_matches_beam_line(self):
        """The Cypher query targets BeamLine nodes."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            beam_line_exists(driver, 1)
        assert "BeamLine" in mock_rq.call_args[0][1]


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    def _payload(self, **overrides):
        base = {
            "name": "QD01",
            "description": None,
            "kind": "Diagnostic",
            "status": 0,
            "labels": [],
            "aliases": [],
            "adjacents": [],
            "connections": [],
        }
        return {**base, **overrides}

    def test_returns_run_query_result(self):
        """The list returned by run_query is passed back unchanged."""
        driver = _make_driver()
        expected = [{"id": 42}]
        with patch("app.cruds.line_items.run_query", return_value=expected):
            result = create(driver, self._payload(), beam_id=1)
        assert result == expected

    def test_returns_empty_on_db_failure(self):
        """An empty list from run_query is returned as-is."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]):
            result = create(driver, self._payload(), beam_id=1)
        assert result == []

    def test_passes_driver_as_first_arg(self):
        """run_query receives the driver as its first positional argument."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(), beam_id=1)
        assert mock_rq.call_args[0][0] is driver

    def test_beam_id_in_params(self):
        """The beam_id is forwarded under 'beam_id' in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(), beam_id=7)
        assert mock_rq.call_args[0][2]["beam_id"] == 7

    def test_name_forwarded_in_params(self):
        """The name field is included in the parameters sent to run_query."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(name="MY-ITEM"), beam_id=1)
        assert mock_rq.call_args[0][2]["name"] == "MY-ITEM"

    def test_labels_forwarded_in_params(self):
        """The labels list is forwarded to run_query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(labels=["magnet", "critical"]), beam_id=1)
        assert mock_rq.call_args[0][2]["labels"] == ["magnet", "critical"]

    def test_aliases_forwarded_in_params(self):
        """The aliases list is forwarded to run_query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(aliases=["QD01-A"]), beam_id=1)
        assert mock_rq.call_args[0][2]["aliases"] == ["QD01-A"]

    def test_connections_deduped_in_params(self):
        """Duplicate connection IDs are deduplicated before being forwarded."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(connections=[1, 2, 1, 3]), beam_id=1)
        assert sorted(mock_rq.call_args[0][2]["connections"]) == [1, 2, 3]

    def test_empty_connections_forwarded(self):
        """An empty connections list is forwarded as an empty list."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(connections=[]), beam_id=1)
        assert mock_rq.call_args[0][2]["connections"] == []

    def test_query_contains_match_beam_and_create_node(self):
        """The query matches the parent beam line and creates the LineItem node."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(), beam_id=1)
        query = mock_rq.call_args[0][1]
        assert "MATCH" in query
        assert "BeamLine" in query
        assert "CREATE" in query

    def test_query_returns_id(self):
        """The query returns li.id AS id."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(), beam_id=1)
        assert "id" in mock_rq.call_args[0][1].lower()


# ---------------------------------------------------------------------------
# get_total_line_item_records
# ---------------------------------------------------------------------------


class TestGetTotalLineItemRecords:
    def test_returns_count_from_record(self):
        """The total value from the first record is returned."""
        driver = _make_driver()
        params = {
            "beam_id": 1,
            "status": None,
            "name": None,
            "alias": None,
            "kind": None,
        }
        with patch("app.cruds.line_items.run_query", return_value=[{"total": 5}]):
            assert get_total_line_item_records(driver, params) == 5

    def test_returns_zero_when_no_records(self):
        """Returns 0 when run_query comes back empty."""
        driver = _make_driver()
        params = {
            "beam_id": 1,
            "status": None,
            "name": None,
            "alias": None,
            "kind": None,
        }
        with patch("app.cruds.line_items.run_query", return_value=[]):
            assert get_total_line_item_records(driver, params) == 0

    def test_passes_params_to_run_query(self):
        """The full params dict is forwarded to run_query."""
        driver = _make_driver()
        params = {"beam_id": 1, "status": 0, "name": "QD", "alias": None, "kind": None}
        with patch(
            "app.cruds.line_items.run_query", return_value=[{"total": 1}]
        ) as mock_rq:
            get_total_line_item_records(driver, params)
        assert mock_rq.call_args[0][2] == params

    def test_query_contains_count_and_beam_match(self):
        """The query counts items scoped to the parent beam line."""
        driver = _make_driver()
        params = {
            "beam_id": 1,
            "status": None,
            "name": None,
            "alias": None,
            "kind": None,
        }
        with patch(
            "app.cruds.line_items.run_query", return_value=[{"total": 0}]
        ) as mock_rq:
            get_total_line_item_records(driver, params)
        query = mock_rq.call_args[0][1].lower()
        assert "count" in query
        assert "beamline" in query


# ---------------------------------------------------------------------------
# get_line_item_records
# ---------------------------------------------------------------------------


class TestGetLineItemRecords:
    def _call(self, driver, records, *, sort=None, page=1, per_page=10):
        params = {
            "beam_id": 1,
            "status": None,
            "name": None,
            "alias": None,
            "kind": None,
        }
        with patch("app.cruds.line_items.run_query", return_value=records):
            return get_line_item_records(
                driver, params, sort=sort, page=page, per_page=per_page
            )

    def test_returns_list_of_dicts(self):
        """Each record is mapped to a dict with id, name, and description keys."""
        driver = _make_driver()
        node = _make_node(id=10, name="QD01")
        node.get = lambda k, d=None: "desc" if k == "description" else d
        result = self._call(driver, [{"li": node}])
        assert result == [{"id": 10, "name": "QD01", "description": "desc"}]

    def test_empty_db_result_returns_empty_list(self):
        """An empty run_query result yields an empty list."""
        driver = _make_driver()
        assert self._call(driver, []) == []

    def test_description_none_when_absent(self):
        """description defaults to None when the node does not carry that property."""
        driver = _make_driver()
        node = _make_node(id=11, name="QF01")
        node.get = lambda k, d=None: d
        result = self._call(driver, [{"li": node}])
        assert result[0]["description"] is None

    def test_pagination_skip_calculated_correctly(self):
        """skip = (page-1) * per_page is included in query parameters."""
        driver = _make_driver()
        params = {
            "beam_id": 1,
            "status": None,
            "name": None,
            "alias": None,
            "kind": None,
        }
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            get_line_item_records(driver, params, sort=None, page=3, per_page=5)
        p = mock_rq.call_args[0][2]
        assert p["skip"] == 10  # (3-1) * 5
        assert p["limit"] == 5

    def test_sort_by_name_adds_order_clause(self):
        """sort=['name'] results in an ORDER BY clause in the query."""
        driver = _make_driver()
        params = {
            "beam_id": 1,
            "status": None,
            "name": None,
            "alias": None,
            "kind": None,
        }
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            get_line_item_records(driver, params, sort=["name"], page=1, per_page=10)
        assert "ORDER BY" in mock_rq.call_args[0][1]

    def test_sort_by_kind_adds_order_clause(self):
        """sort=['kind'] results in an ORDER BY clause in the query."""
        driver = _make_driver()
        params = {
            "beam_id": 1,
            "status": None,
            "name": None,
            "alias": None,
            "kind": None,
        }
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            get_line_item_records(driver, params, sort=["kind"], page=1, per_page=10)
        assert "ORDER BY" in mock_rq.call_args[0][1]

    def test_no_sort_omits_order_clause(self):
        """sort=None means no ORDER BY clause in the query."""
        driver = _make_driver()
        params = {
            "beam_id": 1,
            "status": None,
            "name": None,
            "alias": None,
            "kind": None,
        }
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            get_line_item_records(driver, params, sort=None, page=1, per_page=10)
        assert "ORDER BY" not in mock_rq.call_args[0][1]

    def test_multiple_records_all_mapped(self):
        """All records returned by run_query appear in the output list."""
        driver = _make_driver()
        nodes = []
        for i, name in enumerate(["A", "B", "C"], start=1):
            n = _make_node(id=i, name=name)
            n.get = lambda k, d=None: d
            nodes.append({"li": n})
        result = self._call(driver, nodes)
        assert len(result) == 3
        assert [r["name"] for r in result] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# get_line_item_record (async)
# ---------------------------------------------------------------------------


class TestGetLineItemRecord:
    def test_returns_none_when_not_found(self):
        """Returns None when run_query yields no records."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]):
            result = asyncio.run(get_line_item_record(driver, beam_id=1, item_id=999))
        assert result is None

    def test_returns_dict_with_links_and_data(self):
        """A found record returns a dict with 'links' and 'data' keys."""
        driver = _make_driver()
        node = _make_node(
            id=10,
            name="QD01",
            description=None,
            kind="Diagnostic",
            status=0,
            labels=[],
            aliases=[],
        )
        with patch("app.cruds.line_items.run_query", return_value=[{"li": node}]):
            result = asyncio.run(get_line_item_record(driver, beam_id=1, item_id=10))
        assert result is not None
        assert "links" in result
        assert "data" in result

    def test_data_contains_all_fields(self):
        """The data dict has id, name, description, kind, status, labels, aliases."""
        driver = _make_driver()
        node = _make_node(
            id=5,
            name="QF01",
            description="A foc quad",
            kind="ES Quadrupole",
            status=1,
            labels=["l"],
            aliases=["a"],
        )
        with patch("app.cruds.line_items.run_query", return_value=[{"li": node}]):
            result = asyncio.run(get_line_item_record(driver, beam_id=1, item_id=5))
        data = result["data"]
        assert data["id"] == 5
        assert data["name"] == "QF01"
        assert data["description"] == "A foc quad"
        assert data["kind"] == "ES Quadrupole"
        assert data["status"] == 1
        assert data["labels"] == ["l"]
        assert data["aliases"] == ["a"]

    def test_labels_default_to_empty_list(self):
        """labels defaults to [] when the node property is absent."""
        driver = _make_driver()
        node = MagicMock()
        node.get = lambda k, default=None: default
        with patch("app.cruds.line_items.run_query", return_value=[{"li": node}]):
            result = asyncio.run(get_line_item_record(driver, beam_id=1, item_id=1))
        assert result["data"]["labels"] == []

    def test_aliases_default_to_empty_list(self):
        """aliases defaults to [] when the node property is absent."""
        driver = _make_driver()
        node = MagicMock()
        node.get = lambda k, default=None: default
        with patch("app.cruds.line_items.run_query", return_value=[{"li": node}]):
            result = asyncio.run(get_line_item_record(driver, beam_id=1, item_id=1))
        assert result["data"]["aliases"] == []

    def test_links_contain_adjacents_and_connections(self):
        """The links dict has both adjacents and connections URLs."""
        driver = _make_driver()
        node = _make_node(
            id=7,
            name="X",
            description=None,
            kind="Diagnostic",
            status=0,
            labels=[],
            aliases=[],
        )
        with patch("app.cruds.line_items.run_query", return_value=[{"li": node}]):
            result = asyncio.run(get_line_item_record(driver, beam_id=2, item_id=7))
        assert "adjacents" in result["links"]
        assert "connections" in result["links"]

    def test_links_urls_contain_beam_and_item_ids(self):
        """Both link URLs contain the beam_id and item_id."""
        driver = _make_driver()
        node = _make_node(
            id=9,
            name="X",
            description=None,
            kind="Diagnostic",
            status=0,
            labels=[],
            aliases=[],
        )
        with patch("app.cruds.line_items.run_query", return_value=[{"li": node}]):
            result = asyncio.run(get_line_item_record(driver, beam_id=3, item_id=9))
        for url in result["links"].values():
            assert "3" in url
            assert "9" in url

    def test_query_uses_correct_params(self):
        """The Cypher query is called with beam_id and item id parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            asyncio.run(get_line_item_record(driver, beam_id=5, item_id=20))
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 5
        assert params["id"] == 20


# ---------------------------------------------------------------------------
# update_line_item_record
# ---------------------------------------------------------------------------


class TestUpdateLineItemRecord:
    def test_returns_run_query_result(self):
        """The list returned by run_query is passed back unchanged."""
        driver = _make_driver()
        expected = [{"id": 10}]
        with patch("app.cruds.line_items.run_query", return_value=expected):
            result = update_line_item_record(
                driver, {"name": "NEW"}, beam_id=1, line_item_id=10
            )
        assert result == expected

    def test_returns_empty_list_when_not_found(self):
        """An empty list from run_query signals no node was matched."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]):
            result = update_line_item_record(
                driver, {"name": "X"}, beam_id=1, line_item_id=999
            )
        assert result == []

    def test_query_includes_name_set_clause(self):
        """SET clause includes li.name when name is in payload."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            update_line_item_record(driver, {"name": "NEW"}, beam_id=1, line_item_id=1)
        assert "li.name" in mock_rq.call_args[0][1]

    def test_query_includes_description_set_clause(self):
        """SET clause includes li.description when description is in payload."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            update_line_item_record(
                driver, {"description": "desc"}, beam_id=1, line_item_id=1
            )
        assert "li.description" in mock_rq.call_args[0][1]

    def test_query_includes_status_set_clause(self):
        """SET clause includes li.status when status is in payload."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            update_line_item_record(driver, {"status": 1}, beam_id=1, line_item_id=1)
        assert "li.status" in mock_rq.call_args[0][1]

    def test_query_includes_kind_set_clause(self):
        """SET clause includes li.kind when kind is in payload."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            update_line_item_record(
                driver, {"kind": "Diagnostic"}, beam_id=1, line_item_id=1
            )
        assert "li.kind" in mock_rq.call_args[0][1]

    def test_query_includes_labels_set_clause(self):
        """SET clause includes li.labels when labels is in payload."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            update_line_item_record(
                driver, {"labels": ["l"]}, beam_id=1, line_item_id=1
            )
        assert "li.labels" in mock_rq.call_args[0][1]

    def test_query_includes_aliases_set_clause(self):
        """SET clause includes li.aliases when aliases is in payload."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            update_line_item_record(
                driver, {"aliases": ["a"]}, beam_id=1, line_item_id=1
            )
        assert "li.aliases" in mock_rq.call_args[0][1]

    def test_beam_id_and_item_id_in_params(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            update_line_item_record(driver, {"name": "X"}, beam_id=3, line_item_id=7)
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 3
        assert params["id"] == 7

    def test_all_set_clauses_included(self):
        """All provided fields appear as SET clauses in the query."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            update_line_item_record(
                driver,
                {
                    "name": "N",
                    "description": "D",
                    "status": 1,
                    "kind": "Diagnostic",
                    "labels": [],
                    "aliases": [],
                },
                beam_id=1,
                line_item_id=1,
            )
        query = mock_rq.call_args[0][1]
        for clause in (
            "li.name",
            "li.description",
            "li.status",
            "li.kind",
            "li.labels",
            "li.aliases",
        ):
            assert clause in query


# ---------------------------------------------------------------------------
# get_line_item_relationships
# ---------------------------------------------------------------------------


class TestGetLineItemRelationships:
    def test_returns_run_query_result(self):
        """The raw run_query list is returned as-is."""
        driver = _make_driver()
        expected = [{"id": 10, "linked_count": 2}]
        with patch("app.cruds.line_items.run_query", return_value=expected):
            assert (
                get_line_item_relationships(driver, beam_id=1, line_item_id=10)
                == expected
            )

    def test_passes_beam_and_item_ids(self):
        """Both beam_id and line_item_id are forwarded in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            get_line_item_relationships(driver, beam_id=4, line_item_id=11)
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 4
        assert params["id"] == 11

    def test_query_uses_optional_match(self):
        """The query uses OPTIONAL MATCH to handle items without relationships."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            get_line_item_relationships(driver, beam_id=1, line_item_id=1)
        assert "OPTIONAL MATCH" in mock_rq.call_args[0][1]

    def test_returns_empty_list_when_no_node(self):
        """An empty list is returned when run_query finds nothing."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]):
            assert (
                get_line_item_relationships(driver, beam_id=1, line_item_id=999) == []
            )

    def test_query_counts_linked_relationships(self):
        """The query returns a linked_count aggregate."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            get_line_item_relationships(driver, beam_id=1, line_item_id=1)
        assert "linked_count" in mock_rq.call_args[0][1]


# ---------------------------------------------------------------------------
# delete_line_item_record
# ---------------------------------------------------------------------------


class TestDeleteLineItemRecord:
    def test_calls_run_query_once(self):
        """run_query is called exactly once."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            delete_line_item_record(driver, beam_id=1, line_item_id=10)
        mock_rq.assert_called_once()

    def test_passes_beam_and_item_ids(self):
        """Both beam_id and line_item_id are passed in the query parameters."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            delete_line_item_record(driver, beam_id=2, line_item_id=55)
        params = mock_rq.call_args[0][2]
        assert params["beam_id"] == 2
        assert params["id"] == 55

    def test_query_contains_detach_delete(self):
        """The Cypher query uses DETACH DELETE."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            delete_line_item_record(driver, beam_id=1, line_item_id=1)
        assert "DETACH DELETE" in mock_rq.call_args[0][1]

    def test_returns_run_query_result(self):
        """The return value of run_query is passed back to the caller."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]):
            assert delete_line_item_record(driver, beam_id=1, line_item_id=1) == []

    def test_passes_driver_to_run_query(self):
        """The driver instance is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            delete_line_item_record(driver, beam_id=1, line_item_id=1)
        assert mock_rq.call_args[0][0] is driver


# ---------------------------------------------------------------------------
# adj_and_conn_items_exist
# ---------------------------------------------------------------------------


class TestAdjAndConnItemsExist:
    def test_returns_true_when_all_exist(self):
        """Returns True when run_query confirms all IDs are present."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_items.run_query", return_value=[{"all_exist": True}]
        ):
            assert adj_and_conn_items_exist(driver, [1, 2]) is True

    def test_returns_false_when_some_missing(self):
        """Returns False when run_query indicates at least one ID is missing."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_items.run_query", return_value=[{"all_exist": False}]
        ):
            assert adj_and_conn_items_exist(driver, [1, 999]) is False

    def test_returns_true_for_empty_list(self):
        """Returns True immediately for an empty list without calling run_query."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]) as mock_rq:
            assert adj_and_conn_items_exist(driver, []) is True
        mock_rq.assert_not_called()

    def test_deduplicates_ids_before_query(self):
        """Duplicate IDs are deduplicated before being forwarded to run_query."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_items.run_query", return_value=[{"all_exist": True}]
        ) as mock_rq:
            adj_and_conn_items_exist(driver, [1, 2, 1, 3])
        assert sorted(mock_rq.call_args[0][2]["ids"]) == [1, 2, 3]

    def test_passes_ids_to_run_query(self):
        """The deduplicated IDs list is forwarded in the parameters dict."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_items.run_query", return_value=[{"all_exist": True}]
        ) as mock_rq:
            adj_and_conn_items_exist(driver, [5, 6])
        assert "ids" in mock_rq.call_args[0][2]

    def test_query_targets_line_item_nodes(self):
        """The Cypher query targets LineItem nodes."""
        driver = _make_driver()
        with patch(
            "app.cruds.line_items.run_query", return_value=[{"all_exist": True}]
        ) as mock_rq:
            adj_and_conn_items_exist(driver, [1])
        assert "LineItem" in mock_rq.call_args[0][1]

    def test_returns_false_when_run_query_empty(self):
        """Returns False when run_query returns an empty list."""
        driver = _make_driver()
        with patch("app.cruds.line_items.run_query", return_value=[]):
            assert adj_and_conn_items_exist(driver, [1]) is False
