from typing import Any

from sqlmodel import Session, select

from .models import Goal, Record, User


def _resolve_target_user_id(session: Session, target_user: str) -> int:
    target = session.exec(select(User).where(User.username == target_user)).first()
    return target.id if target is not None else -1


def get_records(session: Session, user: User, target_user: str | None = None) -> list[Record]:
    query = select(Record)
    if user.is_admin and target_user:
        query = query.where(Record.user_id == _resolve_target_user_id(session, target_user))
    elif not user.is_admin:
        query = query.where(Record.user_id == user.id)
    return list(session.exec(query).all())


def search_records(
    session: Session, user: User, start: str | None, end: str | None, target_user: str | None = None
) -> list[Record]:
    query = select(Record)
    if user.is_admin and target_user:
        query = query.where(Record.user_id == _resolve_target_user_id(session, target_user))
    elif not user.is_admin:
        query = query.where(Record.user_id == user.id)
    if start is not None:
        query = query.where(Record.date >= start)
    if end is not None:
        query = query.where(Record.date <= end)
    return list(session.exec(query).all())


def get_record_by_id(session: Session, record_id: int) -> Record | None:
    return session.get(Record, record_id)


def get_records_by_user_id(session: Session, user_id: int) -> list[Record]:
    return list(session.exec(select(Record).where(Record.user_id == user_id)).all())


def add_record(session: Session, record: dict[str, Any], user: User) -> Record:
    db_record = Record(**record, user_id=user.id)
    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    return db_record


def update_record(session: Session, record_id: int, record: dict[str, Any]) -> Record | None:
    db_record = session.get(Record, record_id)
    if db_record is None:
        return None
    for key, value in record.items():
        setattr(db_record, key, value)
    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    return db_record


def delete_record(session: Session, record_id: int) -> bool:
    db_record = session.get(Record, record_id)
    if db_record is None:
        return False
    session.delete(db_record)
    session.commit()
    return True


def check_ownership(record: Record, user: User) -> bool:
    return user.is_admin or record.user_id == user.id


def get_goal_by_user_id(session: Session, user_id: int) -> Goal | None:
    return session.get(Goal, user_id)


def get_goal(session: Session, user: User, target_user: str | None = None) -> Goal | None:
    if user.is_admin and target_user:
        target = session.exec(select(User).where(User.username == target_user)).first()
        if target is None:
            return None
        return session.get(Goal, target.id)
    return session.get(Goal, user.id)


def set_goal(session: Session, user: User, goal: dict[str, Any]) -> Goal:
    db_goal = session.get(Goal, user.id)
    if db_goal is None:
        db_goal = Goal(user_id=user.id, **goal)
    else:
        for key, value in goal.items():
            setattr(db_goal, key, value)
    session.add(db_goal)
    session.commit()
    session.refresh(db_goal)
    return db_goal


def get_cumulative_users_by_day(session: Session, dates: list[str]) -> list[int]:
    created_dates = sorted(u.created_at for u in session.exec(select(User).where(User.is_active == True)).all())  # noqa: E712
    return [sum(1 for c in created_dates if c <= d) for d in dates]


def get_daily_record_counts(session: Session, dates: list[str]) -> list[int]:
    active_user_ids = {u.id for u in session.exec(select(User).where(User.is_active == True)).all()}  # noqa: E712
    counts: dict[str, int] = {}
    for r in session.exec(select(Record)).all():
        if r.user_id in active_user_ids:
            counts[r.date] = counts.get(r.date, 0) + 1
    return [counts.get(d, 0) for d in dates]
