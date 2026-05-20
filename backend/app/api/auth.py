"""认证：注册 / 登录 / 登出 / me / 邮箱验证 / 密码找回。

cookie 模式：登录成功后 set HttpOnly cookie，前端 fetch 自动携带，无需手动放 token。

邮箱验证流程：
- 注册成功 → 自动登录，但 email_verified=False
- 发 6 位数字验证码到注册邮箱
- 用户在 /verify-email 输入验证码 → email_verified=True
- 未验证邮箱可看报告，BYOK 等需在 user_byok/qa 路由里再校验

密码找回流程：
- POST /forgot-password {email}：无论 email 存不存在都返回 200（防枚举），存在则发码
- POST /reset-password {email, code, new_password}：验证码通过 → 改 password_hash
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import (
    clear_session_cookie,
    create_token,
    current_user_optional,
    hash_password,
    require_user,
    set_session_cookie,
    verify_password,
)
from app.config import get_settings
from app.db.models import EmailCodeKind, User
from app.db.session import get_db
from app.notify import email_codes
from app.notify.email import send_reset_code, send_verify_code

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class VerifyEmailIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    email: str
    email_verified: bool


def _user_out(user: User) -> UserOut:
    return UserOut(email=user.email, email_verified=bool(user.email_verified))


def _result_to_msg(result: str) -> str:
    return {
        email_codes.CodeCheckResult.NOT_FOUND: "请先获取验证码",
        email_codes.CodeCheckResult.EXPIRED: "验证码已过期，请重新获取",
        email_codes.CodeCheckResult.TOO_MANY_ATTEMPTS: "尝试次数过多，请重新获取验证码",
        email_codes.CodeCheckResult.WRONG: "验证码错误",
    }.get(result, "验证码错误或已过期")


def _send_code_safe(kind: str, user: User, code: str) -> None:
    """发邮件失败时只记日志、不抛 —— 由调用方决定是否友好提示。"""
    settings = get_settings()
    ttl_min = max(1, settings.verify_code_ttl_seconds // 60)
    try:
        if kind == EmailCodeKind.VERIFY:
            send_verify_code(user.email, code, ttl_minutes=ttl_min)
        elif kind == EmailCodeKind.RESET:
            send_reset_code(user.email, code, ttl_minutes=ttl_min)
    except Exception as e:
        log.warning("邮件发送失败 kind=%s user_id=%s err=%s", kind, user.id, e)
        raise


# ── 注册 / 登录 / 登出 / me ────────────────────────────────────────────────────


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(400, "邮箱已注册")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 自动登录（即便邮箱未验证也允许登录，BYOK 等敏感操作后续单独校验）
    token = create_token(user.id)
    set_session_cookie(response, token)

    # 发验证码：失败不阻断注册，但前端 me 会显示未验证，用户可走重发
    try:
        code = email_codes.issue_code(db, user.id, EmailCodeKind.VERIFY)
        _send_code_safe(EmailCodeKind.VERIFY, user, code)
    except Exception:
        pass  # 已在 _send_code_safe 内 log

    return _user_out(user)


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    token = create_token(user.id)
    set_session_cookie(response, token)
    return _user_out(user)


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User | None = Depends(current_user_optional)):
    if not user:
        raise HTTPException(401, "未登录")
    return _user_out(user)


# ── 邮箱验证 ──────────────────────────────────────────────────────────────────


@router.post("/verify-email", response_model=UserOut)
def verify_email(
    payload: VerifyEmailIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if user.email_verified:
        return _user_out(user)
    result = email_codes.verify_and_consume(
        db, user.id, EmailCodeKind.VERIFY, payload.code
    )
    if result != email_codes.CodeCheckResult.OK:
        raise HTTPException(400, _result_to_msg(result))
    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("/resend-verify-code")
def resend_verify_code(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if user.email_verified:
        raise HTTPException(400, "邮箱已经验证过了")
    can, wait_seconds = email_codes.can_resend(db, user.id, EmailCodeKind.VERIFY)
    if not can:
        raise HTTPException(429, f"请等待 {wait_seconds} 秒后再试")
    code = email_codes.issue_code(db, user.id, EmailCodeKind.VERIFY)
    try:
        _send_code_safe(EmailCodeKind.VERIFY, user, code)
    except Exception as e:
        raise HTTPException(502, f"邮件发送失败：{e}")
    return {"ok": True}


# ── 密码找回 ──────────────────────────────────────────────────────────────────


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordIn, db: Session = Depends(get_db)):
    """无论 email 是否存在都返回 200 —— 防枚举。"""
    email = payload.email.lower().strip()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user:
        can, _ = email_codes.can_resend(db, user.id, EmailCodeKind.RESET)
        if can:
            code = email_codes.issue_code(db, user.id, EmailCodeKind.RESET)
            try:
                _send_code_safe(EmailCodeKind.RESET, user, code)
            except Exception:
                pass
    return {"ok": True}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        # 防枚举：和"验证码错误"返回同一种错误
        raise HTTPException(400, "验证码错误或已过期")
    result = email_codes.verify_and_consume(
        db, user.id, EmailCodeKind.RESET, payload.code
    )
    if result != email_codes.CodeCheckResult.OK:
        raise HTTPException(400, _result_to_msg(result))
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}
