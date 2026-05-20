from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Market:
    """Enumerated market codes. Kept as plain strings for SQLite portability."""

    CN_A = "cn_a"
    US = "us"
    # Reserved for v2:
    JP = "jp"
    KR = "kr"

    ALL_MVP = (CN_A, US, JP, KR)


class MoveType:
    LIMIT_UP = "limit_up"
    LIMIT_DOWN = "limit_down"
    TOP_GAINER = "top_gainer"
    TOP_LOSER = "top_loser"


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("market", "report_date", name="uq_reports_market_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    summary_md: Mapped[str] = mapped_column(String, default="")
    raw_sources: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    indices: Mapped[list | None] = mapped_column(JSON, nullable=True)
    themes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    model_used: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok | failed

    sectors: Mapped[list["MarketSector"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    movers: Mapped[list["MarketMover"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class MarketSector(Base):
    __tablename__ = "market_sectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String, default="")

    report: Mapped[Report] = relationship(back_populates="sectors")


class MarketMover(Base):
    __tablename__ = "market_movers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), default="")
    name: Mapped[str] = mapped_column(String(64))
    move_type: Mapped[str] = mapped_column(String(16))
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String, default="")
    # A 股专属
    limit_up_streak: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 连板数；首板=1
    concept: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 所属行业/题材
    sealing_amount: Mapped[float | None] = mapped_column(Float, nullable=True)  # 封单金额（亿元）

    report: Mapped[Report] = relationship(back_populates="movers")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    byok: Mapped["UserBYOK | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    email_codes: Mapped[list["EmailCode"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class EmailCodeKind:
    VERIFY = "verify"
    RESET = "reset"
    ALL = (VERIFY, RESET)


class EmailCode(Base):
    """注册激活 + 密码重置用的 6 位数字验证码。

    存 code_hash（bcrypt）而非明文，防 DB dump 后直接回放。
    每条 code 有 expires_at + attempts 上限，超过即作废。
    """

    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="email_codes")


class UserBYOK(Base):
    """用户保存的 BYOK 配置。api_key 字段是 Fernet 密文，不是明文。"""

    __tablename__ = "user_byok"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    api_key_encrypted: Mapped[str] = mapped_column(String)  # Fernet 密文
    model: Mapped[str] = mapped_column(String(128), default="")
    base_url: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    user: Mapped[User] = relationship(back_populates="byok")
