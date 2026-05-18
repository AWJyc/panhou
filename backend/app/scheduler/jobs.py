"""APScheduler registration. Stage 1 wires up A股; 美股 added in stage 3."""

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.pipeline.runner import run_pipeline_sync

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_cn_a() -> None:
    run_pipeline_sync("cn_a", date.today())


def _run_us() -> None:
    # 美股盘后任务在北京时间次日 06:00 触发，目标日期是 "昨天"（美东收盘日）
    run_pipeline_sync("us", date.today() - timedelta(days=1))


def _run_jp() -> None:
    # 东京 15:00 JST = 14:00 CST 收盘；14:30 CST 触发，目标日期就是今天
    run_pipeline_sync("jp", date.today())


def _run_kr() -> None:
    # 首尔 15:30 KST = 14:30 CST 收盘；15:00 CST 触发，目标日期就是今天
    run_pipeline_sync("kr", date.today())


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    sched = BackgroundScheduler(timezone=settings.scheduler_timezone)

    sched.add_job(
        _run_cn_a,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30),
        id="cn_a_daily",
        replace_existing=True,
    )
    sched.add_job(
        _run_jp,
        CronTrigger(day_of_week="mon-fri", hour=14, minute=30),
        id="jp_daily",
        replace_existing=True,
    )
    sched.add_job(
        _run_kr,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=0),
        id="kr_daily",
        replace_existing=True,
    )
    sched.add_job(
        _run_us,
        CronTrigger(day_of_week="tue-sat", hour=6, minute=0),
        id="us_daily",
        replace_existing=True,
    )

    sched.start()
    _scheduler = sched
    log.info(
        "scheduler started: jp@14:30, kr@15:00, cn_a@15:30 mon-fri, us@06:00 tue-sat (%s)",
        settings.scheduler_timezone,
    )
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
