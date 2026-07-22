import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select

import auth
from db import engine, init_db
from models import User


def create_admin(username: str, password: str) -> None:
    init_db()
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.username == username)).first()
        if existing is not None:
            print(f"이미 존재하는 사용자입니다: {username}")
            return
        admin = User(username=username, hashed_password=auth.hash_password(password), is_admin=True)
        session.add(admin)
        session.commit()
        print(f"관리자 계정 생성 완료: {username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="관리자 계정 생성")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    create_admin(args.username, args.password)


if __name__ == "__main__":
    main()
