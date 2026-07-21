"""Unit tests for item-kind CRUD helpers."""

from unittest.mock import MagicMock, patch

from app.cruds.item_kinds import (
    create_item_kind,
    delete_item_kind,
    get_all_item_kinds,
    item_kind_exists,
    item_kind_in_use,
)


def test_create_item_kind_query_and_parameters():
    driver = MagicMock()
    expected = [{"name": "Rack"}]
    with patch("app.cruds.item_kinds.run_query", return_value=expected) as run:
        assert create_item_kind(driver, "Rack") == expected
    assert "ItemKind" in run.call_args[0][1]
    assert run.call_args[0][2] == {"name": "Rack"}


def test_get_all_item_kinds_maps_and_orders_records():
    driver = MagicMock()
    with patch(
        "app.cruds.item_kinds.run_query", return_value=[{"name": "Rack"}]
    ) as run:
        assert get_all_item_kinds(driver) == [{"name": "Rack"}]
    assert "ORDER BY" in run.call_args[0][1]


def test_delete_item_kind_query_and_parameters():
    driver = MagicMock()
    with patch("app.cruds.item_kinds.run_query", return_value=[]) as run:
        assert delete_item_kind(driver, "Rack") == []
    assert "DELETE" in run.call_args[0][1]
    assert run.call_args[0][2] == {"name": "Rack"}


def test_item_kind_exists():
    driver = MagicMock()
    with patch("app.cruds.item_kinds.run_query", return_value=[{"exists": True}]):
        assert item_kind_exists(driver, "Rack") is True


def test_item_kind_in_use_targets_items():
    driver = MagicMock()
    with patch(
        "app.cruds.item_kinds.run_query", return_value=[{"in_use": True}]
    ) as run:
        assert item_kind_in_use(driver, "Rack") is True
    assert "MATCH (i:Item" in run.call_args[0][1]
