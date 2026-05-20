"""Pipeline 完成通知。读 db 拿最终 status 和统计，发到飞书群。

调用方只传 (market, report_date, report_id, elapsed_sec)。
notify 本身的失败必须吞掉 + log，绝不影响 pipeline。
"""

import logging
from datetime import date

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import MarketMover, MarketSector, Report
from app.db.session import SessionLocal
from app.notify.feishu import send_card

log = logging.getLogger(__name__)

MARKET_LABEL = {
    "cn_a": "A 股",
    "us": "美股",
    "jp": "日股",
    "kr": "韩股",
}


def notify_pipeline_done(
    market: str,
    report_date: date,
    report_id: int,
    *,
    elapsed_sec: float,
    forced_status: str | None = None,
    error: str | None = None,
) -> None:
    """Pipeline 跑完后调用。读 db 拿状态，组装卡片发飞书。

    forced_status: 调用方明确传 'failed'（例如外层 except）时跳过 db 读取
    error: 异常时的人类可读错误（一行）
    """
    settings = get_settings()
    if not settings.notify_enabled:
        return
    webhook = settings.feishu_webhook_url
    if not webhook:
        log.debug("FEISHU_WEBHOOK_URL 未配置，跳过 notify")
        return

    try:
        status, sectors_n, movers_n, summary_head = _load_report_meta(report_id)
    except Exception as e:
        log.warning("notify: 读 db 失败 (%s)，按 forced_status 走", e)
        status, sectors_n, movers_n, summary_head = (
            forced_status or "failed",
            0,
            0,
            "",
        )

    if forced_status:
        status = forced_status

    is_failed = status != "ok"

    if settings.notify_level == "failure" and not is_failed:
        return

    label = MARKET_LABEL.get(market, market)
    title = ("❌" if is_failed else "✅") + f" {label} {report_date} "
    title += "失败" if is_failed else "完成"
    color = "red" if is_failed else "green"

    lines = [
        f"**市场**：{label}（`{market}`）",
        f"**报告日期**：{report_date}",
        f"**报告 ID**：`{report_id}`",
        f"**耗时**：{elapsed_sec:.1f}s",
        f"**状态**：{'失败' if is_failed else '成功'}",
    ]
    if not is_failed:
        lines.append(f"**Sectors / Movers**：{sectors_n} / {movers_n}")
        if summary_head:
            lines.append(f"**摘要**：{summary_head}")
    else:
        if error:
            lines.append(f"**错误**：`{_truncate(error, 200)}`")
        elif summary_head:
            lines.append(f"**原因**：{summary_head}")

    try:
        send_card(
            webhook,
            title=title,
            content_lines=lines,
            color=color,
            secret=settings.feishu_webhook_secret or None,
        )
        log.info("notify ok market=%s date=%s status=%s", market, report_date, status)
    except Exception as e:
        log.warning("notify 发送失败 (非致命) market=%s date=%s: %s", market, report_date, e)


def _load_report_meta(report_id: int) -> tuple[str, int, int, str]:
    """返回 (status, sectors_count, movers_count, summary_head 前 80 字)。"""
    with SessionLocal() as db:
        report = db.get(Report, report_id)
        if report is None:
            return "failed", 0, 0, ""
        sectors_n = db.execute(
            select(func.count(MarketSector.id)).where(MarketSector.report_id == report_id)
        ).scalar_one()
        movers_n = db.execute(
            select(func.count(MarketMover.id)).where(MarketMover.report_id == report_id)
        ).scalar_one()
        head = _truncate((report.summary_md or "").strip().replace("\n", " "), 80)
        return report.status, sectors_n, movers_n, head


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"
