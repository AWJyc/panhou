"""Per-market Tavily query templates.

To add a new market: follow the `market-pipeline` skill — register here, add to
Market enum in db.models, add scheduler job, add frontend card.
"""

from datetime import date


def cn_a_queries(d: date) -> list[str]:
    """A 股查询专注于盘面叙事和宏观，结构化涨跌停由 akshare 直接拉。"""
    ds = d.strftime("%Y年%m月%d日")
    return [
        f"A股 大盘 收盘 三大指数 {ds}",
        f"A股 主线 板块 热点 {ds}",
        f"A股 政策 资金面 北向 {ds}",
    ]


def us_queries(d: date) -> list[str]:
    ds = d.strftime("%B %d %Y")
    return [
        f"US stock market close summary {ds}",
        f"S&P 500 sector performance {ds}",
        f"Fed news market impact {ds}",
        f"top gainers losers Nasdaq NYSE {ds}",
    ]


def jp_queries(d: date) -> list[str]:
    ds = d.strftime("%Y年%m月%d日")
    en = d.strftime("%B %d %Y")
    return [
        f"日経平均 終値 {ds}",
        f"TOPIX セクター 業種 {ds}",
        f"日本株 注目銘柄 上昇 下落 {ds}",
        f"Nikkei 225 close summary {en}",
        f"Bank of Japan policy yen market {en}",
    ]


def kr_queries(d: date) -> list[str]:
    ds = d.strftime("%Y년 %m월 %d일")
    en = d.strftime("%B %d %Y")
    return [
        f"코스피 종가 {ds}",
        f"코스닥 업종 {ds}",
        f"한국 주식 시장 마감 {ds}",
        f"KOSPI close summary {en}",
        f"Samsung SK Hynix Korea stocks {en}",
    ]


QUERY_BUILDERS = {
    "cn_a": cn_a_queries,
    "us": us_queries,
    "jp": jp_queries,
    "kr": kr_queries,
}


def build_queries(market: str, d: date) -> list[str]:
    builder = QUERY_BUILDERS.get(market)
    if builder is None:
        raise ValueError(f"no query builder for market: {market}")
    return builder(d)
