from datetime import date as date_type

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from .. import auth, logic, storage
from ..db import get_session
from ..models import User

router = APIRouter(prefix="/admin", tags=["admin"])


def _latest_status(session: Session, user_id: int) -> tuple[str, int]:
    records = storage.get_records_by_user_id(session, user_id)
    if not records:
        return "정상", 0
    latest = max(records, key=lambda r: r.date)
    enriched = logic.enrich_record(latest.model_dump())
    status = logic.summarize_user_status(enriched["bmi_category"], enriched["bp_category"], enriched["sugar_category"])
    return status, len(records)


@router.get("/users")
def list_users(session: Session = Depends(get_session), _: User = Depends(auth.require_admin)) -> dict:
    users = session.exec(select(User).where(User.is_active == True)).all()  # noqa: E712
    result = []
    for u in users:
        status, record_count = _latest_status(session, u.id)
        result.append({
            "username": u.username,
            "created_at": u.created_at,
            "record_count": record_count,
            "status": status,
        })
    return {"users": result}


@router.get("/stats")
def admin_stats(session: Session = Depends(get_session), _: User = Depends(auth.require_admin)) -> dict:
    users = session.exec(select(User).where(User.is_active == True)).all()  # noqa: E712
    today_str = date_type.today().isoformat()

    total_users = len(users)
    today_records = 0
    at_risk_users = 0
    bmis: list[float] = []

    for u in users:
        records = storage.get_records_by_user_id(session, u.id)
        today_records += sum(1 for r in records if r.date == today_str)
        if not records:
            continue
        latest = max(records, key=lambda r: r.date)
        enriched = logic.enrich_record(latest.model_dump())
        bmis.append(enriched["bmi"])
        status = logic.summarize_user_status(enriched["bmi_category"], enriched["bp_category"], enriched["sugar_category"])
        if status == "위험":
            at_risk_users += 1

    avg_bmi_all = round(sum(bmis) / len(bmis), 1) if bmis else None

    return {
        "total_users": total_users,
        "today_records": today_records,
        "at_risk_users": at_risk_users,
        "avg_bmi_all": avg_bmi_all,
    }
