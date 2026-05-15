"use client";

import { useState } from "react";
import Link from "next/link";
import { callQA } from "@/lib/byok";
import { Market, Mover } from "@/lib/types";

interface Props {
  market: Market;
  mover: Mover;
}

const PROMPT_TEMPLATE = (m: Mover) =>
  [
    `请基于今日盘后报告，对以下涨停股做一份不超过 250 字的分析：`,
    `名称：${m.name}`,
    `代码：${m.symbol}`,
    `所属板块：${m.concept || "未知"}`,
    `连板数：${m.limit_up_streak ?? 1}`,
    `今日涨跌幅：${m.change_pct?.toFixed(2) ?? "—"}%`,
    `封单：${m.sealing_amount?.toFixed(2) ?? "—"} 亿`,
    ``,
    `请输出 3-5 个要点，覆盖：催化逻辑（题材/政策/公司新闻）、资金面（连板强度/封单/同板块联动）、风险点（高位接力风险/换手率/板块持续性）。直接列点，不要客套话。`,
  ].join("\n");

export function StockDeepDiveButton({ market, mover }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const handleOpen = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setOpen(true);
    if (answer) return; // 已经拉过结果就不重复请求
    setLoading(true);
    setErr(null);
    try {
      const res = await callQA({
        market,
        messages: [{ role: "user", content: PROMPT_TEMPLATE(mover) }],
      });
      setAnswer(res.answer);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={handleOpen}
        className="mt-2.5 w-full text-[11.5px] font-mono uppercase tracking-wide2 text-accent border border-accent/40 rounded-md py-1.5 hover:bg-accent hover:text-ink-inverse transition-colors"
      >
        AI 深挖 →
      </button>
      {open && (
        <DeepDiveModal
          mover={mover}
          loading={loading}
          answer={answer}
          err={err}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

function DeepDiveModal({
  mover,
  loading,
  answer,
  err,
  onClose,
}: {
  mover: Mover;
  loading: boolean;
  answer: string;
  err: string | null;
  onClose: () => void;
}) {
  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-start justify-center pt-[10vh] px-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl rounded-2xl bg-surface border border-line shadow-2xl"
      >
        <div className="px-6 py-4 flex items-baseline justify-between border-b border-line-subtle">
          <div className="flex items-baseline gap-2">
            <span className="eyebrow-accent">AI 深挖</span>
            <h3 className="text-[17px] font-semibold text-ink">{mover.name}</h3>
            <span className="font-mono text-[11px] text-ink-muted">{mover.symbol}</span>
          </div>
          <button
            onClick={onClose}
            className="text-[18px] text-ink-muted hover:text-ink"
          >
            ×
          </button>
        </div>
        <div className="px-6 py-5 min-h-[200px]">
          {loading && (
            <div className="space-y-2.5 animate-pulse">
              <div className="h-3 bg-raised rounded w-3/4" />
              <div className="h-3 bg-raised rounded w-5/6" />
              <div className="h-3 bg-raised rounded w-2/3" />
              <div className="h-3 bg-raised rounded w-4/5" />
              <div className="h-3 bg-raised rounded w-1/2" />
              <p className="text-[12px] text-ink-muted mt-4">
                正在调用你的 AI 模型分析中…
              </p>
            </div>
          )}
          {err && (
            <div className="space-y-3">
              <p className="text-[14px] text-fall">{err}</p>
              {err.includes("尚未配置") && (
                <Link
                  href="/settings"
                  className="inline-block pill bg-accent text-ink-inverse"
                  onClick={onClose}
                >
                  去配置 BYOK →
                </Link>
              )}
            </div>
          )}
          {answer && (
            <div className="prose-ai whitespace-pre-wrap">{answer}</div>
          )}
        </div>
        <div className="px-6 py-3 border-t border-line-subtle text-[11px] text-ink-muted font-mono">
          使用你的 BYOK key 调用 · 后端不留存
        </div>
      </div>
    </div>
  );
}
