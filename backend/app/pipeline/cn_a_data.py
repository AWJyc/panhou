"""A 股结构化数据：涨停板池 / 跌停板池（akshare 包装东方财富数据）。

akshare 库较重，仅在调用时延迟导入，避免拖慢 FastAPI 启动。
"""

import logging
from datetime import date
from typing import Any

from app.pipeline._akshare_pool import run_akshare

log = logging.getLogger(__name__)


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (ValueError, TypeError):
        return None


def _to_int(v: Any, default: int | None = None) -> int | None:
    if v is None:
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


async def fetch_limit_up_pool(d: date) -> list[dict[str, Any]]:
    """涨停板池。返回按"连板数降序 + 封单金额降序"排好的记录列表。"""

    def _fetch():
        import akshare as ak

        df = ak.stock_zt_pool_em(date=d.strftime("%Y%m%d"))
        return df.to_dict(orient="records") if df is not None and not df.empty else []

    try:
        records = await run_akshare(_fetch)
    except Exception as e:
        log.warning("akshare 涨停板池抓取失败: %s", e)
        return []

    out: list[dict[str, Any]] = []
    for r in records:
        out.append(
            {
                "symbol": str(r.get("代码") or "").strip(),
                "name": str(r.get("名称") or "").strip(),
                "concept": str(r.get("所属行业") or "").strip() or None,
                "limit_up_streak": _to_int(r.get("连板数"), 1) or 1,
                "change_pct": _to_float(r.get("涨跌幅")),
                "sealing_amount": (
                    _to_float(r.get("封板资金")) / 1e8 if r.get("封板资金") else None
                ),  # 亿元
                "turnover": (
                    _to_float(r.get("成交额")) / 1e8 if r.get("成交额") else None
                ),  # 亿元
                "first_limit_time": str(r.get("首次封板时间") or "").strip(),
                "failed_seal_count": _to_int(r.get("炸板次数"), 0) or 0,
            }
        )
    out.sort(
        key=lambda x: (
            -(x["limit_up_streak"] or 0),
            -(x["sealing_amount"] or 0),
        )
    )
    return out


async def fetch_limit_down_pool(d: date) -> list[dict[str, Any]]:
    """跌停板池。"""

    def _fetch():
        import akshare as ak

        df = ak.stock_zt_pool_dtgc_em(date=d.strftime("%Y%m%d"))
        return df.to_dict(orient="records") if df is not None and not df.empty else []

    try:
        records = await run_akshare(_fetch)
    except Exception as e:
        log.warning("akshare 跌停板池抓取失败: %s", e)
        return []

    out: list[dict[str, Any]] = []
    for r in records:
        out.append(
            {
                "symbol": str(r.get("代码") or "").strip(),
                "name": str(r.get("名称") or "").strip(),
                "concept": str(r.get("所属行业") or "").strip() or None,
                "change_pct": _to_float(r.get("涨跌幅")),
                "turnover": (
                    _to_float(r.get("成交额")) / 1e8 if r.get("成交额") else None
                ),
            }
        )
    out.sort(key=lambda x: (x["change_pct"] or 0))
    return out


_A_INDEX_SINA = [
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
]


def _fetch_a_indices_eastmoney() -> list[dict[str, Any]]:
    import akshare as ak

    try:
        df = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
    except TypeError:
        df = ak.stock_zh_index_spot_em()
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    wanted = {"上证指数", "深证成指", "创业板指"}
    out = []
    for r in records:
        name = str(r.get("名称") or "").strip()
        if name not in wanted:
            continue
        out.append(
            {
                "symbol": str(r.get("代码") or "").strip(),
                "name": name,
                "close": _to_float(r.get("最新价")),
                "change_pct": _to_float(r.get("涨跌幅")),
            }
        )
    return out


def _fetch_a_indices_sina() -> list[dict[str, Any]]:
    """走新浪日线接口的兜底，逐个指数取最后两个交易日算涨跌幅。"""
    import akshare as ak

    out = []
    for sym, name in _A_INDEX_SINA:
        try:
            df = ak.stock_zh_index_daily(symbol=sym)
        except Exception as e:
            log.warning("sina 指数 %s 抓取失败: %s", sym, e)
            continue
        if df is None or df.empty or len(df) < 2:
            continue
        last = df.iloc[-1]
        prev = df.iloc[-2]
        close = _to_float(last.get("close"))
        prev_close = _to_float(prev.get("close"))
        if close is None or prev_close in (None, 0):
            continue
        out.append(
            {
                "symbol": sym,
                "name": name,
                "close": close,
                "change_pct": (close - prev_close) / prev_close * 100,
            }
        )
    return out


async def fetch_a_indices() -> list[dict[str, Any]]:
    """上证 / 深成 / 创业板 当日点位+涨跌幅。

    主路东方财富 → 兜底新浪日线（绕开 push2 子域 SSL 问题）。
    """
    try:
        records = await run_akshare(_fetch_a_indices_eastmoney)
    except Exception as e:
        log.warning("akshare A 股指数主路失败: %s", e)
        records = []
    if not records:
        try:
            records = await run_akshare(_fetch_a_indices_sina)
        except Exception as e:
            log.warning("akshare A 股指数 sina 兜底也失败: %s", e)
            return []

    order = ["上证指数", "深证成指", "创业板指"]
    records.sort(key=lambda x: order.index(x["name"]) if x["name"] in order else 99)
    return records


