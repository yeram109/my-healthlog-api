from datetime import date, timedelta

from sqlmodel import select

from models import User

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


def test_signup_creates_user(client):
    res = client.post("/auth/signup", json={"username": "newuser", "password": "pass1234"})
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "newuser"
    assert body["is_admin"] is False
    assert "password" not in body
    assert "hashed_password" not in body


def test_signup_duplicate_username_returns_400(client):
    client.post("/auth/signup", json={"username": "dupuser", "password": "pass1234"})
    res = client.post("/auth/signup", json={"username": "dupuser", "password": "other5678"})
    assert res.status_code == 400


def test_signup_ignores_is_admin_field(client, session):
    client.post("/auth/signup", json={"username": "sneaky", "password": "pass1234", "is_admin": True})
    user = session.exec(select(User).where(User.username == "sneaky")).first()
    assert user.is_admin is False


def test_login_success_returns_token(client):
    client.post("/auth/signup", json={"username": "loginuser", "password": "pass1234"})
    res = client.post("/auth/login", data={"username": "loginuser", "password": "pass1234"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_returns_401(client):
    client.post("/auth/signup", json={"username": "wrongpass", "password": "correct123"})
    res = client.post("/auth/login", data={"username": "wrongpass", "password": "incorrect"})
    assert res.status_code == 401


def test_login_nonexistent_user_returns_401(client):
    res = client.post("/auth/login", data={"username": "nobody", "password": "whatever"})
    assert res.status_code == 401


def test_protected_endpoint_without_token_returns_401(client):
    res = client.get("/records")
    assert res.status_code == 401


def test_protected_endpoint_with_invalid_token_returns_401(client):
    res = client.get("/records", headers={"Authorization": "Bearer invalid-token"})
    assert res.status_code == 401


def test_delete_account_deactivates_user(client, auth_headers, session):
    res = client.delete("/auth/me", headers=auth_headers("deleteuser"))
    assert res.status_code == 200

    user = session.exec(select(User).where(User.username == "deleteuser")).first()
    assert user.is_active is False


def test_delete_account_requires_auth(client):
    res = client.delete("/auth/me")
    assert res.status_code == 401


def test_deactivated_user_cannot_login(client, auth_headers):
    client.delete("/auth/me", headers=auth_headers("relogin"))
    res = client.post("/auth/login", data={"username": "relogin", "password": "testpass123"})
    assert res.status_code == 403


def test_deactivated_user_existing_token_becomes_unauthorized(client, auth_headers):
    headers = auth_headers("tokenholder")
    client.delete("/auth/me", headers=headers)
    res = client.get("/records", headers=headers)
    assert res.status_code == 401


def test_records_preserved_after_account_deletion(client, auth_headers):
    headers = auth_headers("preserveduser")
    client.post("/records", json=SAMPLE_RECORD, headers=headers)
    client.delete("/auth/me", headers=headers)

    res = client.get("/records", headers=auth_headers("admin", is_admin=True))
    assert res.json()["count"] == 1


def test_create_record_returns_201_with_owner(client, auth_headers, session):
    res = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice"))
    assert res.status_code == 201
    body = res.json()
    alice = session.exec(select(User).where(User.username == "alice")).first()
    assert body["id"] == 1
    assert body["user_id"] == alice.id
    assert body["date"] == "2026-07-20"


def test_list_records_filters_by_user(client, auth_headers, session):
    client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice"))
    client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("bob"))

    res = client.get("/records", headers=auth_headers("alice"))
    body = res.json()
    alice = session.exec(select(User).where(User.username == "alice")).first()
    assert body["count"] == 1
    assert body["records"][0]["user_id"] == alice.id


def test_list_records_admin_sees_all(client, auth_headers):
    client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice"))
    client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("bob"))

    res = client.get("/records", headers=auth_headers("admin", is_admin=True))
    assert res.json()["count"] == 2


def test_get_record_by_id_success(client, auth_headers):
    created = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice")).json()
    res = client.get(f"/records/{created['id']}", headers=auth_headers("alice"))
    assert res.status_code == 200
    assert res.json()["id"] == created["id"]


def test_get_record_missing_id_returns_404(client, auth_headers):
    res = client.get("/records/999", headers=auth_headers("alice"))
    assert res.status_code == 404


