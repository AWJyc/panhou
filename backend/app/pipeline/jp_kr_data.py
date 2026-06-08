"""日股 / 韩股结构化数据：核心指数 + 精选大盘股篮子。

- 指数：akshare.index_global_spot_em（东方财富全球指数）一次拿全部，按 code 过滤。
- 板块 / 个股涨跌幅：akshare 对日韩没有板块/个股源，改用 Yahoo Finance v8/chart
  拉一篮子大盘股（每市场 ~30 只，带中文名 + 板块标签）的当日涨跌幅，并据此：
    · movers = 篮子内涨跌榜（真实 %）
    · sectors = 同标签成员涨跌幅均值（真实 %，「代表性成分股均值」非官方板块指数）
  和美股一个路子：数据给数字，LLM 只写解读。
"""

import asyncio
import concurrent.futures
import logging
import time
from datetime import datetime, timedelta, timezone
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
    # TOPIX / JPXN 在 yahoo finance 上没有清晰的 free 接口，主路 EM 失败时只拿 N225
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


# ── 精选大盘股篮子（Yahoo symbol, 中文名, 板块标签）──────────────────────
# 板块 = 该标签下成员的代表，sectors 涨跌幅取成员均值；同标签至少 2 只。
# 个股展示用的 symbol 直接用 Yahoo 代码（如 7203.T / 005930.KS）。
JP_BASKET: list[tuple[str, str, str]] = [
    ("7203.T", "丰田汽车", "汽车"),
    ("7267.T", "本田", "汽车"),
    ("7201.T", "日产汽车", "汽车"),
    ("6902.T", "电装", "汽车"),
    ("6758.T", "索尼集团", "科技与通信"),
    ("9984.T", "软银集团", "科技与通信"),
    ("9432.T", "日本电信电话", "科技与通信"),
    ("9433.T", "KDDI", "科技与通信"),
    ("6098.T", "瑞可利", "科技与通信"),
    ("6857.T", "爱德万测试", "半导体与电子"),
    ("8035.T", "东京电子", "半导体与电子"),
    ("6861.T", "基恩士", "半导体与电子"),
    ("6981.T", "村田制作所", "半导体与电子"),
    ("6954.T", "发那科", "工业与机械"),
    ("6501.T", "日立", "工业与机械"),
    ("6503.T", "三菱电机", "工业与机械"),
    ("7011.T", "三菱重工", "工业与机械"),
    ("8306.T", "三菱日联金融集团", "金融"),
    ("8316.T", "三井住友金融集团", "金融"),
    ("8411.T", "瑞穗金融集团", "金融"),
    ("8766.T", "东京海上控股", "金融"),
    ("8591.T", "欧力士", "金融"),
    ("4502.T", "武田药品", "医药健康"),
    ("4519.T", "中外制药", "医药健康"),
    ("4568.T", "第一三共", "医药健康"),
    ("4063.T", "信越化学", "材料化工"),
    ("5108.T", "普利司通", "材料化工"),
    ("8058.T", "三菱商事", "商社与能源"),
    ("8001.T", "伊藤忠商事", "商社与能源"),
    ("8031.T", "三井物产", "商社与能源"),
    ("9983.T", "迅销", "消费零售"),
    ("3382.T", "7&i 控股", "消费零售"),
]

KR_BASKET: list[tuple[str, str, str]] = [
    ("005930.KS", "三星电子", "半导体与电子"),
    ("000660.KS", "SK海力士", "半导体与电子"),
    ("066570.KS", "LG电子", "半导体与电子"),
    ("009150.KS", "三星电机", "半导体与电子"),
    ("005380.KS", "现代汽车", "汽车"),
    ("000270.KS", "起亚", "汽车"),
    ("012330.KS", "现代摩比斯", "汽车"),
    ("373220.KS", "LG新能源", "化工与电池"),
    ("051910.KS", "LG化学", "化工与电池"),
    ("006400.KS", "三星SDI", "化工与电池"),
    ("105560.KS", "KB金融集团", "金融"),
    ("055550.KS", "新韩金融集团", "金融"),
    ("086790.KS", "韩亚金融集团", "金融"),
    ("316140.KS", "友利金融集团", "金融"),
    ("035420.KS", "NAVER", "互联网与游戏"),
    ("035720.KS", "Kakao", "互联网与游戏"),
    ("036570.KS", "NCsoft", "互联网与游戏"),
    ("207940.KS", "三星生物制剂", "医药生物"),
    ("068270.KS", "赛特瑞恩", "医药生物"),
    ("005490.KS", "浦项控股", "钢铁材料"),
    ("010130.KS", "高丽亚铅", "钢铁材料"),
    ("017670.KS", "SK电讯", "通信服务"),
    ("030200.KS", "KT", "通信服务"),
    ("032640.KS", "LG U+", "通信服务"),
    ("329180.KS", "HD现代重工", "重工与造船"),
    ("042660.KS", "韩华海洋", "重工与造船"),
    ("011200.KS", "HMM", "重工与造船"),
    ("051900.KS", "LG生活健康", "消费零售"),
    ("097950.KS", "CJ第一制糖", "消费零售"),
    ("015760.KS", "韩国电力", "公用事业"),
    ("036460.KS", "韩国天然气公社", "公用事业"),
]

