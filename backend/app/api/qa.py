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

from app.byok.proxy import proxy_chat
from app.db.models import Market, Report
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["byok"])
log = logging.getLogger(__name__)


class QAMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class QARequest(BaseModel):
    market: Literal["cn_a", "us"]
    provider: str
    api_key: str = Field(min_length=8, max_length=512)
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
def qa(req: QARequest, db: Session = Depends(get_db)) -> QAResponse:
    if req.market not in Market.ALL_MVP:
        raise HTTPException(status_code=400, detail=f"unsupported market: {req.market}")

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
            provider=req.provider,
            api_key=req.api_key,
            model=req.model,
            base_url=req.base_url,
            messages=[m.model_dump() for m in req.messages],
        )
    except ValueError as e:
        # 入参/provider 校验失败
        raise HTTPException(status_code=400, detail=_redact(str(e), req.api_key)[:300])
    except Exception as e:
        # 上游 SDK 错误（认证、限流、模型不存在等）
        msg = _redact(str(e), req.api_key)[:500]
        log.warning("byok qa upstream err provider=%s: %s", req.provider, _redact(str(type(e).__name__), req.api_key))
        raise HTTPException(status_code=502, detail=f"上游模型错误: {msg}")

    return QAResponse(answer=answer, model=model_id)
