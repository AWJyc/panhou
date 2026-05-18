"""日股 / 韩股结构化数据：主要指数（无个股 movers 数据源）。

走 akshare.index_global_spot_em（东方财富全球指数），一次请求拿全部全球指数，
按 code 过滤出 jp/kr 的核心指数。
"""

import logging
import time
from typing import Any

from app.pipeline._akshare_pool import run_akshare

log = logging.getLogger(__name__)


# (em_code, display_name) — 顺序就是 UI 上呈现的顺序
JP_INDEX_CODES: list[tuple[str, str]] = [
    ("N225", "日经 225"),
    ("TOPIX", "TOPIX"),
    ("JPXN", "JPX-Nikkei 400"),
]

KR_INDEX_CODES: list[tuple[str, str]] = [
    ("KS11", "KOSPI"),
    ("KOSPI200", "KOSPI 200"),
    ("KOSDAQ", "KOSDAQ"),
]


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


def _fetch_global_indices_em(want_codes: list[tuple[str, str]], attempts: int = 3) -> list[dict] | None:
    """EM 全球指数 spot。失败重试 N 次。"""
    import akshare as ak

    for i in range(attempts):
        try:
            df = ak.index_global_spot_em()
        except Exception as e:
            log.warning("index_global_spot_em attempt %d/%d failed: %s", i + 1, attempts, e)
            if i + 1 < attempts:
                time.sleep(1.0 * (i + 1))
            continue
        if df is None or df.empty:
            continue
        df.columns = ["idx", "code", "name", "price", "chg", "pct", "open", "high", "low", "prev", "amp", "ts"]
        out: list[dict] = []
        for code, label in want_codes:
            row = df[df["code"] == code]
            if row.empty:
                continue
            r = row.iloc[0]
            price = _to_float(r["price"])
            pct = _to_float(r["pct"])
            if price is None:
                continue
            out.append(
                {
                    "symbol": code,
                    "name": label,
                    "close": price,
                    "change_pct": pct,
                    "date": str(r.get("ts", ""))[:10],
                }
            )
        return out
    return None


# ── 兜底：yahoo finance public API（境外节点直连，国内可能需代理）────────
_YF_SYM = {
    "N225": ("^N225", "日经 225"),
    "TOPIX": ("^TPX", "TOPIX"),
    "JPXN": ("^JPXNK400", "JPX-Nikkei 400"),
    "KS11": ("^KS11", "KOSPI"),
    "KOSPI200": ("^KS200", "KOSPI 200"),
    "KOSDAQ": ("^KQ11", "KOSDAQ"),
}


def _fetch_indices_yahoo(want_codes: list[tuple[str, str]]) -> list[dict]:
    """yahoo finance chart API，拿最近 5 天日线算涨跌幅。"""
    import requests

    out: list[dict] = []
    for em_code, label in want_codes:
        yf_sym, fallback_label = _YF_SYM.get(em_code, (None, None))
        if not yf_sym:
            continue
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}"
        params = {"interval": "1d", "range": "5d"}
        try:
            r = requests.get(
                url,
                params=params,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning("yahoo %s 失败: %s", yf_sym, e)
            continue
        try:
            res = data["chart"]["result"][0]
            ts = res["timestamp"]
            closes = res["indicators"]["quote"][0]["close"]
            # 去掉 None
            pairs = [(t, c) for t, c in zip(ts, closes) if c is not None]
            if len(pairs) < 2:
                continue
            from datetime import datetime, timezone

            last_t, last_close = pairs[-1]
            prev_close = pairs[-2][1]
            change_pct = (last_close - prev_close) / prev_close * 100 if prev_close else None
            iso = datetime.fromtimestamp(last_t, tz=timezone.utc).date().isoformat()
            out.append(
                {
                    "symbol": em_code,
                    "name": label or fallback_label,
                    "close": float(last_close),
                    "change_pct": change_pct,
                    "date": iso,
                }
            )
        except (KeyError, IndexError, TypeError) as e:
            log.warning("yahoo %s parse 失败: %s", yf_sym, e)
            continue
    return out


def _fetch_indices_sina_yfinance(want_codes: list[tuple[str, str]]) -> list[dict]:
    """对外保持函数名兼容；改走 yahoo finance。"""
    return _fetch_indices_yahoo(want_codes)


async def fetch_jp_indices() -> list[dict]:
    res = await run_akshare(_fetch_global_indices_em, JP_INDEX_CODES)
    if res:
        return res
    log.warning("EM 全球指数挂，jp 切 sina 兜底")
    try:
        res = await run_akshare(_fetch_indices_sina_yfinance, JP_INDEX_CODES)
        return res or []
    except Exception as e:
        log.warning("sina jp 兜底失败: %s", e)
        return []


async def fetch_kr_indices() -> list[dict]:
    res = await run_akshare(_fetch_global_indices_em, KR_INDEX_CODES)
    if res:
        return res
    log.warning("EM 全球指数挂，kr 切 sina 兜底")
    try:
        res = await run_akshare(_fetch_indices_sina_yfinance, KR_INDEX_CODES)
        return res or []
    except Exception as e:
        log.warning("sina kr 兜底失败: %s", e)
        return []


def summarize_idx_for_llm(label: str, indices: list[dict]) -> str:
    if not indices:
        return ""
    lines = [
        f"{i['name']}({i['symbol']}) {i['close']:.2f}，{i['change_pct']:+.2f}%"
        if i.get("change_pct") is not None
        else f"{i['name']}({i['symbol']}) {i['close']:.2f}"
        for i in indices
    ]
    return f"【{label}核心指数】\n" + "\n".join(lines)
