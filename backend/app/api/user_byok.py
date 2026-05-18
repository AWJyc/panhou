"""用户 BYOK 配置：GET / PUT / DELETE。需登录。

api_key 写入时 Fernet 加密，读出时解密。GET 接口**永远不返回明文 key**，
只返回 has_key 标记 + 其他元数据，让前端能预填表单但不能看到原 key。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.crypto import encrypt_key
from app.auth.security import require_user
from app.db.models import User, UserBYOK
from app.db.session import get_db

router = APIRouter(prefix="/api/user/byok", tags=["user_byok"])

_ALLOWED_PROVIDERS = {
    "anthropic",
    "openai",
    "deepseek",
    "doubao",
    "qwen",
    "openai_compatible",
}


class BYOKIn(BaseModel):
    provider: str
    api_key: str = Field(min_length=4, max_length=512)
    model: str = Field(default="", max_length=128)
    base_url: str = Field(default="", max_length=255)


class BYOKOut(BaseModel):
    provider: str
    model: str
    base_url: str
    has_key: bool


@router.get("", response_model=BYOKOut | None)
def get_byok(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    cfg = db.execute(select(UserBYOK).where(UserBYOK.user_id == user.id)).scalar_one_or_none()
    if not cfg:
        return None
    return BYOKOut(
        provider=cfg.provider,
        model=cfg.model,
        base_url=cfg.base_url,
        has_key=bool(cfg.api_key_encrypted),
    )


@router.put("", response_model=BYOKOut)
def put_byok(
    payload: BYOKIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if payload.provider not in _ALLOWED_PROVIDERS:
        raise HTTPException(400, f"不支持的 provider: {payload.provider}")
    cipher = encrypt_key(payload.api_key)
    cfg = db.execute(select(UserBYOK).where(UserBYOK.user_id == user.id)).scalar_one_or_none()
    if cfg:
        cfg.provider = payload.provider
        cfg.api_key_encrypted = cipher
        cfg.model = payload.model
        cfg.base_url = payload.base_url
    else:
        cfg = UserBYOK(
            user_id=user.id,
            provider=payload.provider,
            api_key_encrypted=cipher,
            model=payload.model,
            base_url=payload.base_url,
        )
        db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return BYOKOut(provider=cfg.provider, model=cfg.model, base_url=cfg.base_url, has_key=True)


@router.delete("")
def delete_byok(user: User = Depends(require_user), db: Session = Depends(get_db)):
    cfg = db.execute(select(UserBYOK).where(UserBYOK.user_id == user.id)).scalar_one_or_none()
    if cfg:
        db.delete(cfg)
        db.commit()
    return {"ok": True}
