"""历史报告保留策略：每个市场只保留最近 N 个交易日(report_date)的报告。

为什么按「最近 N 个 report_date」而不是「日历 N 天」：各市场交易日历不同，且
某市场可能几天没出报告（节假日 / 任务失败）。按日历窗口会把这种市场整张表删空，
首页卡片直接崩。按「最近 N 个 report_date」保证每个市场永远留住最新 N 份、不删空。

删除走 ORM（Report 上 cascade="all, delete-orphan" 会带走 market_sectors /
market_movers）。N 来自 settings.report_retention_days。
"""

import logging

from sqlalchemy import select

from app.db.models import Market, Report
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


def prune_market_history(market: str, keep: int) -> int:
    """删除 market 中早于「最近 keep 个 report_date」的报告，返回删除条数。

    market 报告数 <= keep 时不删（还没攒够）。
    """
    if keep < 1:
        return 0
    with SessionLocal() as db:
        recent_dates = (
            db.execute(
                select(Report.report_date)
                .where(Report.market == market)
                .order_by(Report.report_date.desc())
                .limit(keep)
            )
            .scalars()
            .all()
        )
        if len(recent_dates) < keep:
            return 0
        cutoff = recent_dates[-1]  # 第 keep 新的交易日
        old = (
            db.execute(
                select(Report).where(
                    Report.market == market, Report.report_date < cutoff
                )
            )
            .scalars()
            .all()
        )
        n = len(old)
        if not n:
            return 0
        for r in old:
            db.delete(r)  # cascade 删 sectors / movers
        db.commit()
        log.info(
            "retention: market=%s 删除 %d 份早于 %s 的报告（保留最近 %d 天）",
            market,
            n,
            cutoff,
            keep,
        )
        return n


def prune_all_history(keep: int) -> int:
    """对所有 MVP 市场做一次裁剪，返回总删除条数。"""
    total = 0
    for m in Market.ALL_MVP:
        try:
            total += prune_market_history(m, keep)
        except Exception as e:
            log.warning("retention prune market=%s 失败: %s", m, e)
    return total
