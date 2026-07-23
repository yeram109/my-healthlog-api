from datetime import date as date_type

from fastapi import APIRouter, Depends
from sqlmodel import Session

from .. import auth, logic, storage
from ..db import get_session
from ..models import GoalCreate, User

router = APIRouter(prefix="/goal", tags=["goal"])


@router.put("")
def set_goal(
    goal: GoalCreate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    stored_goal = {
        "target_weight": goal.target_weight,
        "target_systolic": goal.target_systolic,
        "target_diastolic": goal.target_diastolic,
        "set_date": date_type.today().isoformat(),
    }
    db_goal = storage.set_goal(session, current_user, stored_goal)
    return {"goal": db_goal.model_dump()}


@router.get("")
def get_goal(
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    goal = storage.get_goal(session, current_user)
    if goal is None:
        return {"goal": None}
    records = [r.model_dump() for r in storage.get_records(session, current_user)]
    goal_dict = goal.model_dump()
    achievement = logic.calculate_goal_achievement(goal_dict, records)
    return {"goal": goal_dict, "achievement": achievement}