def test_get_other_users_record_returns_404(client, auth_headers):
    created = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice")).json()
    res = client.get(f"/records/{created['id']}", headers=auth_headers("bob"))
    assert res.status_code == 404


def test_invalid_date_format_returns_422(client, auth_headers):
    bad_record = {**SAMPLE_RECORD, "date": "2026/07/20"}
    res = client.post("/records", json=bad_record, headers=auth_headers("alice"))
    assert res.status_code == 422


def test_create_record_includes_bmi_and_categories(client, auth_headers):
    res = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice"))
    body = res.json()
    assert body["bmi"] == 23.0
    assert body["bmi_category"] == "과체중"
    assert body["bp_category"] == "정상"
    assert body["sugar_category"] == "정상"
    assert body["warnings"] == []


def test_warnings_triggered_for_high_risk_values(client, auth_headers):
    risky_record = {
        **SAMPLE_RECORD,
        "weight": 90,
        "height": 160,
        "systolic": 150,
        "diastolic": 95,
        "blood_sugar": 130,
    }
    res = client.post("/records", json=risky_record, headers=auth_headers("alice"))
    body = res.json()
    assert body["bmi_category"] == "비만"
    assert body["bp_category"] == "고혈압"
    assert body["sugar_category"] == "당뇨 의심"
    assert len(body["warnings"]) == 3


def test_put_updates_record(client, auth_headers, session):
    created = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice")).json()
    updated_body = {**SAMPLE_RECORD, "weight": 68.0, "memo": "updated"}
    res = client.put(f"/records/{created['id']}", json=updated_body, headers=auth_headers("alice"))
    assert res.status_code == 200
    body = res.json()
    alice = session.exec(select(User).where(User.username == "alice")).first()
    assert body["weight"] == 68.0
    assert body["memo"] == "updated"
    assert body["user_id"] == alice.id


def test_put_missing_id_returns_404(client, auth_headers):
    res = client.put("/records/999", json=SAMPLE_RECORD, headers=auth_headers("alice"))
    assert res.status_code == 404


def test_put_other_users_record_returns_403(client, auth_headers):
    created = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice")).json()
    res = client.put(f"/records/{created['id']}", json=SAMPLE_RECORD, headers=auth_headers("bob"))
    assert res.status_code == 403


def test_admin_can_put_others_record(client, auth_headers):
    created = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice")).json()
    updated_body = {**SAMPLE_RECORD, "weight": 60.0}
    res = client.put(f"/records/{created['id']}", json=updated_body, headers=auth_headers("admin", is_admin=True))
    assert res.status_code == 200
    assert res.json()["weight"] == 60.0


def test_delete_record_success(client, auth_headers):
    created = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice")).json()
    res = client.delete(f"/records/{created['id']}", headers=auth_headers("alice"))
    assert res.status_code == 200
    assert res.json() == {"message": "삭제되었습니다", "deleted_id": created["id"]}

    follow_up = client.get(f"/records/{created['id']}", headers=auth_headers("alice"))
    assert follow_up.status_code == 404


def test_delete_missing_id_returns_404(client, auth_headers):
    res = client.delete("/records/999", headers=auth_headers("alice"))
    assert res.status_code == 404


def test_delete_other_users_record_returns_403(client, auth_headers):
    created = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice")).json()
    res = client.delete(f"/records/{created['id']}", headers=auth_headers("bob"))
    assert res.status_code == 403


def test_search_without_range_returns_all_own_records(client, auth_headers):
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers=auth_headers("alice"))
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers=auth_headers("alice"))

    res = client.get("/search", headers=auth_headers("alice"))
    assert res.status_code == 200
    assert res.json()["count"] == 2


def test_search_with_one_sided_range(client, auth_headers):
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers=auth_headers("alice"))
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers=auth_headers("alice"))

    res = client.get("/search?start=2026-07-15", headers=auth_headers("alice"))
    body = res.json()
    assert body["count"] == 1
    assert body["records"][0]["date"] == "2026-07-20"


def test_search_with_both_bounds(client, auth_headers):
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-01"}, headers=auth_headers("alice"))
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-10"}, headers=auth_headers("alice"))
    client.post("/records", json={**SAMPLE_RECORD, "date": "2026-07-20"}, headers=auth_headers("alice"))

    res = client.get("/search?start=2026-07-05&end=2026-07-15", headers=auth_headers("alice"))
    body = res.json()
    assert body["count"] == 1
    assert body["records"][0]["date"] == "2026-07-10"


