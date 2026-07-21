from fastapi import Depends, FastAPI, Header, HTTPException

import storage
from models import RecordIn

app = FastAPI(title="마이 헬스 로그 API")


def get_current_user(x_user_id: str | None = Header(default=None)) -> str:
    return x_user_id or "guest"


@app.get("/api")
def api_status() -> dict[str, str]:
    return {"message": "마이 헬스 로그 API"}


@app.post("/records", status_code=201)
def create_record(record: RecordIn, user: str = Depends(get_current_user)) -> dict:
    return storage.add_record(record.model_dump(), user)


@app.get("/records")
def list_records(user: str = Depends(get_current_user)) -> dict:
    records = storage.get_records(user)
    return {"count": len(records), "records": records}


@app.get("/records/{record_id}")
def get_record(record_id: int, user: str = Depends(get_current_user)) -> dict:
    record = storage.get_record_by_id(record_id)
    if record is None or not storage.check_ownership(record, user):
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    return record
