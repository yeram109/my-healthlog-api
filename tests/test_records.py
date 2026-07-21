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


def test_create_record_includes_bmi_and_categories():
    res = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["bmi"] == 23.0
    assert body["bmi_category"] == "과체중"
    assert body["bp_category"] == "정상"
    assert body["sugar_category"] == "정상"
    assert body["warnings"] == []


def test_warnings_triggered_for_high_risk_values():
    risky_record = {
        **SAMPLE_RECORD,
        "weight": 90,
        "height": 160,
        "systolic": 150,
        "diastolic": 95,
        "blood_sugar": 130,
    }
    res = client.post("/records", json=risky_record, headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["bmi_category"] == "비만"
    assert body["bp_category"] == "고혈압"
    assert body["sugar_category"] == "당뇨 의심"
    assert len(body["warnings"]) == 3


def test_put_updates_record():
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    updated_body = {**SAMPLE_RECORD, "weight": 68.0, "memo": "updated"}
    res = client.put(f"/records/{created['id']}", json=updated_body, headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    body = res.json()
    assert body["weight"] == 68.0
    assert body["memo"] == "updated"
    assert body["user"] == "alice"


def test_put_missing_id_returns_404():
    res = client.put("/records/999", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    assert res.status_code == 404


def test_put_other_users_record_returns_403():
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.put(f"/records/{created['id']}", json=SAMPLE_RECORD, headers={"X-User-Id": "bob"})
    assert res.status_code == 403


def test_admin_can_put_others_record():
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    updated_body = {**SAMPLE_RECORD, "weight": 60.0}
    res = client.put(f"/records/{created['id']}", json=updated_body, headers={"X-User-Id": "admin"})
    assert res.status_code == 200
    assert res.json()["weight"] == 60.0


def test_delete_record_success():
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.delete(f"/records/{created['id']}", headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    assert res.json() == {"message": "삭제되었습니다", "deleted_id": created["id"]}

    follow_up = client.get(f"/records/{created['id']}", headers={"X-User-Id": "alice"})
    assert follow_up.status_code == 404


def test_delete_missing_id_returns_404():
    res = client.delete("/records/999", headers={"X-User-Id": "alice"})
    assert res.status_code == 404


def test_delete_other_users_record_returns_403():
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.delete(f"/records/{created['id']}", headers={"X-User-Id": "bob"})
    assert res.status_code == 403


def test_search_without_range_returns_all_own_records():
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers={"X-User-Id": "alice"})

    res = client.get("/search", headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    assert res.json()["count"] == 2


def test_search_with_one_sided_range():
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers={"X-User-Id": "alice"})

    res = client.get("/search?start=2026-07-15", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 1
    assert body["records"][0]["date"] == "2026-07-20"


def test_search_with_both_bounds():
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-01"}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers={"X-User-Id": "alice"})

    res = client.get("/search?start=2026-07-05&end=2026-07-15", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 1
    assert body["records"][0]["date"] == "2026-07-10"


def test_search_start_after_end_returns_422():
    res = client.get("/search?start=2026-07-20&end=2026-07-01", headers={"X-User-Id": "alice"})
    assert res.status_code == 422


def test_search_invalid_date_format_returns_422():
    res = client.get("/search?start=2026/07/20", headers={"X-User-Id": "alice"})
    assert res.status_code == 422


def test_stats_empty_returns_nulls():
    res = client.get("/stats", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 0
    assert body["avg_weight"] is None
    assert body["avg_bmi"] is None
    assert body["bmi_category_counts"] == {"저체중": 0, "정상": 0, "과체중": 0, "비만": 0}


def test_stats_computes_averages_and_category_counts():
    normal_record = {**SAMPLE_RECORD, "weight": 70.5, "height": 175, "systolic": 118, "diastolic": 76, "blood_sugar": 95}
    risky_record = {**SAMPLE_RECORD, "weight": 90, "height": 160, "systolic": 150, "diastolic": 95, "blood_sugar": 130}
    client.post("/records", json=normal_record, headers={"X-User-Id": "alice"})
    client.post("/records", json=risky_record, headers={"X-User-Id": "alice"})

    res = client.get("/stats", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 2
    assert body["avg_bmi"] == round((23.0 + 35.2) / 2, 1)
    assert body["bmi_category_counts"]["과체중"] == 1
    assert body["bmi_category_counts"]["비만"] == 1
    assert body["bp_category_counts"]["정상"] == 1
    assert body["bp_category_counts"]["고혈압"] == 1


def test_stats_scoped_to_user():
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "bob"})

    res = client.get("/stats", headers={"X-User-Id": "alice"})
    assert res.json()["count"] == 1

    res_admin = client.get("/stats", headers={"X-User-Id": "admin"})
    assert res_admin.json()["count"] == 2


def test_root_serves_html_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
