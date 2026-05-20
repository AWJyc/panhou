"""BYOK 对话接口：用户带自己的 key 与当日报告对话。

安全约束：
- 全程不记录、不持久化 api_key。
- 错误信息向客户端返回前对 api_key 做脱敏。
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.crypto import decrypt_key
from app.auth.security import current_user_optional
from app.byok.proxy import proxy_chat
from app.db.models import Market, Report, User, UserBYOK
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["byok"])
log = logging.getLogger(__name__)


class QAMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class QARequest(BaseModel):
    market: Literal["cn_a", "us"]
    # 登录用户可省略以下四项，让服务端读 DB 里加密的配置
    provider: str = ""
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    messages: list[QAMessage] = Field(min_length=1, max_length=20)


class QAResponse(BaseModel):
    answer: str
    model: str


def _redact(text: str, secret: str) -> str:
    if not secret or len(secret) < 6:
        return text
    return text.replace(secret, "[REDACTED]")


@router.post("/qa", response_model=QAResponse)
def qa(
    req: QARequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_optional),
) -> QAResponse:
    if req.market not in Market.ALL_MVP:
        raise HTTPException(status_code=400, detail=f"unsupported market: {req.market}")

    # 解析最终用哪份 BYOK 配置
    provider = req.provider
    api_key = req.api_key
    model = req.model
    base_url = req.base_url
    if user:
        # 登录但未验证邮箱 → 锁定 BYOK 问答（防止灌水/滥用）
        if not user.email_verified:
            raise HTTPException(403, "请先验证邮箱后再使用 AI 问答")
        # 登录用户：服务端读 DB 加密 key，忽略 body 里的 api_key（避免泄露给前端）
        cfg = db.execute(select(UserBYOK).where(UserBYOK.user_id == user.id)).scalar_one_or_none()
        if not cfg:
            raise HTTPException(400, "请先在设置页填入 AI 模型 key")
        try:
            api_key = decrypt_key(cfg.api_key_encrypted)
        except ValueError as e:
            log.error("byok decrypt failed for user %s: %s", user.id, e)
            raise HTTPException(500, "服务端 BYOK 解密失败，请联系管理员检查 BYOK_ENCRYPTION_KEY")
        provider = cfg.provider
        model = cfg.model
        base_url = cfg.base_url
    elif not api_key:
        raise HTTPException(401, "未登录用户请直接在请求体里带 api_key，或先登录")

    stmt = (
        select(Report)
        .where(Report.market == req.market)
        .options(selectinload(Report.sectors), selectinload(Report.movers))
        .order_by(Report.report_date.desc())
        .limit(1)
    )
    report = db.execute(stmt).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="该市场暂无报告")

    try:
        answer, model_id = proxy_chat(
            report=report,
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            messages=[m.model_dump() for m in req.messages],
        )
    except ValueError as e:
        # 入参/provider 校验失败
        raise HTTPException(status_code=400, detail=_redact(str(e), api_key)[:300])
    except Exception as e:
        # 上游 SDK 错误（认证、限流、模型不存在等）
        msg = _redact(str(e), api_key)[:500]
        log.warning("byok qa upstream err provider=%s: %s", provider, _redact(str(type(e).__name__), api_key))
        raise HTTPException(status_code=502, detail=f"上游模型错误: {msg}")

    return QAResponse(answer=answer, model=model_id)
