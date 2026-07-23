from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import auth
from .db import init_db
from .routers import auth as auth_router
from .routers import goal, records, reports

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth.ensure_secret_key_configured()
    init_db()
    yield


app = FastAPI(title="마이 헬스 로그 API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth_router.router)
app.include_router(records.router)
app.include_router(goal.router)
app.include_router(reports.router)


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api")
def api_status() -> dict[str, str]:
    return {"message": "마이 헬스 로그 API"}
