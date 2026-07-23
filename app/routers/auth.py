from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from .. import auth
from ..db import get_session
from ..models import User, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=UserRead)
def signup(user: UserCreate, session: Session = Depends(get_session)) -> User:
    existing = session.exec(select(User).where(User.username == user.username)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자명입니다")
    db_user = User(username=user.username, hashed_password=auth.hash_password(user.password))
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.post("/login")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
) -> dict:
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if user is None or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="아이디 또는 비밀번호가 올바르지 않습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="탈퇴한 계정입니다")
    access_token = auth.create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.delete("/me")
def delete_account(
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    current_user.is_active = False
    session.add(current_user)
    session.commit()
    return {"message": "회원 탈퇴가 완료되었습니다"}
