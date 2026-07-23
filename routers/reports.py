from datetime import date as date_type
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session

import auth
import logic
import storage
from db import get_session
from models import User

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/weekly")
def get_weekly_report(
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    records = [r.model_dump() for r in storage.get_records(session, current_user)]
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
            "steps": round(this_week_avg["avg_steps"] - last_week_avg["avg_steps"], 1),
            "sleep_hours": round(this_week_avg["avg_sleep_hours"] - last_week_avg["avg_sleep_hours"], 1),
        }

    return {
        "this_week": this_week_avg,
        "last_week": last_week_avg,
        "delta": delta,
    }
