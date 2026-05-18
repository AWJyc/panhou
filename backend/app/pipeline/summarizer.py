"""LLM structuring step: turn raw Tavily results into a structured market report.

Provider-agnostic: configured via REPORT_PROVIDER / REPORT_API_KEY / REPORT_MODEL.

For A 股 (`market == "cn_a"`), 涨停/跌停个股已从 akshare 直接入库（authoritative，
避免 LLM 幻觉股票代码），LLM 只产 summary + sectors。`pool_digest` 作为统计提示
让 LLM 在 summary 里准确引用涨停数/连板分布/高频题材。
"""

import json
import logging
from datetime import date
from typing import Any

from app.config import get_settings
from app.llm.providers import resolve_provider_config, structured_call

log = logging.getLogger(__name__)


_MARKET_LABEL = {
    "cn_a": "中国 A 股",
    "us": "美股",
    "jp": "日股 / 日经 225",
    "kr": "韩股 / KOSPI",
}


SYSTEM_PROMPT_BASE = """你是一位严谨的金融市场分析师。基于给定的搜索结果片段（可能附带结构化盘面统计），提取并结构化"指定市场在指定日期"的盘后报告。

🚨 语言强制规则（最高优先级，违反则视为输出失败）：
- 所有面向用户的文本字段（summary_md / sectors.name / sectors.note / movers.name / movers.note）**必须是简体中文**。
- 即使消息源是日文、韩文、英文，**禁止**在 name / note 字段保留任何原文（假名、谚文、英文短语）。必须翻译。
- 公司名翻译例：「ソニーグループ」→「索尼集团」；「トヨタ自動車」→「丰田汽车」；「アドバンテスト」→「爱德万测试」；「三菱UFJフィナンシャル・グループ」→「三菱UFJ 金融集团」；「삼성전자」→「三星电子」；「SK하이닉스」→「SK 海力士」。
- 板块名翻译例：「半導体・電子部品」→「半导体与电子元件」；「自動車」→「汽车」；「金融」→「金融」；「Technology」→「科技」。
- 美股公司名（Apple, Tesla, Nvidia 等）保留英文，note 解读仍然简体中文。
- symbol 字段（如 7203.T、005930.KS、AAPL）**保持原始代码不变**，不翻译。

通用要求：
1. 只输出工具调用结果，不要其他文字。
2. summary_md 用简体中文 Markdown，3-6 个要点，覆盖：整体涨跌、主线/热点、政策或宏观事件、风险提示。语气客观，不写投资建议。如果消息里给了结构化盘面统计（涨停数、连板分布、高频题材等），必须准确引用这些数字。
3. sectors 列出当日值得关注的板块（5-10 个），name 必须简体中文，note 写明异动原因（也用简体中文）。change_pct 如果片段中没明确百分比，留空（不传或传 null）。
4. 全部数组字段必须出现在工具入参里，即使是空数组。
"""

SYSTEM_PROMPT_DEFAULT = (
    SYSTEM_PROMPT_BASE
    + """
5. movers 列出代表性个股（涨停/跌停/领涨/领跌，合计 5-15 只）。move_type 必须是 limit_up | limit_down | top_gainer | top_loser 之一。symbol 没有就留空字符串。
6. 如果搜索结果信息不足以可靠结构化某项，宁可少列也不要编造。
7. **所有面向用户的中文字段都用简体中文**，包括：summary_md / sectors.name / sectors.note / movers.name / movers.note。
   - 日文公司名（如「ソニーグループ」「トヨタ自動車」）翻译为通用中译（「索尼集团」「丰田汽车」）；
   - 韩文公司名（如「삼성전자」「SK하이닉스」）翻译为通用中译（「三星电子」「SK 海力士」）；
   - 英文公司名保留英文（如「Apple」「Tesla」）但 note 解读必须中文；
   - sectors.name 也翻译成中文板块名（如「Technology」→「科技」，「半導体」→「半导体」）。
   - symbol 字段保持原始代码不变（如 7203.T、005930.KS）。
"""
)

