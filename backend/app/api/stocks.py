"""单股分时数据 / sparkline。

A 股分钟级 intraday：当日 9:30-15:00（240+ 个 1 分钟 bar）。
带内存缓存（同 symbol+date 一天内只打一次 akshare）。
"""

import asyncio
import logging
from datetime import date as date_cls, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.pipeline._akshare_pool import run_akshare

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

log = logging.getLogger(__name__)

_cache: dict[tuple, dict[str, Any]] = {}
_lock = asyncio.Lock()


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:
            return None
        return f
    except (ValueError, TypeError):
        return None


def _cn_a_sina_prefix(symbol: str) -> str:
    if symbol.startswith("6"):
        return "sh" + symbol
    if symbol.startswith(("0", "3")):
        return "sz" + symbol
    if symbol.startswith(("4", "8", "9")):
        return "bj" + symbol
    return "sh" + symbol


def _fetch_cn_a_intraday(symbol: str, target_date: str) -> dict | None:
    """A 股分钟级 intraday。target_date='2026-05-13'。

    优先 EM hist_min（指定日期），失败时 sina minute（只能拿最近一日）。
    返回 {points: [{t, close, volume}], prev_close}
    """
    import akshare as ak

    start = f"{target_date} 09:00:00"
    end = f"{target_date} 15:30:00"

    # EM 主路：指定日期
    try:
        df = ak.stock_zh_a_hist_min_em(
            symbol=symbol, start_date=start, end_date=end, period="1", adjust=""
        )
        if df is not None and not df.empty:
            return _parse_em_intraday(df, target_date)
    except Exception as e:
        log.warning("EM intraday %s 失败: %s", symbol, e)

    # sina 兜底：只拿最近日（如果 target_date 不是最近日，可能不准）
    try:
        sina_sym = _cn_a_sina_prefix(symbol)
        df = ak.stock_zh_a_minute(symbol=sina_sym, period="1", adjust="")
        if df is not None and not df.empty:
            return _parse_sina_intraday(df, target_date)
    except Exception as e:
        log.warning("sina minute %s 失败: %s", symbol, e)

    return None


def _parse_em_intraday(df, target_date: str) -> dict:
    """EM columns: 时间, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 均价"""
    records = df.to_dict(orient="records")
    points: list[dict] = []
    closes: list[float] = []
    for r in records:
        ts = str(r.get("时间") or "")
        if target_date and not ts.startswith(target_date):
            continue
        close = _to_float(r.get("收盘"))
        if close is None:
            continue
        # 截 HH:MM
        t_short = ts[11:16] if len(ts) >= 16 else ts
        points.append(
            {
                "t": t_short,
                "close": close,
                "volume": _to_float(r.get("成交量")),
            }
        )
        closes.append(close)
    # 前收：假设涨停 ≈ +10%，从第一根估算（仅作参考线）
    first_close = closes[0] if closes else None
    prev_close = round(first_close / 1.10, 4) if first_close else None
    return {"points": points, "prev_close": prev_close}


def _parse_sina_intraday(df, target_date: str) -> dict:
    """sina columns: day(YYYY-MM-DD HH:MM:SS), open, high, low, close, volume"""
    records = df.to_dict(orient="records")
    points: list[dict] = []
    closes: list[float] = []
    for r in records:
        ts = str(r.get("day") or "")
        if target_date and not ts.startswith(target_date):
            continue
        close = _to_float(r.get("close"))
        if close is None:
            continue
        t_short = ts[11:16] if len(ts) >= 16 else ts
        points.append(
            {
                "t": t_short,
                "close": close,
                "volume": _to_float(r.get("volume")),
            }
        )
        closes.append(close)
    first_close = closes[0] if closes else None
    prev_close = round(first_close / 1.10, 4) if first_close else None
    return {"points": points, "prev_close": prev_close}


@router.get("/sparkline")
async def get_sparkline(
    market: str = Query(...),
    symbol: str = Query(..., min_length=1, max_length=16),
    date: str | None = Query(default=None, description="YYYY-MM-DD, 默认今天"),
):
    """A 股当日分钟级分时线。返回 {symbol, date, points:[{t,close,volume}], prev_close}。"""
    if market != "cn_a":
        raise HTTPException(400, "only cn_a is supported for intraday sparkline")
    if not symbol.isalnum():
        raise HTTPException(400, "invalid symbol")

    target = date or date_cls.today().isoformat()
    try:
        date_cls.fromisoformat(target)
    except ValueError:
        raise HTTPException(400, "invalid date format, expect YYYY-MM-DD")

    cache_key = (market, symbol, target)
    async with _lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    data = await run_akshare(_fetch_cn_a_intraday, symbol, target)
    if data is None:
        out = {
            "symbol": symbol,
            "date": target,
            "points": [],
            "prev_close": None,
            "error": "fetch_failed",
        }
    else:
        out = {
            "symbol": symbol,
            "date": target,
            "points": data["points"],
            "prev_close": data["prev_close"],
        }

    async with _lock:
        _cache[cache_key] = out
    return out
