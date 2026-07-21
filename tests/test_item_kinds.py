"""Tests for the item-kinds REST API."""

from unittest.mock import MagicMock, patch

BASE = "/api/v1/item-kinds"


def test_create_item_kind(client, admin_headers):
    with (
        patch("app.routers.item_kinds.item_kind_exists", return_value=False),
        patch(
            "app.routers.item_kinds.create_item_kind",
            return_value=[{"name": "Rack"}],
        ),
    ):
        response = client.post(BASE, json={"name": "Rack"}, headers=admin_headers)
    assert response.status_code == 201
    assert response.json() == {"name": "Rack"}


def test_create_duplicate_item_kind(client, admin_headers):
    with patch("app.routers.item_kinds.item_kind_exists", return_value=True):
        response = client.post(BASE, json={"name": "Rack"}, headers=admin_headers)
    assert response.status_code == 409


def test_create_empty_item_kind_rejected(client, admin_headers):
    response = client.post(BASE, json={"name": ""}, headers=admin_headers)
    assert response.status_code == 422


def test_list_item_kinds(client):
    kinds = [{"name": "Box"}, {"name": "Rack"}]
    with patch("app.routers.item_kinds.get_all_item_kinds", return_value=kinds):
        response = client.get(BASE)
    assert response.status_code == 200
    assert response.json() == {"total": 2, "data": kinds}


def test_delete_item_kind(client, admin_headers):
    mock_delete = MagicMock(return_value=[])
    with (
        patch("app.routers.item_kinds.item_kind_exists", return_value=True),
        patch("app.routers.item_kinds.item_kind_in_use", return_value=False),
        patch("app.routers.item_kinds.delete_item_kind", mock_delete),
    ):
        response = client.delete(f"{BASE}/Rack", headers=admin_headers)
    assert response.status_code == 204
    mock_delete.assert_called_once()


def test_delete_missing_item_kind(client, admin_headers):
    with patch("app.routers.item_kinds.item_kind_exists", return_value=False):
        response = client.delete(f"{BASE}/Unknown", headers=admin_headers)
    assert response.status_code == 204


def test_delete_item_kind_in_use(client, admin_headers):
    with (
        patch("app.routers.item_kinds.item_kind_exists", return_value=True),
        patch("app.routers.item_kinds.item_kind_in_use", return_value=True),
    ):
        response = client.delete(f"{BASE}/Rack", headers=admin_headers)
    assert response.status_code == 409
