"""密码哈希 + JWT 签发 / 解析。"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import User
from app.db.session import get_db

COOKIE_NAME = "tradeagent_session"
JWT_ALG = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.auth_token_ttl_days)).timestamp()),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.auth_secret, algorithms=[JWT_ALG])


def _user_from_cookie(request: Request, db: Session) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub") or 0)
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
    if user_id <= 0:
        return None
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def get_current_user_optional(
    request: Request,
    db: Session = None,  # 由依赖填充
) -> User | None:
    """未登录返回 None。"""
    # 让 FastAPI 注入 db
    from fastapi import Depends

    raise RuntimeError("use get_current_user_optional with Depends; see deps.py")


# 实际 FastAPI 依赖（避免与 typing 默认值冲突）
def make_current_user_optional():
    from fastapi import Depends

    def _dep(request: Request, db: Session = Depends(get_db)) -> User | None:
        return _user_from_cookie(request, db)

    return _dep


def make_require_user():
    from fastapi import Depends

    def _dep(request: Request, db: Session = Depends(get_db)) -> User:
        user = _user_from_cookie(request, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    return _dep


# 暴露给路由用的两个依赖实例
current_user_optional = make_current_user_optional()
require_user = make_require_user()


def set_session_cookie(response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.auth_token_ttl_days * 24 * 3600,
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")