SYSTEM_PROMPT_CN_A = (
    SYSTEM_PROMPT_BASE
    + """
5. **重要**：涨停/跌停个股清单已由数据源（东方财富）直接提供，**不要**在 movers 数组里重复列出涨停跌停股票，**movers 必须返回空数组 []**。
6. 你的工作集中在 summary_md（盘面综述）和 sectors（板块解读）上。
7. 关于 sectors：消息里的"板块异动 TOP 12"已给出权威的涨跌幅数据，你的 sectors **必须从这两份榜单里挑选 8-10 个最值得解读的**（涨幅或跌幅显著、带龙头线索的）。每个 sector 的 change_pct **直接抄取消息里给出的数字**（含正负号），name 与榜单中的名称一字不差。note 写明异动原因/龙头/资金面。
"""
)

SYSTEM_PROMPT_US = (
    SYSTEM_PROMPT_BASE
    + """
5. **重要**：三大指数、SPDR 行业 ETF 涨跌、领涨/领跌大盘股均已由数据源直接提供，**不要**在 movers 数组里重复，**movers 必须返回空数组 []**。
6. 你的工作集中在 summary_md（盘面综述）和 sectors（板块解读）上。summary_md 要引用三大指数当日点位/涨跌幅、点出主线/资金面/宏观事件（财报季、Fed、CPI 等）。
7. 关于 sectors：消息里"SPDR 行业 ETF 涨跌幅"列出了全部 11 个板块。请挑选当日值得解读的 6-9 个（不必全列），note 写明背后原因（财报、商品价格、利率预期、龙头公司新闻等）。name 与 ETF 板块名称一字不差。
"""
)


REPORT_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary_md": {"type": "string"},
        "sectors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "change_pct": {"type": ["number", "null"]},
                    "note": {"type": "string"},
                },
                "required": ["name", "note"],
            },
        },
        "movers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "name": {"type": "string"},
                    "move_type": {
                        "type": "string",
                        "enum": ["limit_up", "limit_down", "top_gainer", "top_loser"],
                    },
                    "change_pct": {"type": ["number", "null"]},
                    "note": {"type": "string"},
                },
                "required": ["name", "move_type"],
            },
        },
    },
    "required": ["summary_md", "sectors", "movers"],
}


