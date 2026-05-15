/**
 * BYOK 客户端：
 *  - 用户 key 仅保存在浏览器 localStorage。
 *  - 每次问答时随请求一次性发到后端代理，后端**不持久化**。
 *  - 切勿在前端日志/分析里打印 apiKey。
 */

export type BYOKProvider =
  | "anthropic"
  | "openai"
  | "deepseek"
  | "doubao"
  | "qwen"
  | "openai_compatible";

export interface BYOKConfig {
  provider: BYOKProvider;
  apiKey: string;
  model?: string;
  baseUrl?: string;
}

const KEY = "tradeagent_byok_v1";

export const PROVIDER_OPTIONS: {
  value: BYOKProvider;
  label: string;
  defaultModel: string;
  hint: string;
  needsBaseUrl?: boolean;
}[] = [
  {
    value: "deepseek",
    label: "DeepSeek",
    defaultModel: "deepseek-chat",
    hint: "platform.deepseek.com · sk-...",
  },
  {
    value: "openai",
    label: "OpenAI",
    defaultModel: "gpt-4o-mini",
    hint: "platform.openai.com · sk-...",
  },
  {
    value: "anthropic",
    label: "Anthropic Claude",
    defaultModel: "claude-haiku-4-5-20251001",
    hint: "console.anthropic.com · sk-ant-...",
  },
  {
    value: "doubao",
    label: "豆包（火山方舟）",
    defaultModel: "",
    hint: "ark.cn-beijing.volces.com · endpoint id 作为 model",
  },
  {
    value: "qwen",
    label: "通义千问",
    defaultModel: "qwen-plus",
    hint: "dashscope · sk-...",
  },
  {
    value: "openai_compatible",
    label: "OpenAI 兼容自定义",
    defaultModel: "",
    hint: "自托管或第三方 endpoint，需自填 base_url 和 model",
    needsBaseUrl: true,
  },
];

export function loadBYOK(): BYOKConfig | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.apiKey !== "string" || !parsed.provider) return null;
    return parsed as BYOKConfig;
  } catch {
    return null;
  }
}

export function saveBYOK(cfg: BYOKConfig): void {
  window.localStorage.setItem(KEY, JSON.stringify(cfg));
}

export function clearBYOK(): void {
  window.localStorage.removeItem(KEY);
}

export function maskKey(k: string): string {
  if (!k) return "";
  if (k.length <= 10) return k.slice(0, 3) + "***";
  return k.slice(0, 6) + "***" + k.slice(-4);
}

export interface QAMessage {
  role: "user" | "assistant";
  content: string;
}

export async function callQA(args: {
  market: "cn_a" | "us";
  messages: QAMessage[];
}): Promise<{ answer: string; model: string }> {
  const cfg = loadBYOK();
  if (!cfg) {
    throw new Error("尚未配置 AI 模型，请到设置页填入。");
  }
  const res = await fetch("/api/qa", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      market: args.market,
      provider: cfg.provider,
      api_key: cfg.apiKey,
      model: cfg.model || "",
      base_url: cfg.baseUrl || "",
      messages: args.messages,
    }),
  });
  if (!res.ok) {
    let detail = await res.text();
    try {
      const body = JSON.parse(detail);
      detail = body.detail || body.error || detail;
    } catch {
      /* keep raw */
    }
    throw new Error(detail || `请求失败 ${res.status}`);
  }
  return res.json();
}
