"""Unit tests for app/cruds/items.py.

All Neo4j DB calls (``run_query``) are patched so these tests run without
any live database.  Each test validates the query construction, parameter
forwarding, and return-value processing inside the CRUD layer.
"""

import asyncio
from unittest.mock import MagicMock, patch


from app.cruds.items import (
    conn_items_exist,
    create,
    delete_item_record,
    get_item_record,
    get_item_records,
    get_item_relationships,
    get_total_item_records,
    update_item_record,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver() -> MagicMock:
    """Return a minimal MagicMock standing in for a Neo4j Driver."""
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
# create
# ---------------------------------------------------------------------------


class TestCreate:
    def _payload(self, **overrides):
        base = {
            "name": "RACK-01",
            "description": None,
            "kind": "Rack",
            "status": 0,
            "labels": [],
            "aliases": [],
            "connections": [],
        }
        return {**base, **overrides}

    def test_returns_run_query_result(self):
        """The list returned by run_query is passed back unchanged."""
        driver = _make_driver()
        expected = [{"id": 42}]
        with patch("app.cruds.items.run_query", return_value=expected):
            result = create(driver, self._payload())
        assert result == expected

    def test_returns_empty_list_on_db_failure(self):
        """An empty list from run_query is returned as-is."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]):
            result = create(driver, self._payload())
        assert result == []

    def test_passes_driver_as_first_arg(self):
        """run_query receives the driver as its first positional argument."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload())
        assert mock_rq.call_args[0][0] is driver

    def test_query_contains_merge_and_create(self):
        """The Cypher query contains both MERGE (counter) and CREATE (node) keywords."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload())
        query = mock_rq.call_args[0][1]
        assert "MERGE" in query
        assert "CREATE" in query

    def test_query_returns_id(self):
        """The query returns i.id AS id."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload())
        query = mock_rq.call_args[0][1]
        assert "id" in query.lower()

    def test_name_forwarded_in_params(self):
        """The name field is included in the parameters sent to run_query."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(name="MY-RACK"))
        params = mock_rq.call_args[0][2]
        assert params["name"] == "MY-RACK"

    def test_kind_forwarded_in_params(self):
        """The kind field is included in the parameters sent to run_query."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(kind="MTBX"))
        params = mock_rq.call_args[0][2]
        assert params["kind"] == "MTBX"

    def test_labels_forwarded_in_params(self):
        """The labels list is forwarded to run_query parameters."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(labels=["rack", "service"]))
        params = mock_rq.call_args[0][2]
        assert params["labels"] == ["rack", "service"]

    def test_aliases_forwarded_in_params(self):
        """The aliases list is forwarded to run_query parameters."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(aliases=["R-1", "R-2"]))
        params = mock_rq.call_args[0][2]
        assert params["aliases"] == ["R-1", "R-2"]

    def test_connections_deduped_in_params(self):
        """Duplicate connection IDs are deduplicated before being forwarded."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(connections=[1, 2, 1, 3, 2]))
        params = mock_rq.call_args[0][2]
        assert sorted(params["connections"]) == [1, 2, 3]

    def test_empty_connections_forwarded(self):
        """An empty connections list is forwarded as an empty list."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            create(driver, self._payload(connections=[]))
        params = mock_rq.call_args[0][2]
        assert params["connections"] == []


# ---------------------------------------------------------------------------
# get_total_item_records
# ---------------------------------------------------------------------------


class TestGetTotalItemRecords:
    def test_returns_count_from_record(self):
        """The total value from the first record is returned as an integer."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[{"total": 7}]):
            result = get_total_item_records(driver, {"name": None, "alias": None})
        assert result == 7

    def test_returns_zero_when_no_records(self):
        """Returns 0 when run_query comes back empty."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]):
            result = get_total_item_records(driver, {"name": None, "alias": None})
        assert result == 0

    def test_passes_params_to_run_query(self):
        """The params dict is forwarded to run_query."""
        driver = _make_driver()
        params = {"name": "rack", "alias": None}
        with patch("app.cruds.items.run_query", return_value=[{"total": 1}]) as mock_rq:
            get_total_item_records(driver, params)
        assert mock_rq.call_args[0][2] == params

    def test_query_contains_count(self):
        """The generated Cypher query uses a COUNT aggregate."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[{"total": 0}]) as mock_rq:
            get_total_item_records(driver, {"name": None, "alias": None})
        query = mock_rq.call_args[0][1].lower()
        assert "count" in query

    def test_query_contains_where_clause(self):
        """The query includes a WHERE clause for optional name/alias filtering."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[{"total": 0}]) as mock_rq:
            get_total_item_records(driver, {"name": None, "alias": None})
        query = mock_rq.call_args[0][1].upper()
        assert "WHERE" in query


# ---------------------------------------------------------------------------
# get_item_records
# ---------------------------------------------------------------------------


class TestGetItemRecords:
    def _call(
        self, driver, records, *, sort=None, page=1, per_page=10, name=None, alias=None
    ):
        with patch("app.cruds.items.run_query", return_value=records):
            return get_item_records(
                driver,
                {"name": name, "alias": alias},
                sort=sort,
                page=page,
                per_page=per_page,
            )

    def test_returns_list_of_dicts(self):
        """Each record is mapped to a dict with id, name, and description keys."""
        driver = _make_driver()
        node = _make_node(id=1, name="RACK-01")
        node.get = lambda k, d=None: "desc" if k == "description" else d
        result = self._call(driver, [{"i": node}])
        assert result == [{"id": 1, "name": "RACK-01", "description": "desc"}]

    def test_empty_db_result_returns_empty_list(self):
        """An empty run_query result yields an empty list."""
        driver = _make_driver()
        result = self._call(driver, [])
        assert result == []

    def test_description_none_when_absent(self):
        """description defaults to None when the node does not carry that property."""
        driver = _make_driver()
        node = _make_node(id=2, name="MTBX-01")
        node.get = lambda k, d=None: d
        result = self._call(driver, [{"i": node}])
        assert result[0]["description"] is None

    def test_pagination_skip_calculated_correctly(self):
        """skip = (page-1) * per_page is included in query parameters."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            get_item_records(
                driver, {"name": None, "alias": None}, sort=None, page=4, per_page=5
            )
        params = mock_rq.call_args[0][2]
        assert params["skip"] == 15  # (4-1) * 5
        assert params["limit"] == 5

    def test_sort_by_name_adds_order_clause(self):
        """sort=['name'] results in an ORDER BY clause in the query."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            get_item_records(
                driver,
                {"name": None, "alias": None},
                sort=["name"],
                page=1,
                per_page=10,
            )
        query = mock_rq.call_args[0][1].lower()
        assert "order by" in query

    def test_sort_by_kind_adds_order_clause(self):
        """sort=['kind'] results in an ORDER BY clause in the query."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            get_item_records(
                driver,
                {"name": None, "alias": None},
                sort=["kind"],
                page=1,
                per_page=10,
            )
        query = mock_rq.call_args[0][1].lower()
        assert "order by" in query

    def test_no_sort_omits_order_clause(self):
        """sort=None means no ORDER BY clause in the query."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            get_item_records(
                driver, {"name": None, "alias": None}, sort=None, page=1, per_page=10
            )
        query = mock_rq.call_args[0][1].lower()
        assert "order by" not in query

    def test_multiple_records_all_mapped(self):
        """All records returned by run_query appear in the output list."""
        driver = _make_driver()
        nodes = []
        for i, name in enumerate(["A", "B", "C"], start=1):
            n = _make_node(id=i, name=name)
            n.get = lambda k, d=None: d
            nodes.append({"i": n})
        result = self._call(driver, nodes)
        assert len(result) == 3
        assert [r["name"] for r in result] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# get_item_record (async)