def test_search_start_after_end_returns_422(client, auth_headers):
    res = client.get("/search?start=2026-07-20&end=2026-07-01", headers=auth_headers("alice"))
    assert res.status_code == 422


def test_search_invalid_date_format_returns_422(client, auth_headers):
    res = client.get("/search?start=2026/07/20", headers=auth_headers("alice"))
    assert res.status_code == 422


def test_stats_empty_returns_nulls(client, auth_headers):
    res = client.get("/stats", headers=auth_headers("alice"))
    body = res.json()
    assert body["count"] == 0
    assert body["avg_weight"] is None
    assert body["avg_bmi"] is None
    assert body["bmi_category_counts"] == {"저체중": 0, "정상": 0, "과체중": 0, "비만": 0}


def test_stats_computes_averages_and_category_counts(client, auth_headers):
    normal_record = {**SAMPLE_RECORD, "weight": 70.5, "height": 175, "systolic": 118, "diastolic": 76, "blood_sugar": 95}
    risky_record = {**SAMPLE_RECORD, "weight": 90, "height": 160, "systolic": 150, "diastolic": 95, "blood_sugar": 130}
    client.post("/records", json=normal_record, headers=auth_headers("alice"))
    client.post("/records", json=risky_record, headers=auth_headers("alice"))

    res = client.get("/stats", headers=auth_headers("alice"))
    body = res.json()
    assert body["count"] == 2
    assert body["avg_bmi"] == round((23.0 + 35.2) / 2, 1)
    assert body["avg_steps"] == 8000
    assert body["avg_sleep_hours"] == 7.5
    assert body["bmi_category_counts"]["과체중"] == 1
    assert body["bmi_category_counts"]["비만"] == 1
    assert body["bp_category_counts"]["정상"] == 1
    assert body["bp_category_counts"]["고혈압"] == 1


def test_stats_scoped_to_user(client, auth_headers):
    client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice"))
    client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("bob"))

    res = client.get("/stats", headers=auth_headers("alice"))
    assert res.json()["count"] == 1

    res_admin = client.get("/stats", headers=auth_headers("admin", is_admin=True))
    assert res_admin.json()["count"] == 2


def test_root_serves_html_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


GOAL_PAYLOAD = {"target_weight": 65, "target_systolic": 120, "target_diastolic": 80}


def test_get_goal_returns_null_when_not_set(client, auth_headers):
    res = client.get("/goal", headers=auth_headers("alice"))
    assert res.json() == {"goal": None}


def test_set_goal_returns_stored_goal(client, auth_headers):
    res = client.put("/goal", json=GOAL_PAYLOAD, headers=auth_headers("alice"))
    assert res.status_code == 200
    body = res.json()
    assert body["goal"]["target_weight"] == 65
    assert body["goal"]["target_systolic"] == 120
    assert body["goal"]["target_diastolic"] == 80
    assert body["goal"]["set_date"] == date.today().isoformat()


def test_goal_achievement_none_without_records_since_goal_set(client, auth_headers):
    client.put("/goal", json=GOAL_PAYLOAD, headers=auth_headers("alice"))
    res = client.get("/goal", headers=auth_headers("alice"))
    assert res.json()["achievement"] is None


def test_goal_achievement_calculated_from_records_since_goal_set(client, auth_headers):
    client.put("/goal", json=GOAL_PAYLOAD, headers=auth_headers("alice"))
    today_str = date.today().isoformat()
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()

    client.post(
        "/records",
        json={**SAMPLE_RECORD, "date": today_str, "weight": 70, "systolic": 130, "diastolic": 90},
        headers=auth_headers("alice"),
    )
    client.post(
        "/records",
        json={**SAMPLE_RECORD, "date": tomorrow_str, "weight": 67, "systolic": 125, "diastolic": 85},
        headers=auth_headers("alice"),
    )

    res = client.get("/goal", headers=auth_headers("alice"))
    achievement = res.json()["achievement"]
    assert achievement["weight_percent"] == 60.0
    assert achievement["systolic_percent"] == 50.0
    assert achievement["diastolic_percent"] == 50.0


