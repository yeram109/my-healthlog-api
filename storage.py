from typing import Any

from sqlmodel import Session, select

from models import Goal, Record


def get_records(session: Session, user: str) -> list[Record]:
    query = select(Record)
    if user != "admin":
        query = query.where(Record.user == user)
    return list(session.exec(query).all())


def search_records(session: Session, user: str, start: str | None, end: str | None) -> list[Record]:
    query = select(Record)
    if user != "admin":
        query = query.where(Record.user == user)
    if start is not None:
        query = query.where(Record.date >= start)
    if end is not None:
        query = query.where(Record.date <= end)
    return list(session.exec(query).all())


def get_record_by_id(session: Session, record_id: int) -> Record | None:
    return session.get(Record, record_id)


def add_record(session: Session, record: dict[str, Any], user: str) -> Record:
    db_record = Record(**record, user=user)
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


def check_ownership(record: Record, user: str) -> bool:
    return user == "admin" or record.user == user


def get_goal(session: Session, user: str) -> Goal | None:
    return session.get(Goal, user)


def set_goal(session: Session, user: str, goal: dict[str, Any]) -> Goal:
    db_goal = session.get(Goal, user)
    if db_goal is None:
        db_goal = Goal(user=user, **goal)
    else:
        for key, value in goal.items():
            setattr(db_goal, key, value)
    session.add(db_goal)
    session.commit()
    session.refresh(db_goal)
    return db_goal
