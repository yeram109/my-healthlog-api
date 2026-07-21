from fastapi import Depends, FastAPI, Header, HTTPException

import logic
import storage
from models import RecordIn, RecordOut

app = FastAPI(title="마이 헬스 로그 API")


def get_current_user(x_user_id: str | None = Header(default=None)) -> str:
    return x_user_id or "guest"


@app.get("/api")
def api_status() -> dict[str, str]:
    return {"message": "마이 헬스 로그 API"}


@app.post("/records", status_code=201, response_model=RecordOut)
def create_record(record: RecordIn, user: str = Depends(get_current_user)) -> dict:
    stored = storage.add_record(record.model_dump(), user)
    return logic.enrich_record(stored)


@app.get("/records")
def list_records(user: str = Depends(get_current_user)) -> dict:
    records = storage.get_records(user)
    enriched = [logic.enrich_record(r) for r in records]
    return {"count": len(enriched), "records": enriched}


@app.get("/records/{record_id}", response_model=RecordOut)
def get_record(record_id: int, user: str = Depends(get_current_user)) -> dict:
    record = storage.get_record_by_id(record_id)
    if record is None or not storage.check_ownership(record, user):
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    return logic.enrich_record(record)


@app.put("/records/{record_id}", response_model=RecordOut)
def replace_record(record_id: int, record: RecordIn, user: str = Depends(get_current_user)) -> dict:
    existing = storage.get_record_by_id(record_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    if not storage.check_ownership(existing, user):
        raise HTTPException(status_code=403, detail="본인의 기록만 수정할 수 있습니다")
    updated = storage.update_record(record_id, record.model_dump())
    return logic.enrich_record(updated)


@app.delete("/records/{record_id}")
def delete_record(record_id: int, user: str = Depends(get_current_user)) -> dict:
    existing = storage.get_record_by_id(record_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    if not storage.check_ownership(existing, user):
        raise HTTPException(status_code=403, detail="본인의 기록만 삭제할 수 있습니다")
    storage.delete_record(record_id)
    return {"message": "삭제되었습니다", "deleted_id": record_id}
