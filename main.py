from datetime import date as date_type
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import logic
import storage
from models import RecordIn, RecordOut

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

    if not records:
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

    enriched = [logic.enrich_record(r) for r in records]
    count = len(enriched)
    for r in enriched:
        bmi_counts[r["bmi_category"]] += 1
        bp_counts[r["bp_category"]] += 1
        sugar_counts[r["sugar_category"]] += 1

    return {
        "count": count,
        "avg_weight": round(sum(r["weight"] for r in enriched) / count, 1),
        "avg_bmi": round(sum(r["bmi"] for r in enriched) / count, 1),
        "avg_systolic": round(sum(r["systolic"] for r in enriched) / count, 1),
        "avg_diastolic": round(sum(r["diastolic"] for r in enriched) / count, 1),
        "avg_blood_sugar": round(sum(r["blood_sugar"] for r in enriched) / count, 1),
        "bmi_category_counts": bmi_counts,
        "bp_category_counts": bp_counts,
        "sugar_category_counts": sugar_counts,
    }
