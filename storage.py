import json
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).parent / "data.json"


def _empty_data() -> dict[str, Any]:
    return {"next_id": 1, "records": []}


def load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return _empty_data()
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict[str, Any]) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_records(user: str) -> list[dict[str, Any]]:
    data = load_data()
    if user == "admin":
        return data["records"]
    return [r for r in data["records"] if r["user"] == user]


def get_record_by_id(record_id: int) -> dict[str, Any] | None:
    data = load_data()
    for r in data["records"]:
        if r["id"] == record_id:
            return r
    return None


def add_record(record: dict[str, Any], user: str) -> dict[str, Any]:
    data = load_data()
    new_record = {"id": data["next_id"], "user": user, **record}
    data["records"].append(new_record)
    data["next_id"] += 1
    save_data(data)
    return new_record


def update_record(record_id: int, record: dict[str, Any]) -> dict[str, Any] | None:
    data = load_data()
    for i, r in enumerate(data["records"]):
        if r["id"] == record_id:
            updated = {"id": r["id"], "user": r["user"], **record}
            data["records"][i] = updated
            save_data(data)
            return updated
    return None


def delete_record(record_id: int) -> bool:
    data = load_data()
    for i, r in enumerate(data["records"]):
        if r["id"] == record_id:
            data["records"].pop(i)
            save_data(data)
            return True
    return False


def check_ownership(record: dict[str, Any], user: str) -> bool:
    return user == "admin" or record["user"] == user
