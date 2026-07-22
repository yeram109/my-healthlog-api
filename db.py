from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

DB_FILE = Path(__file__).parent / "health_log.db"
engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
