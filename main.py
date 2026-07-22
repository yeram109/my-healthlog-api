from contextlib import asynccontextmanager
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

import auth
import logic
import storage
from db import get_session, init_db
from models import GoalCreate, RecordCreate, RecordRead, User, UserCreate, UserRead

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

BMI_CATEGORIES = ["저체중", "정상", "과체중", "비만"]
BP_CATEGORIES = ["정상", "주의", "고혈압"]
SUGAR_CATEGORIES = ["정상", "공복혈당장애", "당뇨 의심"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth.ensure_secret_key_configured()
    init_db()
    yield


app = FastAPI(title="마이 헬스 로그 API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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


@app.post("/auth/signup", status_code=201, response_model=UserRead)
def signup(user: UserCreate, session: Session = Depends(get_session)) -> User:
    existing = session.exec(select(User).where(User.username == user.username)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자명입니다")
    db_user = User(username=user.username, hashed_password=auth.hash_password(user.password))
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.post("/auth/login")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
) -> dict:
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if user is None or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="아이디 또는 비밀번호가 올바르지 않습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="탈퇴한 계정입니다")
    access_token = auth.create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.delete("/auth/me")
def delete_account(
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    current_user.is_active = False
    session.add(current_user)
    session.commit()
    return {"message": "회원 탈퇴가 완료되었습니다"}


@app.post("/records", status_code=201, response_model=RecordRead)
def create_record(
    record: RecordCreate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    stored = storage.add_record(session, record.model_dump(), current_user)
    return logic.enrich_record(stored.model_dump())


@app.get("/records")
def list_records(
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    records = storage.get_records(session, current_user)
    enriched = [logic.enrich_record(r.model_dump()) for r in records]
    return {"count": len(enriched), "records": enriched}


@app.get("/records/{record_id}", response_model=RecordRead)
def get_record(
    record_id: int,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    record = storage.get_record_by_id(session, record_id)
    if record is None or not storage.check_ownership(record, current_user):
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    return logic.enrich_record(record.model_dump())


@app.put("/records/{record_id}", response_model=RecordRead)
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


@app.delete("/records/{record_id}")
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


@app.get("/search")
def search_records(
    start: str | None = None,
    end: str | None = None,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    _validate_date_param(start)
    _validate_date_param(end)
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start가 end보다 늦을 수 없습니다")

    records = storage.search_records(session, current_user, start, end)
    enriched = [logic.enrich_record(r.model_dump()) for r in records]
    return {"count": len(enriched), "records": enriched}


@app.get("/stats")
def get_stats(
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    records = [r.model_dump() for r in storage.get_records(session, current_user)]
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


@app.get("/goal")
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


@app.get("/reports/weekly")
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
        }

    return {
        "this_week": this_week_avg,
        "last_week": last_week_avg,
        "delta": delta,
    }
