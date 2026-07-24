from datetime import date as date_type
from datetime import timedelta

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


@router.get("/goals/overview")
def goals_overview(session: Session = Depends(get_session), _: User = Depends(auth.require_admin)) -> dict:
    users = session.exec(select(User).where(User.is_active == True)).all()  # noqa: E712
    total_users = len(users)

    entries = []
    for u in users:
        goal = storage.get_goal_by_user_id(session, u.id)
        if goal is None:
            continue
        records = [r.model_dump() for r in storage.get_records_by_user_id(session, u.id)]
        relevant = sorted((r for r in records if r["date"] >= goal.set_date), key=lambda r: r["date"])
        if not relevant:
            continue
        start_weight = relevant[0]["weight"]
        current_weight = relevant[-1]["weight"]
        progress = logic.calculate_achievement_percent(start_weight, current_weight, goal.target_weight)
        entries.append({
            "username": u.username,
            "target_weight": goal.target_weight,
            "current_weight": current_weight,
            "progress": progress,
        })

    entries.sort(key=lambda e: e["progress"])
    users_with_goal = len(entries)
    avg_progress = round(sum(e["progress"] for e in entries) / users_with_goal, 1) if users_with_goal else None

    return {
        "total_users": total_users,
        "users_with_goal": users_with_goal,
        "avg_progress": avg_progress,
        "users": entries,
    }


@router.get("/reports/overview")
def reports_overview(session: Session = Depends(get_session), _: User = Depends(auth.require_admin)) -> dict:
    users = session.exec(select(User).where(User.is_active == True)).all()  # noqa: E712
    today = date_type.today()
    this_week_start = (today - timedelta(days=7)).isoformat()
    last_week_start = (today - timedelta(days=14)).isoformat()

    weight_changes: list[float] = []
    steps_this_week: list[float] = []
    improved = worsened = unchanged = 0

    for u in users:
        records = [r.model_dump() for r in storage.get_records_by_user_id(session, u.id)]
        this_week = [r for r in records if r["date"] >= this_week_start]
        last_week = [r for r in records if last_week_start <= r["date"] < this_week_start]
        this_week_avg = logic.calculate_averages(this_week)
        last_week_avg = logic.calculate_averages(last_week)

        if this_week_avg is not None:
            steps_this_week.append(this_week_avg["avg_steps"])

        if this_week_avg is not None and last_week_avg is not None:
            weight_changes.append(this_week_avg["avg_weight"] - last_week_avg["avg_weight"])
            trend = logic.classify_weight_trend(this_week_avg["avg_weight"], last_week_avg["avg_weight"])
            if trend == "improved":
                improved += 1
            elif trend == "worsened":
                worsened += 1
            else:
                unchanged += 1

    avg_weight_change = round(sum(weight_changes) / len(weight_changes), 1) if weight_changes else None
    avg_steps_this_week = round(sum(steps_this_week) / len(steps_this_week), 1) if steps_this_week else None

    return {
        "avg_weight_change": avg_weight_change,
        "avg_steps_this_week": avg_steps_this_week,
        "improved_users": improved,
        "worsened_users": worsened,
        "unchanged_users": unchanged,
    }


@router.get("/stats/timeseries")
def stats_timeseries(
    days: int = 14, session: Session = Depends(get_session), _: User = Depends(auth.require_admin)
) -> dict:
    today = date_type.today()
    dates = [(today - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
    return {
        "dates": dates,
        "cumulative_users": storage.get_cumulative_users_by_day(session, dates),
        "daily_new_records": storage.get_daily_record_counts(session, dates),
    }
