"""美股结构化数据：3 大指数、11 个 SPDR 行业 ETF、全美股领涨/领跌 TOP。

数据源走 akshare（东方财富/新浪国内镜像），稳定且 China-friendly。
"""

import asyncio
import logging
import time
from typing import Any, Callable, TypeVar

from app.pipeline._akshare_pool import run_akshare

log = logging.getLogger(__name__)

R = TypeVar("R")


def _retry_sync(fn: Callable[[], R], name: str, attempts: int = 3, backoff: float = 2.0) -> R | None:
    """同步重试，遇到 RemoteDisconnected/ConnectionError 这类瞬时网络错误再试一次。"""
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i + 1 < attempts:
                wait = backoff * (i + 1)
                log.warning("%s attempt %d/%d failed: %s — retry in %.1fs", name, i + 1, attempts, e, wait)
                time.sleep(wait)
            else:
                log.warning("%s 最终失败 (%d 次): %s", name, attempts, e)
    return None

# 新浪美股指数代码
US_INDICES = {
    ".INX": "标普 500",
    ".DJI": "道琼斯",
    ".IXIC": "纳斯达克",
}

# SPDR 行业 ETF（11 个 S&P 500 sector），作为美股板块代表
US_SECTOR_ETFS: list[tuple[str, str]] = [
    ("XLK", "科技"),
    ("XLF", "金融"),
    ("XLV", "医疗保健"),
    ("XLY", "可选消费"),
    ("XLP", "必选消费"),
    ("XLE", "能源"),
    ("XLI", "工业"),
    ("XLB", "原材料"),
    ("XLU", "公用事业"),
    ("XLRE", "房地产"),
    ("XLC", "通信服务"),
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


def _fetch_index_one(symbol: str, name: str) -> dict | None:
    import akshare as ak

    try:
        df = ak.index_us_stock_sina(symbol=symbol)
    except Exception as e:
        log.warning("akshare 美股指数 %s 抓取失败: %s", symbol, e)
        return None
    if df is None or df.empty or len(df) < 2:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = _to_float(last.get("close"))
    prev_close = _to_float(prev.get("close"))
    if close is None or prev_close is None or prev_close == 0:
        return None
    return {
        "symbol": symbol,
        "name": name,
        "close": close,
        "change_pct": (close - prev_close) / prev_close * 100,
        "date": str(last.get("date") or ""),
    }


async def fetch_us_indices() -> list[dict]:
    out: list[dict] = []
    for sym, name in US_INDICES.items():
        try:
            r = await run_akshare(_fetch_index_one, sym, name)
        except Exception as e:
            log.warning("us index %s 失败: %s", sym, e)
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _fetch_etf_one_em(symbol: str, label: str) -> dict | None:
    """东方财富主路。"""
    import akshare as ak

    df = _retry_sync(
        lambda: ak.stock_us_hist(symbol=f"107.{symbol}", period="daily", adjust=""),
        name=f"us_etf_em/{symbol}",
        attempts=2,
        backoff=1.0,
    )
    if df is None or df.empty or len(df) < 2:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = _to_float(last.get("收盘"))
    prev_close = _to_float(prev.get("收盘"))
    change_pct_raw = _to_float(last.get("涨跌幅"))
    if close is None:
        return None
    if change_pct_raw is None and prev_close:
        change_pct_raw = (close - prev_close) / prev_close * 100
    return {
        "symbol": symbol,
        "name": label,
        "close": close,
        "change_pct": change_pct_raw,
        "date": str(last.get("日期") or ""),
    }


def _fetch_etf_one_sina(symbol: str, label: str) -> dict | None:
    """新浪兜底：单 symbol 日线接口，取最后两天算涨跌幅。"""
    import akshare as ak

    df = _retry_sync(
        lambda: ak.stock_us_daily(symbol=symbol, adjust=""),
        name=f"us_etf_sina/{symbol}",
        attempts=2,
        backoff=1.0,
    )
    if df is None or df.empty or len(df) < 2:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = _to_float(last.get("close"))
    prev_close = _to_float(prev.get("close"))
    if close is None or prev_close in (None, 0):
        return None
    return {
        "symbol": symbol,
        "name": label,
        "close": close,
        "change_pct": (close - prev_close) / prev_close * 100,
        "date": str(last.get("date") or ""),
    }


def _fetch_etf_one(symbol: str, label: str) -> dict | None:
    r = _fetch_etf_one_em(symbol, label)
    if r is not None:
        return r
    return _fetch_etf_one_sina(symbol, label)


async def fetch_us_sectors() -> list[dict]:
    """返回 SPDR sector ETF 的当日涨跌幅。

    串行调用（mini_racer 跨线程并发不安全）。
    主路东方财富 push2 → 兜底新浪日线（绕开 push2 SSL 问题）。
    """
    out: list[dict] = []
    for sym, label in US_SECTOR_ETFS:
        try:
            r = await run_akshare(_fetch_etf_one, sym, label)
        except Exception as e:
            log.warning("us etf %s 失败: %s", sym, e)
            continue
        if isinstance(r, dict):
            out.append(r)
    out.sort(key=lambda x: -abs(x["change_pct"] or 0))
    return out


def _fetch_top_movers() -> tuple[list[dict], list[dict]]:
    """从 akshare 美股池筛 top 涨/跌。

    优先用 stock_us_famous_spot_em（~100 只知名大盘股，稳定快），含 retry。
    失败时回退到全美股 stock_us_spot_em（4000+ 行，慢但全）。
    """
    import akshare as ak

    df = None
    for source_fn, label in [
        (ak.stock_us_famous_spot_em, "famous"),
        (ak.stock_us_spot_em, "spot_all"),
    ]:
        df = _retry_sync(source_fn, name=f"us_movers/{label}", attempts=3, backoff=1.5)
        if df is not None and not df.empty:
            log.info("us movers source=%s rows=%d", label, len(df))
            break
        df = None

    if df is None or df.empty:
        return [], []

    records = df.to_dict(orient="records")
    cleaned = []
    for r in records:
        change_pct = _to_float(r.get("涨跌幅"))
        if change_pct is None:
            continue
        market_cap = _to_float(r.get("总市值"))
        # famous 池里 market_cap 可能缺失，不强卡门槛；全美股池卡 5B
        if market_cap is not None and market_cap < 5e9 and len(records) > 200:
            continue
        cleaned.append(
            {
                "symbol": str(r.get("代码") or "").split(".")[-1],
                "name": str(r.get("名称") or "").strip(),
                "change_pct": change_pct,
                "latest_price": _to_float(r.get("最新价")),
                "market_cap": market_cap,
                "turnover": _to_float(r.get("成交额")),
            }
        )

    cleaned.sort(key=lambda x: -x["change_pct"])
    gainers = [c for c in cleaned if c["change_pct"] > 0][:12]
    losers = sorted(
        [c for c in cleaned if c["change_pct"] < 0], key=lambda x: x["change_pct"]
    )[:12]
    return gainers, losers


# 兜底用：当 EM push2 都挂时，走新浪日线拉这批代表性大盘股
_US_BLUECHIPS: list[tuple[str, str]] = [
    ("AAPL", "苹果"),
    ("MSFT", "微软"),
    ("GOOGL", "谷歌-A"),
    ("AMZN", "亚马逊"),
    ("META", "Meta"),
    ("NVDA", "英伟达"),
    ("TSLA", "特斯拉"),
    ("AVGO", "博通"),
    ("ORCL", "甲骨文"),
    ("CRM", "Salesforce"),
    ("ADBE", "Adobe"),
    ("NFLX", "奈飞"),
    ("AMD", "AMD"),
    ("QCOM", "高通"),
    ("INTC", "英特尔"),
    ("JPM", "摩根大通"),
    ("BAC", "美国银行"),
    ("V", "Visa"),
    ("MA", "Mastercard"),
    ("GS", "高盛"),
    ("UNH", "联合健康"),
    ("JNJ", "强生"),
    ("LLY", "礼来"),
    ("PFE", "辉瑞"),
    ("WMT", "沃尔玛"),
    ("HD", "家得宝"),
    ("COST", "好市多"),
    ("DIS", "迪士尼"),
    ("NKE", "耐克"),
    ("XOM", "埃克森美孚"),
    ("CVX", "雪佛龙"),
    ("BA", "波音"),
    ("CAT", "卡特彼勒"),
]


def _fetch_one_bluechip_sina(symbol: str, label: str) -> dict | None:
    import akshare as ak

    df = _retry_sync(
        lambda: ak.stock_us_daily(symbol=symbol, adjust=""),
        name=f"us_blue_sina/{symbol}",
        attempts=2,
        backoff=1.0,
    )
    if df is None or df.empty or len(df) < 2:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = _to_float(last.get("close"))
    prev_close = _to_float(prev.get("close"))
    if close is None or prev_close in (None, 0):
        return None
    return {
        "symbol": symbol,
        "name": label,
        "change_pct": (close - prev_close) / prev_close * 100,
        "latest_price": close,
        "market_cap": None,
        "turnover": None,
    }


def _fetch_top_movers_sina() -> tuple[list[dict], list[dict]]:
    """sina 兜底：串行拉 ~30 只蓝筹的两日收盘，算涨跌幅。"""
    cleaned: list[dict] = []
    for sym, label in _US_BLUECHIPS:
        r = _fetch_one_bluechip_sina(sym, label)
        if r:
            cleaned.append(r)
    cleaned.sort(key=lambda x: -x["change_pct"])
    gainers = [c for c in cleaned if c["change_pct"] > 0][:12]
    losers = sorted(
        [c for c in cleaned if c["change_pct"] < 0], key=lambda x: x["change_pct"]
    )[:12]
    return gainers, losers


async def fetch_us_top_movers() -> tuple[list[dict], list[dict]]:
    gainers, losers = await run_akshare(_fetch_top_movers)
    if gainers or losers:
        return gainers, losers
    log.warning("us movers EM 主路全失败，切到 sina 蓝筹兜底（~30 只）")
    return await run_akshare(_fetch_top_movers_sina)


def summarize_us_for_llm(
    indices: list[dict],
    sectors: list[dict],
    gainers: list[dict],
    losers: list[dict],
) -> str:
    """折叠美股结构化数据为紧凑文字给 LLM 写综述。"""
    parts: list[str] = []

    if indices:
        idx_lines = [
            f"{i['name']}({i['symbol']}) {i['close']:.2f}，{i['change_pct']:+.2f}%"
            for i in indices
        ]
        parts.append("【三大指数】\n" + "\n".join(idx_lines))

    if sectors:
        sec_lines = [
            f"{s['name']}({s['symbol']}) {s['change_pct']:+.2f}%"
            for s in sectors
        ]
        parts.append("【SPDR 行业 ETF 涨跌幅】\n" + "\n".join(sec_lines))

    if gainers:
        g_lines = [
            f"{g['name']}({g['symbol']}) {g['change_pct']:+.2f}%"
            for g in gainers[:8]
        ]
        parts.append("【今日领涨大盘股 (>$5B)】\n" + "\n".join(g_lines))

    if losers:
        l_lines = [
            f"{l['name']}({l['symbol']}) {l['change_pct']:+.2f}%"
            for l in losers[:8]
        ]
        parts.append("【今日领跌大盘股 (>$5B)】\n" + "\n".join(l_lines))

    return "\n\n".join(parts)
