"""认证：注册 / 登录 / 登出 / me。

cookie 模式：登录成功后 set HttpOnly cookie，前端 fetch 自动携带，无需手动放 token。
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import (
    clear_session_cookie,
    create_token,
    current_user_optional,
    hash_password,
    set_session_cookie,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    email: str


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(400, "邮箱已注册")
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id)
    set_session_cookie(response, token)
    return UserOut(email=user.email)


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    token = create_token(user.id)
    set_session_cookie(response, token)
    return UserOut(email=user.email)


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User | None = Depends(current_user_optional)):
    if not user:
        raise HTTPException(401, "未登录")
    return UserOut(email=user.email)