def test_goal_achievement_clamped_at_100_when_exceeded(client, auth_headers):
    client.put("/goal", json=GOAL_PAYLOAD, headers=auth_headers("alice"))
    today_str = date.today().isoformat()
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()

    client.post(
        "/records",
        json={**SAMPLE_RECORD, "date": today_str, "weight": 70, "systolic": 130, "diastolic": 90},
        headers=auth_headers("alice"),
    )
    client.post(
        "/records",
        json={**SAMPLE_RECORD, "date": tomorrow_str, "weight": 50, "systolic": 100, "diastolic": 70},
        headers=auth_headers("alice"),
    )

    res = client.get("/goal", headers=auth_headers("alice"))
    achievement = res.json()["achievement"]
    assert achievement["weight_percent"] == 100.0
    assert achievement["systolic_percent"] == 100.0
    assert achievement["diastolic_percent"] == 100.0


def test_goal_scoped_to_user(client, auth_headers):
    client.put("/goal", json=GOAL_PAYLOAD, headers=auth_headers("alice"))
    res = client.get("/goal", headers=auth_headers("bob"))
    assert res.json() == {"goal": None}


def test_weekly_report_empty_returns_nulls(client, auth_headers):
    res = client.get("/reports/weekly", headers=auth_headers("alice"))
    assert res.json() == {"this_week": None, "last_week": None, "delta": None}


def test_weekly_report_computes_averages_and_delta(client, auth_headers):
    today = date.today()
    this_week_dates = [today - timedelta(days=1), today - timedelta(days=3)]
    last_week_dates = [today - timedelta(days=8), today - timedelta(days=10)]

    for record_date, weight in zip(this_week_dates, [70, 72]):
        client.post(
            "/records",
            json={**SAMPLE_RECORD, "date": record_date.isoformat(), "weight": weight},
            headers=auth_headers("alice"),
        )
    for record_date, weight in zip(last_week_dates, [75, 77]):
        client.post(
            "/records",
            json={**SAMPLE_RECORD, "date": record_date.isoformat(), "weight": weight},
            headers=auth_headers("alice"),
        )

    res = client.get("/reports/weekly", headers=auth_headers("alice"))
    body = res.json()
    assert body["this_week"]["count"] == 2
    assert body["this_week"]["avg_weight"] == 71.0
    assert body["last_week"]["count"] == 2
    assert body["last_week"]["avg_weight"] == 76.0
    assert body["delta"]["weight"] == -5.0
    assert body["this_week"]["avg_steps"] == 8000
    assert body["this_week"]["avg_sleep_hours"] == 7.5
    assert body["delta"]["steps"] == 0.0
    assert body["delta"]["sleep_hours"] == 0.0


def test_weekly_report_scoped_to_user(client, auth_headers):
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    client.post("/records", json={**SAMPLE_RECORD, "date": yesterday_str}, headers=auth_headers("alice"))
    client.post("/records", json={**SAMPLE_RECORD, "date": yesterday_str}, headers=auth_headers("bob"))

    res = client.get("/reports/weekly", headers=auth_headers("alice"))
    assert res.json()["this_week"]["count"] == 1


def test_default_steps_and_sleep_categories(client, auth_headers):
    res = client.post("/records", json=SAMPLE_RECORD, headers=auth_headers("alice"))
    body = res.json()
    assert body["steps_grade"] == "적정"
    assert body["sleep_category"] == "적정"


def test_steps_grade_boundary_values(client, auth_headers):
    def steps_grade(steps):
        res = client.post("/records", json={**SAMPLE_RECORD, "steps": steps}, headers=auth_headers("alice"))
        return res.json()["steps_grade"]

    assert steps_grade(4999) == "부족"
    assert steps_grade(5000) == "적정"
    assert steps_grade(9999) == "적정"
    assert steps_grade(10000) == "우수"


def test_sleep_category_boundary_values(client, auth_headers):
    def sleep_category(sleep_hours):
        res = client.post("/records", json={**SAMPLE_RECORD, "sleep_hours": sleep_hours}, headers=auth_headers("alice"))
        return res.json()["sleep_category"]

    assert sleep_category(6.9) == "부족"
    assert sleep_category(7.0) == "적정"
    assert sleep_category(9.0) == "적정"
    assert sleep_category(9.1) == "과다"