# ---------------------------------------------------------------------------


class TestGetItemRecord:
    def test_returns_none_when_not_found(self):
        """Returns None when run_query yields no records."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]):
            result = asyncio.run(get_item_record(driver, 999))
        assert result is None

    def test_returns_dict_with_links_and_data(self):
        """A found record returns a dict with 'links' and 'data' keys."""
        driver = _make_driver()
        node = _make_node(
            id=1,
            name="RACK-01",
            description=None,
            kind="Rack",
            status=0,
            labels=[],
            aliases=[],
        )
        with patch("app.cruds.items.run_query", return_value=[{"i": node}]):
            result = asyncio.run(get_item_record(driver, 1))
        assert result is not None
        assert "links" in result
        assert "data" in result

    def test_data_contains_all_fields(self):
        """The data dict has id, name, description, kind, status, labels, aliases."""
        driver = _make_driver()
        node = _make_node(
            id=5,
            name="MTBX-01",
            description="A box",
            kind="MTBX",
            status=1,
            labels=["l"],
            aliases=["a"],
        )
        with patch("app.cruds.items.run_query", return_value=[{"i": node}]):
            result = asyncio.run(get_item_record(driver, 5))
        data = result["data"]
        assert data["id"] == 5
        assert data["name"] == "MTBX-01"
        assert data["description"] == "A box"
        assert data["kind"] == "MTBX"
        assert data["status"] == 1
        assert data["labels"] == ["l"]
        assert data["aliases"] == ["a"]

    def test_labels_default_to_empty_list(self):
        """labels defaults to [] when the node property is absent."""
        driver = _make_driver()
        node = MagicMock()
        # .get returns default for labels and aliases
        node.get = lambda k, default=None: default
        with patch("app.cruds.items.run_query", return_value=[{"i": node}]):
            result = asyncio.run(get_item_record(driver, 1))
        assert result["data"]["labels"] == []

    def test_aliases_default_to_empty_list(self):
        """aliases defaults to [] when the node property is absent."""
        driver = _make_driver()
        node = MagicMock()
        node.get = lambda k, default=None: default
        with patch("app.cruds.items.run_query", return_value=[{"i": node}]):
            result = asyncio.run(get_item_record(driver, 1))
        assert result["data"]["aliases"] == []

    def test_links_contain_connections_url(self):
        """The links dict has a connections URL containing the item_id."""
        driver = _make_driver()
        node = _make_node(
            id=7,
            name="X",
            description=None,
            kind="Rack",
            status=0,
            labels=[],
            aliases=[],
        )
        with patch("app.cruds.items.run_query", return_value=[{"i": node}]):
            result = asyncio.run(get_item_record(driver, 7))
        assert "7" in result["links"]["connections"]

    def test_query_uses_correct_id_param(self):
        """The Cypher query is called with the correct id parameter."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            asyncio.run(get_item_record(driver, 99))
        assert mock_rq.call_args[0][2] == {"id": 99}


