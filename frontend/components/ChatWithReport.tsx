"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { callQA, loadBYOK, QAMessage } from "@/lib/byok";
import { Market } from "@/lib/types";

interface Props {
  market: Market;
}

export function ChatWithReport({ market }: Props) {
  const [hasKey, setHasKey] = useState<boolean | null>(null);
  const [providerLabel, setProviderLabel] = useState<string>("");
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cfg = loadBYOK();
    if (cfg) {
      setHasKey(true);
      setProviderLabel(`${cfg.provider}${cfg.model ? " · " + cfg.model : ""}`);
    } else {
      setHasKey(false);
    }
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pending]);

  async function send() {
    const text = input.trim();
    if (!text || pending) return;
    const next: QAMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setPending(true);
    setError(null);
    try {
      const { answer } = await callQA({ market, messages: next });
      setMessages([...next, { role: "assistant", content: answer }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(false);
    }
  }

  if (hasKey === null) {
    return (
      <div className="rounded-2xl border border-line bg-surface p-6">
        <div className="font-mono text-[12px] text-ink-muted">加载中…</div>
      </div>
    );
  }

  if (!hasKey) {
    return (
      <div className="rounded-2xl border border-line border-dashed bg-surface p-6">
        <span className="eyebrow-accent">BYOK 未配置</span>
        <p className="mt-3 text-[14px] text-ink-secondary leading-[1.6]">
          填入你自己的 AI 模型 key 即可在此与当日报告对话。
          支持 OpenAI / Claude / DeepSeek / 豆包 / Qwen。
        </p>
        <Link
          href="/settings"
          className="inline-flex items-center gap-1.5 mt-4 px-3 py-1.5 rounded-full bg-inverse text-ink-inverse text-[12px] font-medium hover:bg-accent transition-colors"
        >
          前往设置 →
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-line bg-surface overflow-hidden flex flex-col">
      <div className="px-5 py-3 border-b border-line-subtle flex items-baseline justify-between">
        <span className="eyebrow">与报告对话</span>
        <span className="font-mono text-[10px] text-ink-muted lowercase truncate ml-2">
          {providerLabel}
        </span>
      </div>

      <div
        ref={scrollRef}
        className="max-h-[460px] overflow-y-auto px-5 py-4 space-y-4 flex-1"
      >
        {messages.length === 0 && (
          <div className="text-[13px] text-ink-muted leading-[1.6]">
            <p className="mb-2 text-ink-secondary">试试问：</p>
            <button
              onClick={() => setInput("今日主线板块的逻辑是什么？")}
              className="block text-left w-full px-3 py-2 mb-1.5 rounded-lg bg-raised hover:bg-line-subtle text-ink-secondary text-[13px] transition-colors"
            >
              今日主线板块的逻辑是什么？
            </button>
            <button
              onClick={() => setInput("龙头股之间有什么联系？")}
              className="block text-left w-full px-3 py-2 mb-1.5 rounded-lg bg-raised hover:bg-line-subtle text-ink-secondary text-[13px] transition-colors"
            >
              龙头股之间有什么联系？
            </button>
            <button
              onClick={() => setInput("当日资金流向如何？")}
              className="block text-left w-full px-3 py-2 rounded-lg bg-raised hover:bg-line-subtle text-ink-secondary text-[13px] transition-colors"
            >
              当日资金流向如何？
            </button>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i}>
            <div
              className={`font-mono uppercase tracking-wide2 text-[9px] mb-1.5 ${
                m.role === "user" ? "text-ink-muted" : "text-accent"
              }`}
            >
              {m.role === "user" ? "YOU" : "ASSISTANT"}
            </div>
            <div
              className={`text-[14px] leading-[1.65] whitespace-pre-wrap ${
                m.role === "user" ? "text-ink" : "text-ink-secondary"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {pending && (
          <div>
            <div className="font-mono uppercase tracking-wide2 text-[9px] mb-1.5 text-accent">
              ASSISTANT
            </div>
            <div className="flex gap-1.5 items-center text-[13px] text-ink-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-livedot" />
              思考中…
            </div>
          </div>
        )}
        {error && (
          <div className="rounded-lg bg-rise-soft p-3">
            <div className="font-mono uppercase tracking-wide2 text-[9px] text-rise mb-1">
              ERROR
            </div>
            <div className="font-mono text-[11px] text-rise-deep break-all">{error}</div>
          </div>
        )}
      </div>

      <div className="border-t border-line-subtle p-3 flex gap-2 bg-page">
        <textarea
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="向报告提问（Enter 发送 · Shift+Enter 换行）"
          className="flex-1 resize-none text-[14px] bg-raised border border-line-subtle focus:border-accent focus:bg-page rounded-lg outline-none px-3 py-2 transition-colors placeholder:text-ink-muted"
          disabled={pending}
        />
        <button
          onClick={send}
          disabled={pending || !input.trim()}
          className="px-4 py-2 rounded-lg bg-inverse text-ink-inverse text-[13px] font-medium hover:bg-accent disabled:bg-line disabled:text-ink-muted disabled:cursor-not-allowed transition-colors"
        >
          发送
        </button>
      </div>
    </div>
  );
}
