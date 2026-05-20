"""轻量级 schema migration —— 启动时跑，幂等。

项目没用 alembic，create_all 能加新表但加不了新列。这里专门处理
existing-table-add-column + 必要的回填。每次只做一次，能反复运行。
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)


def _column_exists(conn, table: str, column: str) -> bool:
    insp = inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def run_migrations(engine: Engine) -> None:
    """启动时调用。所有迁移逻辑都要幂等。"""
    with engine.begin() as conn:
        _migrate_users_email_verified(conn)


def _migrate_users_email_verified(conn) -> None:
    """users 表加 email_verified + email_verified_at；老用户回填为已验证。"""
    if not _column_exists(conn, "users", "email_verified"):
        log.info("migrate: ALTER TABLE users ADD COLUMN email_verified")
        conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE users ADD COLUMN email_verified_at DATETIME NULL"))
        # 回填：本次升级之前已经存在的用户全部视为已验证（不打扰存量用户）
        result = conn.execute(
            text(
                "UPDATE users SET email_verified=1, email_verified_at=created_at "
                "WHERE email_verified=0"
            )
        )
        log.info("migrate: backfilled email_verified=1 for %s existing users", result.rowcount)
