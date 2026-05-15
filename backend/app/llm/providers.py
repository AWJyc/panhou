"""Provider abstraction for "given a system prompt + user text + a JSON-schema-shaped tool, return the tool's parsed input dict".

Supports:
  - anthropic: native tool_use, prompt caching on system prompt
  - deepseek / doubao / qwen / openai_compatible: OpenAI-style function calling

Used by:
  - app/pipeline/summarizer.py (server-side daily report generation)
  - app/byok/proxy.py (stage 5, user-supplied key for Q&A)  # not yet wired
"""

import json
import logging
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

log = logging.getLogger(__name__)


PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "anthropic": {"base_url": "", "model": "claude-opus-4-7"},
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "doubao": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": ""},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "openai_compatible": {"base_url": "", "model": ""},
}


SUPPORTED_PROVIDERS = tuple(PROVIDER_DEFAULTS.keys())


def resolve_provider_config(
    provider: str,
    api_key: str,
    model: str = "",
    base_url: str = "",
) -> tuple[str, str, str]:
    """Return (provider, model, base_url) with defaults filled in.

    Raises ValueError if provider is unknown or required fields missing.
    """
    if provider not in PROVIDER_DEFAULTS:
        raise ValueError(f"unsupported provider: {provider}. Choose from {SUPPORTED_PROVIDERS}")
    if not api_key:
        raise ValueError(f"api_key required for provider={provider}")

    defaults = PROVIDER_DEFAULTS[provider]
    final_model = model or defaults["model"]
    final_base_url = base_url or defaults["base_url"]

    if not final_model:
        raise ValueError(
            f"model name required for provider={provider} (no default). "
            "For Doubao, pass the endpoint id; for openai_compatible, pass model + base_url."
        )
    if provider == "openai_compatible" and not final_base_url:
        raise ValueError("base_url required for provider=openai_compatible")
    return provider, final_model, final_base_url


def structured_call(
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    system_prompt: str,
    user_text: str,
    tool_name: str,
    tool_description: str,
    tool_schema: dict[str, Any],
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Force the model to call a single tool and return its parsed arguments.

    `tool_schema` is a JSON Schema object describing the tool's input
    (same shape works for Anthropic input_schema and OpenAI function parameters).
    """
    if provider == "anthropic":
        return _anthropic_call(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_text=user_text,
            tool_name=tool_name,
            tool_description=tool_description,
            tool_schema=tool_schema,
            max_tokens=max_tokens,
        )
    return _openai_compat_call(
        api_key=api_key,
        base_url=base_url,
        model=model,
        system_prompt=system_prompt,
        user_text=user_text,
        tool_name=tool_name,
        tool_description=tool_description,
        tool_schema=tool_schema,
        max_tokens=max_tokens,
    )


def _anthropic_call(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_text: str,
    tool_name: str,
    tool_description: str,
    tool_schema: dict,
    max_tokens: int,
) -> dict:
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[
            {
                "name": tool_name,
                "description": tool_description,
                "input_schema": tool_schema,
            }
        ],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": [{"type": "text", "text": user_text}]}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            return dict(block.input)
    raise RuntimeError(f"anthropic: no tool_use returned, stop_reason={resp.stop_reason}")


def chat_call(
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 2048,
) -> str:
    """非结构化对话。messages 形如 [{"role": "user"|"assistant", "content": str}]。"""
    if provider == "anthropic":
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": m["role"], "content": m["content"]} for m in messages
            ],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    client = OpenAI(api_key=api_key, base_url=base_url or None)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            *[{"role": m["role"], "content": m["content"]} for m in messages],
        ],
    )
    return resp.choices[0].message.content or ""


def _openai_compat_call(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_text: str,
    tool_name: str,
    tool_description: str,
    tool_schema: dict,
    max_tokens: int,
) -> dict:
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": tool_schema,
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )
    choice = resp.choices[0]
    tool_calls = getattr(choice.message, "tool_calls", None) or []
    for tc in tool_calls:
        if tc.function and tc.function.name == tool_name:
            raw = tc.function.arguments
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                # LLM 偶尔产畸形 JSON（少逗号/多逗号/截断），用 json_repair 兜底
                log.warning(
                    "openai_compat: bad JSON in tool args (%s); attempting repair. raw=%r",
                    e,
                    raw[:200],
                )
                try:
                    from json_repair import repair_json

                    repaired = repair_json(raw, return_objects=True)
                    if isinstance(repaired, dict):
                        return repaired
                    raise RuntimeError(
                        f"openai_compat: repair returned non-dict: {type(repaired)}"
                    )
                except Exception as repair_err:
                    raise RuntimeError(
                        f"openai_compat: JSON unrepairable. orig={e} repair={repair_err} "
                        f"raw_head={raw[:300]!r}"
                    ) from repair_err
    raise RuntimeError(
        f"openai_compat: no tool_call returned, finish_reason={choice.finish_reason}"
    )