def summarize(
    market: str,
    report_date: date,
    compact_sources: list[dict[str, Any]],
    pool_digest: str | None = None,
) -> tuple[dict, str]:
    """Returns (structured_dict, model_id_used)."""
    settings = get_settings()
    provider, model, base_url = resolve_provider_config(
        provider=settings.report_provider,
        api_key=settings.report_api_key or settings.anthropic_api_key,
        model=settings.report_model,
        base_url=settings.report_base_url,
    )

    market_label = _MARKET_LABEL.get(market, market)
    payload = {
        "market": market_label,
        "report_date": report_date.isoformat(),
        "sources": compact_sources,
    }
    if pool_digest:
        payload["pool_digest"] = pool_digest
    user_blob = json.dumps(payload, ensure_ascii=False)

    lang_reminder = ""
    if market in ("jp", "kr"):
        src_lang = "日文" if market == "jp" else "韩文"
        lang_reminder = (
            f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚨🚨🚨 翻译强制规则（最高优先级）🚨🚨🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"消息源是 {src_lang}，**你输出的每个文本字段** "
            f"（summary_md / sectors.name / sectors.note / movers.name / movers.note）"
            f"**必须 100% 简体中文，不允许出现一个 {src_lang} 字符**（包括括号里的注释）。\n"
            f"\n"
            f"✗ 错误示例（违反规则）：\n"
            f"  - note=\"アドバンテストが急騰\"（含日文片假名）\n"
            f"  - note=\"KB금융 股价下跌\"（括号里含韩文谚文）\n"
            f"  - note=\"三星电子（삼성전자）上涨\"（保留了韩文原文）\n"
            f"  - name=\"ファナック\"（公司名没翻译）\n"
            f"\n"
            f"✓ 正确示例：\n"
            f"  - note=\"爱德万测试急涨\"\n"
            f"  - note=\"KB 金融集团股价下跌\"\n"
            f"  - note=\"三星电子上涨\"（不要原文括注）\n"
            f"  - name=\"发那科\"\n"
            f"\n"
            f"翻译参考：\n"
            f"  ソフトバンクグループ→软银集团  トヨタ自動車→丰田汽车\n"
            f"  ソニーグループ→索尼集团  アドバンテスト→爱德万测试\n"
            f"  ファナック→发那科  三菱UFJフィナンシャル・グループ→三菱日联金融集团\n"
            f"  삼성전자→三星电子  SK하이닉스→SK 海力士  현대자동차→现代汽车\n"
            f"  LG에너지솔루션→LG 新能源  KB금융→KB 金融集团\n"
            f"\n"
            f"symbol 字段保留原代码（7203.T、005930.KS）。\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    user_text = (
        f"以下是关于 {market_label} {report_date.isoformat()} 的搜索结果"
        + ("及盘面结构化统计" if pool_digest else "")
        + f"。请生成报告。{lang_reminder}\n\n{user_blob}"
    )

    if market == "cn_a":
        system_prompt = SYSTEM_PROMPT_CN_A
    elif market == "us":
        system_prompt = SYSTEM_PROMPT_US
    else:
        system_prompt = SYSTEM_PROMPT_DEFAULT

    result = structured_call(
        provider=provider,
        api_key=settings.report_api_key or settings.anthropic_api_key,
        model=model,
        base_url=base_url,
        system_prompt=system_prompt,
        user_text=user_text,
        tool_name="submit_market_report",
        tool_description="提交结构化的当日市场报告",
        tool_schema=REPORT_TOOL_SCHEMA,
        max_tokens=4096,
    )
    return result, f"{provider}:{model}"


LIMIT_UP_REASON_SYSTEM = """你是 A 股盘后分析师。任务有两个：

A. 为**每只涨停股**写一句话「涨停原因」+ 一个高维「主题标签」。
B. 把涨停股聚成 4-7 个**高维主题**，给每个主题写一段叙事。

「原因」原则：
1. 优先引用消息片段里出现的题材、政策、公司具体事件（财报、合同、产品发布、并购等）。
2. 没有具体新闻支撑的，引用同概念/同行业板块联动。
3. 高位连板股（连板≥3）要点出资金接力强度与情绪面。
4. 18-40 字，直接讲题材/事件，不要废话。
5. **不允许编造**。没有依据时写「板块联动 + 资金接力，未见明确公司层面催化」。
6. symbol 必须与给定列表完全一致，所有涨停股都要给一条，不能漏。

「主题标签」与「主题聚类」原则：
1. 主题是比 akshare「所属行业」更高一层的市场叙事维度。例如「光伏设备」、「电池」、「新能源车零部件」可以聚成一个「新能源车产业链」主题。
2. 标签数 4-7 个，覆盖当日所有涨停股；冷门孤股可以放到「其他」主题（最多一个）。
3. 主题名称用中文 6-12 字，要有信息量（不要写「主线」「热点」这种空词）。
4. 每个主题的 narrative 写 40-80 字，讲清楚：板块涨幅 / 龙头 / 资金面 / 政策或产业催化。
5. 主题成员数加起来必须等于涨停总数。每只股的 reason 里的 theme 标签必须与 themes 数组里的 name 完全一致。
"""

LIMIT_UP_REASON_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reasons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "reason": {"type": "string"},
                    "theme": {"type": "string"},
                },
                "required": ["symbol", "reason", "theme"],
            },
        },
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "narrative": {"type": "string"},
                },
                "required": ["name", "narrative"],
            },
        },
    },
    "required": ["reasons", "themes"],
}


