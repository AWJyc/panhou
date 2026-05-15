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
        _run_us,
        CronTrigger(day_of_week="tue-sat", hour=6, minute=0),
        id="us_daily",
        replace_existing=True,
    )

    sched.start()
    _scheduler = sched
    log.info("scheduler started: cn_a@15:30 mon-fri, us@06:00 tue-sat (%s)", settings.scheduler_timezone)
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
