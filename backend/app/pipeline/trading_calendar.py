"""判断某市场某日是否为交易日。

- A 股：chinese_calendar.is_workday()（包含国务院调休规则，最准）
- 美/日/韩：holidays 库 + 周末判断
- 任何库错误时降级：周一到周五视为交易日（保守不漏报）
"""

import logging
from datetime import date
from functools import lru_cache

log = logging.getLogger(__name__)


def is_trading_day(market: str, d: date) -> bool:
    if d.weekday() >= 5:  # 周六/周日全部 false（chinese_calendar 也会处理调休补班）
        if market == "cn_a":
            return _cn_a_is_workday(d)
        return False

    if market == "cn_a":
        return _cn_a_is_workday(d)
    if market == "us":
        return d not in _us_holidays(d.year)
    if market == "jp":
        return d not in _jp_holidays(d.year)
    if market == "kr":
        return d not in _kr_holidays(d.year)
    # 未知 market：保守判断为交易日，让 pipeline 自己决定
    return True


def _cn_a_is_workday(d: date) -> bool:
    try:
        import chinese_calendar as cc

        return bool(cc.is_workday(d))
    except Exception as e:
        log.warning("chinese_calendar 判断失败，降级为周一-周五: %s", e)
        return d.weekday() < 5


@lru_cache(maxsize=8)
def _us_holidays(year: int):
    try:
        import holidays

        return holidays.US(years=[year])
    except Exception as e:
        log.warning("holidays.US 加载失败: %s", e)
        return set()


@lru_cache(maxsize=8)
def _jp_holidays(year: int):
    try:
        import holidays

        # 日本年末年始 12/31-1/3 东京交易所休市，不全是法定节假日；手动补
        base = holidays.JP(years=[year])
        for m, dd in [(12, 31), (1, 2), (1, 3)]:
            try:
                base.append({date(year, m, dd): "TSE year-end/year-start"})
            except Exception:
                pass
        return base
    except Exception as e:
        log.warning("holidays.JP 加载失败: %s", e)
        return set()


@lru_cache(maxsize=8)
def _kr_holidays(year: int):
    try:
        import holidays

        return holidays.KR(years=[year])
    except Exception as e:
        log.warning("holidays.KR 加载失败: %s", e)
        return set()
