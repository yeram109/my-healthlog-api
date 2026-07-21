from datetime import date as date_type
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import logic
import storage
from models import GoalIn, RecordIn, RecordOut

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="마이 헬스 로그 API")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

BMI_CATEGORIES = ["저체중", "정상", "과체중", "비만"]
BP_CATEGORIES = ["정상", "주의", "고혈압"]
SUGAR_CATEGORIES = ["정상", "공복혈당장애", "당뇨 의심"]


def get_current_user(x_user_id: str | None = Header(default=None)) -> str:
    return x_user_id or "guest"


def _validate_date_param(value: str | None) -> None:
    if value is None:
        return
    try:
        date_type.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="start/end는 YYYY-MM-DD 형식이어야 합니다")


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api")
def api_status() -> dict[str, str]:
    return {"message": "마이 헬스 로그 API"}


@app.post("/records", status_code=201, response_model=RecordOut)
def create_record(record: RecordIn, user: str = Depends(get_current_user)) -> dict:
    stored = storage.add_record(record.model_dump(), user)
    return logic.enrich_record(stored)


@app.get("/records")
def list_records(user: str = Depends(get_current_user)) -> dict:
    records = storage.get_records(user)
    enriched = [logic.enrich_record(r) for r in records]
    return {"count": len(enriched), "records": enriched}


@app.get("/records/{record_id}", response_model=RecordOut)
def get_record(record_id: int, user: str = Depends(get_current_user)) -> dict:
    record = storage.get_record_by_id(record_id)
    if record is None or not storage.check_ownership(record, user):
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    return logic.enrich_record(record)


@app.put("/records/{record_id}", response_model=RecordOut)
def replace_record(record_id: int, record: RecordIn, user: str = Depends(get_current_user)) -> dict:
    existing = storage.get_record_by_id(record_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    if not storage.check_ownership(existing, user):
        raise HTTPException(status_code=403, detail="본인의 기록만 수정할 수 있습니다")
    updated = storage.update_record(record_id, record.model_dump())
    return logic.enrich_record(updated)


@app.delete("/records/{record_id}")
def delete_record(record_id: int, user: str = Depends(get_current_user)) -> dict:
    existing = storage.get_record_by_id(record_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    if not storage.check_ownership(existing, user):
        raise HTTPException(status_code=403, detail="본인의 기록만 삭제할 수 있습니다")
    storage.delete_record(record_id)
    return {"message": "삭제되었습니다", "deleted_id": record_id}


@app.get("/search")
def search_records(
    start: str | None = None,
    end: str | None = None,
    user: str = Depends(get_current_user),
) -> dict:
    _validate_date_param(start)
    _validate_date_param(end)
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start가 end보다 늦을 수 없습니다")

    records = storage.get_records(user)
    filtered = [
        r
        for r in records
        if (start is None or r["date"] >= start) and (end is None or r["date"] <= end)
    ]
    enriched = [logic.enrich_record(r) for r in filtered]
    return {"count": len(enriched), "records": enriched}


@app.get("/stats")
def get_stats(user: str = Depends(get_current_user)) -> dict:
    records = storage.get_records(user)
    bmi_counts = {c: 0 for c in BMI_CATEGORIES}
    bp_counts = {c: 0 for c in BP_CATEGORIES}
    sugar_counts = {c: 0 for c in SUGAR_CATEGORIES}

    averages = logic.calculate_averages(records)
    if averages is None:
        return {
            "count": 0,
            "avg_weight": None,
            "avg_bmi": None,
            "avg_systolic": None,
            "avg_diastolic": None,
            "avg_blood_sugar": None,
            "bmi_category_counts": bmi_counts,
            "bp_category_counts": bp_counts,
            "sugar_category_counts": sugar_counts,
        }

    for r in records:
        enriched = logic.enrich_record(r)
        bmi_counts[enriched["bmi_category"]] += 1
        bp_counts[enriched["bp_category"]] += 1
        sugar_counts[enriched["sugar_category"]] += 1

    return {
        **averages,
        "bmi_category_counts": bmi_counts,
        "bp_category_counts": bp_counts,
        "sugar_category_counts": sugar_counts,
    }


@app.put("/goal")
def set_goal(goal: GoalIn, user: str = Depends(get_current_user)) -> dict:
    stored_goal = {
        "target_weight": goal.target_weight,
        "target_systolic": goal.target_systolic,
        "target_diastolic": goal.target_diastolic,
        "set_date": date_type.today().isoformat(),
    }
    storage.set_goal(user, stored_goal)
    return {"goal": stored_goal}


@app.get("/goal")
def get_goal(user: str = Depends(get_current_user)) -> dict:
    goal = storage.get_goal(user)
    if goal is None:
        return {"goal": None}
    records = storage.get_records(user)
    achievement = logic.calculate_goal_achievement(goal, records)
    return {"goal": goal, "achievement": achievement}


@app.get("/reports/weekly")
def get_weekly_report(user: str = Depends(get_current_user)) -> dict:
    records = storage.get_records(user)
    today = date_type.today()
    this_week_start = (today - timedelta(days=7)).isoformat()
    last_week_start = (today - timedelta(days=14)).isoformat()

    this_week = [r for r in records if r["date"] >= this_week_start]
    last_week = [r for r in records if last_week_start <= r["date"] < this_week_start]

    this_week_avg = logic.calculate_averages(this_week)
    last_week_avg = logic.calculate_averages(last_week)

    delta = None
    if this_week_avg is not None and last_week_avg is not None:
        delta = {
            "weight": round(this_week_avg["avg_weight"] - last_week_avg["avg_weight"], 1),
            "bmi": round(this_week_avg["avg_bmi"] - last_week_avg["avg_bmi"], 1),
            "systolic": round(this_week_avg["avg_systolic"] - last_week_avg["avg_systolic"], 1),
            "diastolic": round(this_week_avg["avg_diastolic"] - last_week_avg["avg_diastolic"], 1),
            "blood_sugar": round(this_week_avg["avg_blood_sugar"] - last_week_avg["avg_blood_sugar"], 1),
        }

    return {
        "this_week": this_week_avg,
        "last_week": last_week_avg,
        "delta": delta,
    }