# ---------------------------------------------------------------------------
# update_item_record
# ---------------------------------------------------------------------------


class TestUpdateItemRecord:
    def test_returns_run_query_result(self):
        """The list returned by run_query is passed back unchanged."""
        driver = _make_driver()
        expected = [{"id": 42}]
        with patch("app.cruds.items.run_query", return_value=expected):
            result = update_item_record(driver, {"name": "NEW"}, item_id=42)
        assert result == expected

    def test_returns_empty_list_when_not_found(self):
        """An empty list from run_query signals no node was matched."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]):
            result = update_item_record(driver, {"name": "X"}, item_id=999)
        assert result == []

    def test_query_includes_name_set_clause(self):
        """SET clause includes i.name when name is in payload."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            update_item_record(driver, {"name": "NEW"}, item_id=1)
        assert "i.name" in mock_rq.call_args[0][1]

    def test_query_includes_description_set_clause(self):
        """SET clause includes i.description when description is in payload."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            update_item_record(driver, {"description": "desc"}, item_id=1)
        assert "i.description" in mock_rq.call_args[0][1]

    def test_query_includes_status_set_clause(self):
        """SET clause includes i.status when status is in payload."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            update_item_record(driver, {"status": 2}, item_id=1)
        assert "i.status" in mock_rq.call_args[0][1]

    def test_query_includes_labels_set_clause(self):
        """SET clause includes i.labels when labels is in payload."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            update_item_record(driver, {"labels": ["l"]}, item_id=1)
        assert "i.labels" in mock_rq.call_args[0][1]

    def test_query_includes_aliases_set_clause(self):
        """SET clause includes i.aliases when aliases is in payload."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            update_item_record(driver, {"aliases": ["a"]}, item_id=1)
        assert "i.aliases" in mock_rq.call_args[0][1]

    def test_item_id_passed_as_id_parameter(self):
        """The item_id is forwarded to run_query under the 'id' key."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            update_item_record(driver, {"name": "X"}, item_id=55)
        assert mock_rq.call_args[0][2]["id"] == 55

    def test_multiple_set_clauses_all_included(self):
        """All provided fields appear as SET clauses in the query."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            update_item_record(
                driver,
                {
                    "name": "N",
                    "description": "D",
                    "status": 1,
                    "labels": [],
                    "aliases": [],
                },
                item_id=1,
            )
        query = mock_rq.call_args[0][1]
        for clause in ("i.name", "i.description", "i.status", "i.labels", "i.aliases"):
            assert clause in query


# ---------------------------------------------------------------------------
# get_item_relationships
# ---------------------------------------------------------------------------


