from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from .. import auth, logic, storage
from ..db import get_session
from ..models import RecordCreate, RecordRead, User

router = APIRouter(tags=["records"])

BMI_CATEGORIES = ["저체중", "정상", "과체중", "비만"]
BP_CATEGORIES = ["정상", "주의", "고혈압"]
SUGAR_CATEGORIES = ["정상", "공복혈당장애", "당뇨 의심"]


def _validate_date_param(value: str | None) -> None:
    if value is None:
        return
    try:
        date_type.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="start/end는 YYYY-MM-DD 형식이어야 합니다")


@router.post("/records", status_code=201, response_model=RecordRead)
def create_record(
    record: RecordCreate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    stored = storage.add_record(session, record.model_dump(), current_user)
    return logic.enrich_record(stored.model_dump())


@router.get("/records")
def list_records(
    target_user: str | None = None,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    records = storage.get_records(session, current_user, target_user)
    enriched = [logic.enrich_record(r.model_dump()) for r in records]
    return {"count": len(enriched), "records": enriched}


@router.get("/records/{record_id}", response_model=RecordRead)
def get_record(
    record_id: int,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    record = storage.get_record_by_id(session, record_id)
    if record is None or not storage.check_ownership(record, current_user):
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    return logic.enrich_record(record.model_dump())


@router.put("/records/{record_id}", response_model=RecordRead)
def replace_record(
    record_id: int,
    record: RecordCreate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    existing = storage.get_record_by_id(session, record_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    if not storage.check_ownership(existing, current_user):
        raise HTTPException(status_code=403, detail="본인의 기록만 수정할 수 있습니다")
    updated = storage.update_record(session, record_id, record.model_dump())
    return logic.enrich_record(updated.model_dump())


@router.delete("/records/{record_id}")
def delete_record(
    record_id: int,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    existing = storage.get_record_by_id(session, record_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    if not storage.check_ownership(existing, current_user):
        raise HTTPException(status_code=403, detail="본인의 기록만 삭제할 수 있습니다")
    storage.delete_record(session, record_id)
    return {"message": "삭제되었습니다", "deleted_id": record_id}


@router.get("/search")
def search_records(
    start: str | None = None,
    end: str | None = None,
    target_user: str | None = None,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    _validate_date_param(start)
    _validate_date_param(end)
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start가 end보다 늦을 수 없습니다")

    records = storage.search_records(session, current_user, start, end, target_user)
    enriched = [logic.enrich_record(r.model_dump()) for r in records]
    return {"count": len(enriched), "records": enriched}


@router.get("/stats")
def get_stats(
    target_user: str | None = None,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    records = [r.model_dump() for r in storage.get_records(session, current_user, target_user)]
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
            "avg_steps": None,
            "avg_sleep_hours": None,
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