async def fetch_industry_boards() -> list[dict[str, Any]]:
    """行业板块当日涨跌幅（来自东方财富实时接口；盘后跑即当日收盘）。

    按 abs(涨跌幅) 降序排好，便于挑"异动板块"。
    """

    def _fetch():
        import akshare as ak

        df = ak.stock_board_industry_name_em()
        return df.to_dict(orient="records") if df is not None and not df.empty else []

    try:
        records = await run_akshare(_fetch)
    except Exception as e:
        log.warning("akshare 行业板块抓取失败: %s", e)
        return []

    out: list[dict[str, Any]] = []
    for r in records:
        name = str(r.get("板块名称") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "kind": "industry",
                "change_pct": _to_float(r.get("涨跌幅")),
                "turnover_ratio": _to_float(r.get("换手率")),
                "leading_stock": str(r.get("领涨股票") or "").strip(),
                "leading_stock_pct": _to_float(r.get("领涨股票-涨跌幅")),
                "rise_count": _to_int(r.get("上涨家数")),
                "fall_count": _to_int(r.get("下跌家数")),
            }
        )
    out.sort(key=lambda x: -abs(x["change_pct"] or 0))
    return out


async def fetch_concept_boards() -> list[dict[str, Any]]:
    """概念板块当日涨跌幅。"""

    def _fetch():
        import akshare as ak

        df = ak.stock_board_concept_name_em()
        return df.to_dict(orient="records") if df is not None and not df.empty else []

    try:
        records = await run_akshare(_fetch)
    except Exception as e:
        log.warning("akshare 概念板块抓取失败: %s", e)
        return []

    out: list[dict[str, Any]] = []
    for r in records:
        name = str(r.get("板块名称") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "kind": "concept",
                "change_pct": _to_float(r.get("涨跌幅")),
                "turnover_ratio": _to_float(r.get("换手率")),
                "leading_stock": str(r.get("领涨股票") or "").strip(),
                "leading_stock_pct": _to_float(r.get("领涨股票-涨跌幅")),
                "rise_count": _to_int(r.get("上涨家数")),
                "fall_count": _to_int(r.get("下跌家数")),
            }
        )
    out.sort(key=lambda x: -abs(x["change_pct"] or 0))
    return out


def summarize_boards_for_llm(industries: list[dict], concepts: list[dict]) -> str:
    """挑各 12 个塞给 LLM；让它在这个范围里选 8-10 个有解读价值的。"""
    if not industries and not concepts:
        return ""

    def fmt(b: dict) -> str:
        pct = b.get("change_pct")
        leader = b.get("leading_stock")
        leader_pct = b.get("leading_stock_pct")
        lead_str = f"，领涨 {leader}({leader_pct:+.1f}%)" if leader and leader_pct is not None else ""
        return f"{b['name']} {pct:+.2f}%{lead_str}" if pct is not None else b["name"]

    parts = []
    if industries:
        parts.append("【行业板块异动 TOP 12】\n" + "\n".join(fmt(b) for b in industries[:12]))
    if concepts:
        parts.append("【概念板块异动 TOP 12】\n" + "\n".join(fmt(b) for b in concepts[:12]))
    return "\n\n".join(parts)


def summarize_pool_for_llm(zt_pool: list[dict], dt_pool: list[dict]) -> str:
    """把结构化数据折叠成一段紧凑文字喂给 LLM 做叙事综述。

    不把全部个股喂进 LLM（贵且无意义），只给统计 + 龙头。
    """
    from collections import Counter

    if not zt_pool and not dt_pool:
        return "（今日无涨停/跌停数据）"

    streak_counter: Counter[int] = Counter(s["limit_up_streak"] for s in zt_pool)
    streak_summary = " / ".join(
        f"{k}板 {v} 只"
        for k, v in sorted(streak_counter.items(), key=lambda x: -x[0])
    )

    concept_counter = Counter(
        s["concept"] for s in zt_pool if s.get("concept")
    )
    top_concepts = ", ".join(
        f"{c}({n} 只)" for c, n in concept_counter.most_common(8)
    )

    dragons = [s for s in zt_pool if (s["limit_up_streak"] or 0) >= 3][:12]
    dragon_summary = ", ".join(
        f"{s['name']}({s['limit_up_streak']} 连板, {s['concept'] or '—'})"
        for s in dragons
    )

    parts = [
        f"涨停总数：{len(zt_pool)}，跌停总数：{len(dt_pool)}",
        f"连板分布：{streak_summary or '—'}",
        f"高频题材：{top_concepts or '—'}",
        f"龙头股（3 连板及以上）：{dragon_summary or '—'}",
    ]
    if dt_pool:
        dt_top = ", ".join(f"{s['name']}({s.get('concept') or '—'})" for s in dt_pool[:6])
        parts.append(f"跌停代表：{dt_top}")

    return "\n".join(parts)
