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


# ── sina 兜底：直接 HTTP 调 sina 全球指数实时接口 ─────────────────────────
# 接口：https://hq.sinajs.cn/list=int_nikkei,int_kospi,...
# 返回：var hq_str_int_nikkei="日経平均株価,..,..,..,..,..,2026-05-18,15:00";
# 字段顺序（不同股指略有差异，主要看 close 位置）

_SINA_GLOBAL_SYM = {
    "N225": ("int_nikkei", "日经 225"),
    "TOPIX": ("int_topix", "TOPIX"),
    "KS11": ("int_kospi", "KOSPI"),
    "KOSDAQ": ("int_kosdaq", "KOSDAQ"),
    # KOSPI200, JPXN sina 无独立 code
}


def _fetch_indices_sina_http(want_codes: list[tuple[str, str]]) -> list[dict]:
    """直接走 sina hq 实时接口。"""
    import requests

    syms = []
    code_to_label: dict[str, tuple[str, str]] = {}
    for em_code, label in want_codes:
        if em_code in _SINA_GLOBAL_SYM:
            sina_sym, _ = _SINA_GLOBAL_SYM[em_code]
            syms.append(sina_sym)
            code_to_label[sina_sym] = (em_code, label)
    if not syms:
        return []

    url = "https://hq.sinajs.cn/list=" + ",".join(syms)
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = "gbk"
        text = r.text
    except Exception as e:
        log.warning("sina hq 全球指数失败: %s", e)
        return []

    out: list[dict] = []
    for line in text.split("\n"):
        line = line.strip().rstrip(";")
        if not line.startswith("var hq_str_int_"):
            continue
        # var hq_str_int_nikkei="名称,now,涨跌,涨跌幅,open,high,low,prev,...,date,time";
        try:
            sina_sym = line.split("var hq_str_")[1].split("=")[0]
            payload = line.split('="', 1)[1].rstrip('"')
            parts = payload.split(",")
            if len(parts) < 8:
                continue
            em_code, label = code_to_label.get(sina_sym, (None, None))
            if not em_code:
                continue
            close = _to_float(parts[1])
            pct = _to_float(parts[3])
            # date 通常在倒数第二个字段
            data_date = parts[-2] if len(parts) >= 2 else ""
            if close is None:
                continue
            out.append(
                {
                    "symbol": em_code,
                    "name": label,
                    "close": close,
                    "change_pct": pct,
                    "date": data_date[:10],
                }
            )
        except Exception as e:
            log.warning("sina parse line failed: %s line=%s", e, line[:80])
            continue
    return out


def _fetch_indices_sina_yfinance(want_codes: list[tuple[str, str]]) -> list[dict]:
    """对外保持函数名兼容；内部走 HTTP 实现。"""
    return _fetch_indices_sina_http(want_codes)


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
