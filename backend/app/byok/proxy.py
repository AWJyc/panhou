"""BYOK 代理：拿用户提供的 key 一次性调对应厂商，**不日志、不持久化**。

设计要点：
- api_key 只存活在请求作用域里，调完即 GC。
- log 时只记 provider/model，绝不写 key。
- 即使 LLM SDK 抛出包含 key 的异常，向客户端返回前会脱敏。
"""

import logging

from app.llm.providers import (
    SUPPORTED_PROVIDERS,
    chat_call,
    resolve_provider_config,
)

log = logging.getLogger(__name__)


_MARKET_LABEL = {"cn_a": "中国 A 股", "us": "美股"}
_MOVE_LABEL = {
    "limit_up": "涨停",
    "limit_down": "跌停",
    "top_gainer": "领涨",
    "top_loser": "领跌",
}


def build_qa_system_prompt(report) -> str:
    market_label = _MARKET_LABEL.get(report.market, report.market)

    sectors_lines: list[str] = []
    for s in report.sectors:
        pct = f"{s.change_pct:+.2f}%" if s.change_pct is not None else "—"
        note = f"  ({s.note})" if s.note else ""
        sectors_lines.append(f"- {s.name} {pct}{note}")

    grouped: dict[str, list] = {}
    for m in report.movers:
        grouped.setdefault(m.move_type, []).append(m)

    movers_blocks: list[str] = []
    for mtype, items in grouped.items():
        label = _MOVE_LABEL.get(mtype, mtype)
        lines = []
        for m in items[:30]:  # cap per type to keep prompt reasonable
            streak = f" {m.limit_up_streak}连板" if getattr(m, "limit_up_streak", None) else ""
            concept = f" [{m.concept}]" if getattr(m, "concept", None) else ""
            pct = f"{m.change_pct:+.2f}%" if m.change_pct is not None else "—"
            sym = m.symbol or "—"
            lines.append(f"- {m.name} ({sym}){streak}{concept}  {pct}")
        movers_blocks.append(f"### {label}（{len(items)} 只）\n" + "\n".join(lines))

    sectors_text = "\n".join(sectors_lines) if sectors_lines else "（无板块数据）"
    movers_text = "\n\n".join(movers_blocks) if movers_blocks else "（无个股数据）"

    return f"""你是一位金融市场分析助手。基于下面给定的"当日盘后报告"，回答用户的提问。

规则：
1. 回答必须扎根报告内容；如果用户问的细节报告里没提，直说"报告未涵盖该内容"。
2. **绝不**给出买卖建议、价格预测或未来走势判断。被问到时礼貌拒绝。
3. 用中文回答，专业、简洁，重要数字直接引用报告原文。
4. 可以做横向对比（板块之间、板块与大盘、个股与板块）和归因解读。

【当日盘后报告 · {market_label} · {report.report_date.isoformat()}】

## 综述
{report.summary_md}

## 板块涨跌
{sectors_text}

## 个股
{movers_text}
"""


def validate_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"unsupported provider {provider!r}; choose from {SUPPORTED_PROVIDERS}"
        )


def proxy_chat(
    *,
    report,
    provider: str,
    api_key: str,
    model: str = "",
    base_url: str = "",
    messages: list[dict],
) -> tuple[str, str]:
    """返回 (answer_text, model_id_used)。

    任何抛出的异常都会被调用方捕获后脱敏 api_key。本函数自身**不写日志**。
    """
    validate_provider(provider)
    if not api_key or len(api_key) < 8:
        raise ValueError("api_key 缺失或过短")

    resolved_provider, resolved_model, resolved_base_url = resolve_provider_config(
        provider=provider, api_key=api_key, model=model, base_url=base_url
    )

    system_prompt = build_qa_system_prompt(report)

    answer = chat_call(
        provider=resolved_provider,
        api_key=api_key,
        model=resolved_model,
        base_url=resolved_base_url,
        system_prompt=system_prompt,
        messages=messages,
        max_tokens=2048,
    )

    # 只记 provider/model，不记 key
    log.info(
        "byok qa ok provider=%s model=%s market=%s msgs=%d",
        resolved_provider,
        resolved_model,
        report.market,
        len(messages),
    )
    return answer, f"{resolved_provider}:{resolved_model}"
