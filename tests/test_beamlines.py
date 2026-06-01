from fastapi.testclient import TestClient
from app.main import app, _beam_lines


client = TestClient(app)


def test_create_and_get_list_and_detail_and_delete():
    # ensure empty
    _beam_lines.clear()

    headers = {"Authorization": "Bearer admin-token", "Content-type": "application/json"}
    # create
    r = client.post(
        "/api/v1/beam-lines",
        json={"Name": "Line A", "Description": "Test line"},
        headers=headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert "ID" in body
    created_id = body["ID"]

    # list
    r = client.get("/api/v1/beam-lines")
    assert r.status_code == 200
    data = r.json()
    assert data["Total"] == 1

    # detail
    r = client.get(f"/api/v1/beam-lines/{created_id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["Data"]["ID"] == created_id

    # patch
    r = client.patch(
        f"/api/v1/beam-lines/{created_id}", json={"Name": "Line A Renamed"}, headers=headers
    )
    assert r.status_code == 204

    # delete without force
    r = client.delete(f"/api/v1/beam-lines/{created_id}", headers=headers)
    assert r.status_code == 204
