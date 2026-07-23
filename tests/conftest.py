import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app import auth
from app.db import get_session
from app.main import app
from app.models import User


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(session: Session):
    def _make_headers(username: str, is_admin: bool = False, password: str = "testpass123") -> dict:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            user = User(username=username, hashed_password=auth.hash_password(password), is_admin=is_admin)
            session.add(user)
            session.commit()
            session.refresh(user)
        token = auth.create_access_token({"sub": username})
        return {"Authorization": f"Bearer {token}"}

    return _make_headers
