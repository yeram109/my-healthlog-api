import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from db import get_session
from models import User

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="인증 정보가 유효하지 않습니다",
    headers={"WWW-Authenticate": "Bearer"},
)


def _secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if not key:
        raise RuntimeError("SECRET_KEY 환경변수를 설정하세요 (.env.example 참고)")
    return key


def ensure_secret_key_configured() -> None:
    _secret_key()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    except JWTError:
        raise CREDENTIALS_EXCEPTION
    username = payload.get("sub")
    if username is None:
        raise CREDENTIALS_EXCEPTION
    return username


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(get_session),
) -> User:
    username = decode_access_token(token)
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not user.is_active:
        raise CREDENTIALS_EXCEPTION
    return user