# 东亚交易日历法日期：JST/KST 均 UTC+9
_EAST_ASIA_TZ_OFFSET = 9


def _fetch_one_quote_yahoo(yf_sym: str, attempts: int = 2) -> dict | None:
    """Yahoo v8/chart 拉最近 5 日日线，取最后两根算当日涨跌幅。失败重试。"""
    import requests

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}"
    params = {"interval": "1d", "range": "5d"}
    for i in range(attempts):
        try:
            r = requests.get(
                url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
            )
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            ts = res["timestamp"]
            closes = res["indicators"]["quote"][0]["close"]
            pairs = [(t, c) for t, c in zip(ts, closes) if c is not None]
            if len(pairs) < 2:
                return None
            last_t, last_close = pairs[-1]
            prev_close = pairs[-2][1]
            if not prev_close:
                return None
            iso = (
                datetime.fromtimestamp(last_t, tz=timezone.utc)
                + timedelta(hours=_EAST_ASIA_TZ_OFFSET)
            ).date().isoformat()
            return {
                "close": float(last_close),
                "change_pct": (last_close - prev_close) / prev_close * 100,
                "date": iso,
            }
        except Exception as e:
            if i + 1 < attempts:
                time.sleep(0.5)
                continue
            log.warning("yahoo quote %s 失败: %s", yf_sym, e)
            return None
    return None


def _fetch_basket_quotes(basket: list[tuple[str, str, str]]) -> list[dict]:
    """并发拉一篮子大盘股的当日涨跌幅。失败的 symbol 跳过。"""

    def work(item: tuple[str, str, str]) -> dict | None:
        yf_sym, name, sector = item
        q = _fetch_one_quote_yahoo(yf_sym)
        if q is None:
            return None
        return {
            "symbol": yf_sym,
            "name": name,
            "sector": sector,
            "close": q["close"],
            "change_pct": q["change_pct"],
            "date": q["date"],
        }

    out: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(work, basket):
            if r is not None:
                out.append(r)
    return out


async def fetch_jp_basket() -> list[dict]:
    loop = asyncio.get_running_loop()
    try:
        res = await loop.run_in_executor(None, _fetch_basket_quotes, JP_BASKET)
    except Exception as e:
        log.warning("jp basket 抓取失败: %s", e)
        return []
    log.info("jp basket quotes=%d/%d", len(res), len(JP_BASKET))
    return res


async def fetch_kr_basket() -> list[dict]:
    loop = asyncio.get_running_loop()
    try:
        res = await loop.run_in_executor(None, _fetch_basket_quotes, KR_BASKET)
    except Exception as e:
        log.warning("kr basket 抓取失败: %s", e)
        return []
    log.info("kr basket quotes=%d/%d", len(res), len(KR_BASKET))
    return res


def build_movers_from_basket(
    quotes: list[dict], top_n: int = 8
) -> tuple[list[dict], list[dict]]:
    """篮子内涨跌榜：top_n 领涨 + top_n 领跌（真实 change_pct）。"""
    valid = [q for q in quotes if q.get("change_pct") is not None]
    gainers = sorted(
        [q for q in valid if q["change_pct"] > 0], key=lambda x: -x["change_pct"]
    )[:top_n]
    losers = sorted(
        [q for q in valid if q["change_pct"] < 0], key=lambda x: x["change_pct"]
    )[:top_n]
    return gainers, losers


def build_sectors_from_basket(quotes: list[dict]) -> list[dict]:
    """按板块标签聚合，change_pct = 成员涨跌幅均值。按涨跌幅降序（领涨在前）。"""
    groups: dict[str, list[float]] = {}
    for q in quotes:
        pct = q.get("change_pct")
        if pct is None:
            continue
        groups.setdefault(q["sector"], []).append(pct)
    sectors = [
        {"name": name, "change_pct": sum(v) / len(v), "members": len(v)}
        for name, v in groups.items()
    ]
    sectors.sort(key=lambda x: -x["change_pct"])
    return sectors


def summarize_overseas_for_llm(
    label: str,
    indices: list[dict],
    sectors: list[dict],
    gainers: list[dict],
    losers: list[dict],
) -> str:
    """折叠日/韩股结构化数据为紧凑文字给 LLM 写综述 + 板块解读。"""
    parts: list[str] = []
    idx = summarize_idx_for_llm(label, indices)
    if idx:
        parts.append(idx)
    if sectors:
        sec_lines = [
            f"{s['name']} {s['change_pct']:+.2f}%（{s['members']}只）" for s in sectors
        ]
        parts.append("【板块涨跌幅（代表性成分股均值）】\n" + "\n".join(sec_lines))
    if gainers:
        g_lines = [
            f"{g['name']}({g['symbol']}) {g['change_pct']:+.2f}%" for g in gainers
        ]
        parts.append("【今日领涨个股】\n" + "\n".join(g_lines))
    if losers:
        l_lines = [
            f"{l['name']}({l['symbol']}) {l['change_pct']:+.2f}%" for l in losers
        ]
        parts.append("【今日领跌个股】\n" + "\n".join(l_lines))
    return "\n\n".join(parts)