class TestGetItemRelationships:
    def test_returns_run_query_result(self):
        """The raw run_query list is returned as-is."""
        driver = _make_driver()
        expected = [{"id": 42, "linked_count": 2}]
        with patch("app.cruds.items.run_query", return_value=expected):
            result = get_item_relationships(driver, 42)
        assert result == expected

    def test_passes_correct_id_parameter(self):
        """The item_id is forwarded in the parameters dict under 'id'."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            get_item_relationships(driver, 77)
        assert mock_rq.call_args[0][2] == {"id": 77}

    def test_query_uses_optional_match(self):
        """The query uses OPTIONAL MATCH to handle items without connections."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            get_item_relationships(driver, 1)
        query = mock_rq.call_args[0][1].upper()
        assert "OPTIONAL MATCH" in query

    def test_returns_empty_list_when_no_node(self):
        """An empty list is returned when run_query finds nothing."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]):
            result = get_item_relationships(driver, 999)
        assert result == []

    def test_query_counts_relationships(self):
        """The query returns a linked_count aggregate."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            get_item_relationships(driver, 1)
        query = mock_rq.call_args[0][1].lower()
        assert "linked_count" in query


# ---------------------------------------------------------------------------
# delete_item_record
# ---------------------------------------------------------------------------


class TestDeleteItemRecord:
    def test_calls_run_query_once(self):
        """run_query is called exactly once."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            delete_item_record(driver, 1)
        mock_rq.assert_called_once()

    def test_passes_correct_id_parameter(self):
        """The item_id is passed under the 'id' key in parameters."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            delete_item_record(driver, 88)
        assert mock_rq.call_args[0][2] == {"id": 88}

    def test_query_contains_detach_delete(self):
        """The Cypher query uses DETACH DELETE to remove the node and all edges."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            delete_item_record(driver, 1)
        query = mock_rq.call_args[0][1].upper()
        assert "DETACH DELETE" in query

    def test_returns_run_query_result(self):
        """The return value of run_query is passed back to the caller."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]):
            result = delete_item_record(driver, 1)
        assert result == []

    def test_passes_driver_to_run_query(self):
        """The driver instance is forwarded as the first argument to run_query."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            delete_item_record(driver, 1)
        assert mock_rq.call_args[0][0] is driver


# ---------------------------------------------------------------------------
# conn_items_exist
# ---------------------------------------------------------------------------


class TestConnItemsExist:
    def test_returns_true_when_all_exist(self):
        """Returns True when run_query confirms all IDs are present."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[{"all_exist": True}]):
            result = conn_items_exist(driver, [1, 2, 3])
        assert result is True

    def test_returns_false_when_some_missing(self):
        """Returns False when run_query indicates at least one ID is missing."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[{"all_exist": False}]):
            result = conn_items_exist(driver, [1, 999])
        assert result is False

    def test_returns_true_for_empty_list(self):
        """Returns True immediately for an empty list without calling run_query."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]) as mock_rq:
            result = conn_items_exist(driver, [])
        assert result is True
        mock_rq.assert_not_called()

    def test_deduplicates_ids_before_query(self):
        """Duplicate IDs are deduplicated before being forwarded to run_query."""
        driver = _make_driver()
        with patch(
            "app.cruds.items.run_query", return_value=[{"all_exist": True}]
        ) as mock_rq:
            conn_items_exist(driver, [1, 2, 1, 3, 2])
        passed_ids = mock_rq.call_args[0][2]["ids"]
        assert sorted(passed_ids) == [1, 2, 3]

    def test_passes_ids_to_run_query(self):
        """The deduplicated IDs list is forwarded in the parameters dict."""
        driver = _make_driver()
        with patch(
            "app.cruds.items.run_query", return_value=[{"all_exist": True}]
        ) as mock_rq:
            conn_items_exist(driver, [5, 6])
        assert "ids" in mock_rq.call_args[0][2]

    def test_query_uses_unwind(self):
        """The Cypher query uses UNWIND to iterate over the IDs list."""
        driver = _make_driver()
        with patch(
            "app.cruds.items.run_query", return_value=[{"all_exist": True}]
        ) as mock_rq:
            conn_items_exist(driver, [1])
        query = mock_rq.call_args[0][1].upper()
        assert "UNWIND" in query

    def test_returns_false_when_run_query_empty(self):
        """Returns False when run_query returns an empty list."""
        driver = _make_driver()
        with patch("app.cruds.items.run_query", return_value=[]):
            result = conn_items_exist(driver, [1])
        assert result is False
