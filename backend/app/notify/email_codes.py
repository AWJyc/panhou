"""注册激活 + 密码重置的 6 位数字验证码业务逻辑。

设计：
- 生成时存 bcrypt(code)，明文 code 仅用于当次邮件
- 同一 user+kind 同时只保留一个 active code（新建即作废旧的）
- expires_at 控时间窗，attempts 控错误次数（达上限即作废）
- 重发冷却 verify_code_resend_cooldown_seconds 秒
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import EmailCode, EmailCodeKind

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def _check_code(code: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _generate_code() -> str:
    """6 位数字，10^6 = 1M 空间。靠 attempts 上限防爆破。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def _strip_tz(dt: datetime | None) -> datetime | None:
    """SQLite 不存 tz，比较前剥 tz 信息。"""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def latest_active(db: Session, user_id: int, kind: str) -> EmailCode | None:
    return (
        db.execute(
            select(EmailCode)
            .where(EmailCode.user_id == user_id, EmailCode.kind == kind, EmailCode.used_at.is_(None))
            .order_by(EmailCode.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def can_resend(db: Session, user_id: int, kind: str) -> tuple[bool, int]:
    """返回 (能否重发, 还需等待秒数)。"""
    settings = get_settings()
    last = latest_active(db, user_id, kind)
    if not last:
        return True, 0
    elapsed = (_utcnow().replace(tzinfo=None) - _strip_tz(last.created_at)).total_seconds()
    cooldown = settings.verify_code_resend_cooldown_seconds
    if elapsed >= cooldown:
        return True, 0
    return False, int(cooldown - elapsed) + 1


def issue_code(db: Session, user_id: int, kind: str) -> str:
    """生成新验证码，作废旧的，返回明文 code（仅用于即发邮件，不要落日志）。"""
    if kind not in EmailCodeKind.ALL:
        raise ValueError(f"未知 kind: {kind}")
    settings = get_settings()
    # 作废同 user+kind 的旧 active code（标 used_at 当前时间，等同 invalidated）
    old = latest_active(db, user_id, kind)
    if old and old.used_at is None:
        old.used_at = _utcnow()
    code = _generate_code()
    row = EmailCode(
        user_id=user_id,
        kind=kind,
        code_hash=_hash_code(code),
        expires_at=_utcnow() + timedelta(seconds=settings.verify_code_ttl_seconds),
        attempts=0,
    )
    db.add(row)
    db.commit()
    return code


class CodeCheckResult:
    OK = "ok"
    NOT_FOUND = "not_found"  # 没生成过/已用
    EXPIRED = "expired"
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    WRONG = "wrong"


def verify_and_consume(db: Session, user_id: int, kind: str, code: str) -> str:
    """校验并消费验证码。成功后标记 used_at。返回 CodeCheckResult 字符串。"""
    settings = get_settings()
    row = latest_active(db, user_id, kind)
    if not row:
        return CodeCheckResult.NOT_FOUND
    now = _utcnow().replace(tzinfo=None)
    if _strip_tz(row.expires_at) <= now:
        return CodeCheckResult.EXPIRED
    if row.attempts >= settings.verify_code_max_attempts:
        return CodeCheckResult.TOO_MANY_ATTEMPTS
    if not _check_code(code, row.code_hash):
        row.attempts += 1
        db.commit()
        # 这次失败后是否就达到上限了，告诉前端
        if row.attempts >= settings.verify_code_max_attempts:
            return CodeCheckResult.TOO_MANY_ATTEMPTS
        return CodeCheckResult.WRONG
    row.used_at = _utcnow()
    db.commit()
    return CodeCheckResult.OK
