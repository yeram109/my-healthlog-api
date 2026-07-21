import pytest
from fastapi.testclient import TestClient

import storage
from main import app

client = TestClient(app)

SAMPLE_RECORD = {
    "date": "2026-07-20",
    "weight": 70.5,
    "height": 175,
    "systolic": 118,
    "diastolic": 76,
    "blood_sugar": 95,
    "steps": 8000,
    "sleep_hours": 7.5,
    "memo": "",
}


@pytest.fixture(autouse=True)
def isolate_data(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_FILE", tmp_path / "data.json")


def test_create_record_returns_201_with_owner():
    res = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    assert res.status_code == 201
    body = res.json()
    assert body["id"] == 1
    assert body["user"] == "alice"
    assert body["date"] == "2026-07-20"


def test_create_record_defaults_to_guest_without_header():
    res = client.post("/records", json=SAMPLE_RECORD)
    assert res.status_code == 201
    assert res.json()["user"] == "guest"


def test_list_records_filters_by_user():
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "bob"})

    res = client.get("/records", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 1
    assert body["records"][0]["user"] == "alice"


def test_list_records_admin_sees_all():
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "bob"})

    res = client.get("/records", headers={"X-User-Id": "admin"})
    assert res.json()["count"] == 2


def test_get_record_by_id_success():
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.get(f"/records/{created['id']}", headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    assert res.json()["id"] == created["id"]


def test_get_record_missing_id_returns_404():
    res = client.get("/records/999", headers={"X-User-Id": "alice"})
    assert res.status_code == 404


def test_get_other_users_record_returns_404():
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.get(f"/records/{created['id']}", headers={"X-User-Id": "bob"})
    assert res.status_code == 404


def test_invalid_date_format_returns_422():
    bad_record = {**SAMPLE_RECORD, "date": "2026/07/20"}
    res = client.post("/records", json=bad_record, headers={"X-User-Id": "alice"})
    assert res.status_code == 422