def generate_limit_up_reasons(
    report_date: date,
    zt_pool: list[dict[str, Any]],
    industries: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
    compact_sources: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]], str]:
    """为涨停板池每只股生成"涨停原因"+"主题标签"，并把涨停股聚成 4-7 个主题。

    Returns ({symbol: {reason, theme}}, [{name, narrative, members}], model_id)。
    失败时返回 ({}, [], "")。
    """
    if not zt_pool:
        return {}, [], ""

    settings = get_settings()
    provider, model, base_url = resolve_provider_config(
        provider=settings.report_provider,
        api_key=settings.report_api_key or settings.anthropic_api_key,
        model=settings.report_model,
        base_url=settings.report_base_url,
    )

    stocks_payload = [
        {
            "symbol": s["symbol"],
            "name": s["name"],
            "concept": s.get("concept") or "",
            "streak": s.get("limit_up_streak") or 1,
            "sealing_amount_yi": s.get("sealing_amount"),
        }
        for s in zt_pool
    ]
    boards_payload = {
        "industries_top": [
            {"name": b["name"], "change_pct": b.get("change_pct"), "leader": b.get("leading_stock")}
            for b in industries[:15]
        ],
        "concepts_top": [
            {"name": b["name"], "change_pct": b.get("change_pct"), "leader": b.get("leading_stock")}
            for b in concepts[:15]
        ],
    }
    payload = {
        "report_date": report_date.isoformat(),
        "limit_up_stocks": stocks_payload,
        "boards": boards_payload,
        "news_sources": compact_sources,
    }
    user_blob = json.dumps(payload, ensure_ascii=False)
    user_text = (
        f"{report_date.isoformat()} A 股共 {len(zt_pool)} 只涨停。"
        "请基于消息和板块联动，为每只股写一句涨停原因。\n\n" + user_blob
    )

    try:
        result = structured_call(
            provider=provider,
            api_key=settings.report_api_key or settings.anthropic_api_key,
            model=model,
            base_url=base_url,
            system_prompt=LIMIT_UP_REASON_SYSTEM,
            user_text=user_text,
            tool_name="submit_limit_up_reasons",
            tool_description="提交每只涨停股的一句话涨停原因 + 主题聚类",
            tool_schema=LIMIT_UP_REASON_TOOL_SCHEMA,
            max_tokens=8192,
        )
    except Exception as e:
        log.warning("limit-up reasons LLM call failed: %s", e)
        return {}, [], ""

    reasons_map: dict[str, dict[str, str]] = {}
    for r in result.get("reasons", []) or []:
        sym = str(r.get("symbol") or "").strip()
        reason = str(r.get("reason") or "").strip()
        theme = str(r.get("theme") or "").strip()
        if sym and reason:
            reasons_map[sym] = {"reason": reason, "theme": theme}

    # 按 theme 聚合成员，附加到 themes 数组
    members_by_theme: dict[str, list[str]] = {}
    for sym, info in reasons_map.items():
        t = info.get("theme") or "其他"
        members_by_theme.setdefault(t, []).append(sym)

    themes_out: list[dict[str, Any]] = []
    for t in result.get("themes", []) or []:
        name = str(t.get("name") or "").strip()
        if not name:
            continue
        themes_out.append(
            {
                "name": name,
                "narrative": str(t.get("narrative") or "").strip(),
                "members": members_by_theme.get(name, []),
            }
        )
    # 兜底：LLM 没在 themes 里登记但 reason.theme 引用到的标签，也补一个最小条目
    declared_names = {t["name"] for t in themes_out}
    for t_name, members in members_by_theme.items():
        if t_name and t_name not in declared_names:
            themes_out.append({"name": t_name, "narrative": "", "members": members})

    themes_out.sort(key=lambda x: -len(x.get("members") or []))
    return reasons_map, themes_out, f"{provider}:{model}"
