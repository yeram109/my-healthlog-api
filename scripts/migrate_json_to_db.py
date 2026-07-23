import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session

from app.db import engine, init_db
from app.models import Goal, Record

DATA_FILE = Path(__file__).parent.parent / "data.json"


def migrate() -> None:
    if not DATA_FILE.exists():
        print("data.json이 없습니다. 이관할 데이터가 없습니다.")
        return

    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    init_db()
    records = data.get("records", [])
    goals = data.get("goals", {})

    with Session(engine) as session:
        for record in records:
            session.add(Record(**record))
        for user, goal in goals.items():
            session.add(Goal(user=user, **goal))
        session.commit()

    print(f"기록 {len(records)}건, 목표 {len(goals)}건 이관 완료 -> {engine.url}")


if __name__ == "__main__":
    migrate()
