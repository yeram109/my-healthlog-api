from datetime import date, timedelta

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


def test_create_record_returns_201_with_owner(client):
    res = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    assert res.status_code == 201
    body = res.json()
    assert body["id"] == 1
    assert body["user"] == "alice"
    assert body["date"] == "2026-07-20"


def test_create_record_defaults_to_guest_without_header(client):
    res = client.post("/records", json=SAMPLE_RECORD)
    assert res.status_code == 201
    assert res.json()["user"] == "guest"


def test_list_records_filters_by_user(client):
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "bob"})

    res = client.get("/records", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 1
    assert body["records"][0]["user"] == "alice"


def test_list_records_admin_sees_all(client):
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "bob"})

    res = client.get("/records", headers={"X-User-Id": "admin"})
    assert res.json()["count"] == 2


def test_get_record_by_id_success(client):
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.get(f"/records/{created['id']}", headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    assert res.json()["id"] == created["id"]


def test_get_record_missing_id_returns_404(client):
    res = client.get("/records/999", headers={"X-User-Id": "alice"})
    assert res.status_code == 404


def test_get_other_users_record_returns_404(client):
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.get(f"/records/{created['id']}", headers={"X-User-Id": "bob"})
    assert res.status_code == 404


def test_invalid_date_format_returns_422(client):
    bad_record = {**SAMPLE_RECORD, "date": "2026/07/20"}
    res = client.post("/records", json=bad_record, headers={"X-User-Id": "alice"})
    assert res.status_code == 422


def test_create_record_includes_bmi_and_categories(client):
    res = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["bmi"] == 23.0
    assert body["bmi_category"] == "과체중"
    assert body["bp_category"] == "정상"
    assert body["sugar_category"] == "정상"
    assert body["warnings"] == []


def test_warnings_triggered_for_high_risk_values(client):
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


def test_put_updates_record(client):
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    updated_body = {**SAMPLE_RECORD, "weight": 68.0, "memo": "updated"}
    res = client.put(f"/records/{created['id']}", json=updated_body, headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    body = res.json()
    assert body["weight"] == 68.0
    assert body["memo"] == "updated"
    assert body["user"] == "alice"


def test_put_missing_id_returns_404(client):
    res = client.put("/records/999", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    assert res.status_code == 404


def test_put_other_users_record_returns_403(client):
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.put(f"/records/{created['id']}", json=SAMPLE_RECORD, headers={"X-User-Id": "bob"})
    assert res.status_code == 403


def test_admin_can_put_others_record(client):
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    updated_body = {**SAMPLE_RECORD, "weight": 60.0}
    res = client.put(f"/records/{created['id']}", json=updated_body, headers={"X-User-Id": "admin"})
    assert res.status_code == 200
    assert res.json()["weight"] == 60.0


def test_delete_record_success(client):
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.delete(f"/records/{created['id']}", headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    assert res.json() == {"message": "삭제되었습니다", "deleted_id": created["id"]}

    follow_up = client.get(f"/records/{created['id']}", headers={"X-User-Id": "alice"})
    assert follow_up.status_code == 404


def test_delete_missing_id_returns_404(client):
    res = client.delete("/records/999", headers={"X-User-Id": "alice"})
    assert res.status_code == 404


def test_delete_other_users_record_returns_403(client):
    created = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"}).json()
    res = client.delete(f"/records/{created['id']}", headers={"X-User-Id": "bob"})
    assert res.status_code == 403


def test_search_without_range_returns_all_own_records(client):
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers={"X-User-Id": "alice"})

    res = client.get("/search", headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    assert res.json()["count"] == 2


def test_search_with_one_sided_range(client):
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers={"X-User-Id": "alice"})

    res = client.get("/search?start=2026-07-15", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 1
    assert body["records"][0]["date"] == "2026-07-20"


def test_search_with_both_bounds(client):
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-01"}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers={"X-User-Id": "alice"})

    res = client.get("/search?start=2026-07-05&end=2026-07-15", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 1
    assert body["records"][0]["date"] == "2026-07-10"


def test_search_start_after_end_returns_422(client):
    res = client.get("/search?start=2026-07-20&end=2026-07-01", headers={"X-User-Id": "alice"})
    assert res.status_code == 422


def test_search_invalid_date_format_returns_422(client):
    res = client.get("/search?start=2026/07/20", headers={"X-User-Id": "alice"})
    assert res.status_code == 422


def test_stats_empty_returns_nulls(client):
    res = client.get("/stats", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["count"] == 0
    assert body["avg_weight"] is None
    assert body["avg_bmi"] is None
    assert body["bmi_category_counts"] == {"저체중": 0, "정상": 0, "과체중": 0, "비만": 0}


def test_stats_computes_averages_and_category_counts(client):
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


def test_stats_scoped_to_user(client):
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "bob"})

    res = client.get("/stats", headers={"X-User-Id": "alice"})
    assert res.json()["count"] == 1

    res_admin = client.get("/stats", headers={"X-User-Id": "admin"})
    assert res_admin.json()["count"] == 2


def test_root_serves_html_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


GOAL_PAYLOAD = {"target_weight": 65, "target_systolic": 120, "target_diastolic": 80}


def test_get_goal_returns_null_when_not_set(client):
    res = client.get("/goal", headers={"X-User-Id": "alice"})
    assert res.json() == {"goal": None}


def test_set_goal_returns_stored_goal(client):
    res = client.put("/goal", json=GOAL_PAYLOAD, headers={"X-User-Id": "alice"})
    assert res.status_code == 200
    body = res.json()
    assert body["goal"]["target_weight"] == 65
    assert body["goal"]["target_systolic"] == 120
    assert body["goal"]["target_diastolic"] == 80
    assert body["goal"]["set_date"] == date.today().isoformat()


def test_goal_achievement_none_without_records_since_goal_set(client):
    client.put("/goal", json=GOAL_PAYLOAD, headers={"X-User-Id": "alice"})
    res = client.get("/goal", headers={"X-User-Id": "alice"})
    assert res.json()["achievement"] is None


def test_goal_achievement_calculated_from_records_since_goal_set(client):
    client.put("/goal", json=GOAL_PAYLOAD, headers={"X-User-Id": "alice"})
    today_str = date.today().isoformat()
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()

    client.post(
        "/records",
        json={**SAMPLE_RECORD, "date": today_str, "weight": 70, "systolic": 130, "diastolic": 90},
        headers={"X-User-Id": "alice"},
    )
    client.post(
        "/records",
        json={**SAMPLE_RECORD, "date": tomorrow_str, "weight": 67, "systolic": 125, "diastolic": 85},
        headers={"X-User-Id": "alice"},
    )

    res = client.get("/goal", headers={"X-User-Id": "alice"})
    achievement = res.json()["achievement"]
    assert achievement["weight_percent"] == 60.0
    assert achievement["systolic_percent"] == 50.0
    assert achievement["diastolic_percent"] == 50.0


def test_goal_achievement_clamped_at_100_when_exceeded(client):
    client.put("/goal", json=GOAL_PAYLOAD, headers={"X-User-Id": "alice"})
    today_str = date.today().isoformat()
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()

    client.post(
        "/records",
        json={**SAMPLE_RECORD, "date": today_str, "weight": 70, "systolic": 130, "diastolic": 90},
        headers={"X-User-Id": "alice"},
    )
    client.post(
        "/records",
        json={**SAMPLE_RECORD, "date": tomorrow_str, "weight": 50, "systolic": 100, "diastolic": 70},
        headers={"X-User-Id": "alice"},
    )

    res = client.get("/goal", headers={"X-User-Id": "alice"})
    achievement = res.json()["achievement"]
    assert achievement["weight_percent"] == 100.0
    assert achievement["systolic_percent"] == 100.0
    assert achievement["diastolic_percent"] == 100.0


def test_goal_scoped_to_user(client):
    client.put("/goal", json=GOAL_PAYLOAD, headers={"X-User-Id": "alice"})
    res = client.get("/goal", headers={"X-User-Id": "bob"})
    assert res.json() == {"goal": None}


def test_weekly_report_empty_returns_nulls(client):
    res = client.get("/reports/weekly", headers={"X-User-Id": "alice"})
    assert res.json() == {"this_week": None, "last_week": None, "delta": None}


def test_weekly_report_computes_averages_and_delta(client):
    today = date.today()
    this_week_dates = [today - timedelta(days=1), today - timedelta(days=3)]
    last_week_dates = [today - timedelta(days=8), today - timedelta(days=10)]

    for record_date, weight in zip(this_week_dates, [70, 72]):
        client.post(
            "/records",
            json={**SAMPLE_RECORD, "date": record_date.isoformat(), "weight": weight},
            headers={"X-User-Id": "alice"},
        )
    for record_date, weight in zip(last_week_dates, [75, 77]):
        client.post(
            "/records",
            json={**SAMPLE_RECORD, "date": record_date.isoformat(), "weight": weight},
            headers={"X-User-Id": "alice"},
        )

    res = client.get("/reports/weekly", headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["this_week"]["count"] == 2
    assert body["this_week"]["avg_weight"] == 71.0
    assert body["last_week"]["count"] == 2
    assert body["last_week"]["avg_weight"] == 76.0
    assert body["delta"]["weight"] == -5.0


def test_weekly_report_scoped_to_user(client):
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    client.post("/records", json={**SAMPLE_RECORD, "date": yesterday_str}, headers={"X-User-Id": "alice"})
    client.post("/records", json={**SAMPLE_RECORD, "date": yesterday_str}, headers={"X-User-Id": "bob"})

    res = client.get("/reports/weekly", headers={"X-User-Id": "alice"})
    assert res.json()["this_week"]["count"] == 1


def test_default_steps_and_sleep_categories(client):
    res = client.post("/records", json=SAMPLE_RECORD, headers={"X-User-Id": "alice"})
    body = res.json()
    assert body["steps_grade"] == "적정"
    assert body["sleep_category"] == "적정"


def test_steps_grade_boundary_values(client):
    def steps_grade(steps):
        res = client.post("/records", json={**SAMPLE_RECORD, "steps": steps}, headers={"X-User-Id": "alice"})
        return res.json()["steps_grade"]

    assert steps_grade(4999) == "부족"
    assert steps_grade(5000) == "적정"
    assert steps_grade(9999) == "적정"
    assert steps_grade(10000) == "우수"


def test_sleep_category_boundary_values(client):
    def sleep_category(sleep_hours):
        res = client.post("/records", json={**SAMPLE_RECORD, "sleep_hours": sleep_hours}, headers={"X-User-Id": "alice"})
        return res.json()["sleep_category"]

    assert sleep_category(6.9) == "부족"
    assert sleep_category(7.0) == "적정"
    assert sleep_category(9.0) == "적정"
    assert sleep_category(9.1) == "과다"
