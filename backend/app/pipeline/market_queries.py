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


QUERY_BUILDERS = {
    "cn_a": cn_a_queries,
    "us": us_queries,
}


def build_queries(market: str, d: date) -> list[str]:
    builder = QUERY_BUILDERS.get(market)
    if builder is None:
        raise ValueError(f"no query builder for market: {market}")
    return builder(d)
