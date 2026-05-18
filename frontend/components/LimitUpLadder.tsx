"use client";

import { useState } from "react";
import { Market, Mover } from "@/lib/types";
import { StockDeepDiveButton } from "./StockDeepDive";
import { Sparkline } from "./Sparkline";
import { usePin } from "./PinContext";

interface Props {
  limitUps: Mover[];
  limitDowns: Mover[];
  market: Market;
  reportDate: string;
}

const STREAK_LABEL: Record<number, string> = {
  1: "首板",
  2: "二连板",
  3: "三连板",
  4: "四连板",
  5: "五连板",
  6: "六连板",
  7: "七连板",
  8: "八连板",
  9: "九连板",
};
const streakLabel = (n: number) => STREAK_LABEL[n] ?? `${n} 连板`;

function formatAmt(amt?: number | null): string {
  if (amt === null || amt === undefined) return "";
  if (amt >= 100) return `¥${amt.toFixed(0)}亿`;
  if (amt >= 10) return `¥${amt.toFixed(1)}亿`;
  return `¥${amt.toFixed(2)}亿`;
}

function sortByConceptCluster(arr: Mover[]): Mover[] {
  // 同板块的挨着放：按板块出现次数降序（大板块优先），相同次数按名称稳定排序，
  // 板块内按封单金额降序。
  const counts = new Map<string, number>();
  for (const m of arr) {
    const c = m.concept || "_";
    counts.set(c, (counts.get(c) ?? 0) + 1);
  }
  return [...arr].sort((a, b) => {
    const ca = a.concept || "_";
    const cb = b.concept || "_";
    const cca = counts.get(ca) ?? 0;
    const ccb = counts.get(cb) ?? 0;
    if (cca !== ccb) return ccb - cca;
    if (ca !== cb) return ca.localeCompare(cb);
    return (b.sealing_amount ?? 0) - (a.sealing_amount ?? 0);
  });
}

export function LimitUpLadder({ limitUps, limitDowns, market, reportDate }: Props) {
  const conceptCounts = new Map<string, number>();
  for (const m of limitUps) {
    const c = m.concept;
    if (!c) continue;
    conceptCounts.set(c, (conceptCounts.get(c) ?? 0) + 1);
  }

  const byStreak = new Map<number, Mover[]>();
  for (const m of limitUps) {
    const k = m.limit_up_streak ?? 1;
    if (!byStreak.has(k)) byStreak.set(k, []);
    byStreak.get(k)!.push(m);
  }
  const streaks = Array.from(byStreak.keys()).sort((a, b) => b - a);
  for (const k of streaks) {
    byStreak.set(k, sortByConceptCluster(byStreak.get(k)!));
  }
  const limitDownsSorted = sortByConceptCluster(limitDowns);

  return (
    <div className="space-y-10">
      {streaks.map((streak) => {
        const list = byStreak.get(streak)!;
        const isHigh = streak >= 3;
        return (
          <div key={streak}>
            <div className="flex items-baseline gap-3 mb-4">
              <h3
                className={`text-[18px] font-semibold tracking-tight2 ${
                  isHigh ? "text-rise-deep" : "text-ink"
                }`}
              >
                {streakLabel(streak)}
              </h3>
              <span className="font-mono text-[11px] text-ink-muted tabular-nums">
                {list.length} 只
              </span>
              {isHigh && (
                <span className="pill bg-rise-soft text-rise-deep">DRAGON</span>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {list.map((m, i) => (
                <StockRow
                  key={i}
                  m={m}
                  tone="rise"
                  market={market}
                  reportDate={reportDate}
                  conceptCount={
                    m.concept ? conceptCounts.get(m.concept) ?? 1 : 0
                  }
                />
              ))}
            </div>
          </div>
        );
      })}

      {limitDowns.length > 0 && (
        <div>
          <div className="flex items-baseline gap-3 mb-4 pt-4 border-t border-line-subtle">
            <h3 className="text-[18px] font-semibold tracking-tight2 text-fall-deep">
              跌停
            </h3>
            <span className="font-mono text-[11px] text-ink-muted">
              {limitDowns.length} 只
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {limitDownsSorted.map((m, i) => (
              <StockRow
                key={i}
                m={m}
                tone="fall"
                market={market}
                reportDate={reportDate}
                conceptCount={0}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StockRow({
  m,
  tone,
  market,
  reportDate,
  conceptCount,
}: {
  m: Mover;
  tone: "rise" | "fall";
  market: Market;
  reportDate: string;
  conceptCount: number;
}) {
  const toneText = tone === "rise" ? "text-rise" : "text-fall";
  const isLimitUp = tone === "rise";
  const { pinned, setPinned } = usePin();
  const isPinned = pinned === m.symbol;
  // 首次 hover/pin 才挂载 sparkline，避免列表渲染时把 100+ 请求一次性打出去
  const [interacted, setInteracted] = useState(false);
  const showSparkline = isLimitUp && (interacted || isPinned);
  return (
    <div
      id={m.symbol ? `stock-${m.symbol}` : undefined}
      onMouseEnter={() => {
        if (!interacted) setInteracted(true);
      }}
      className={`group relative ${
        isPinned
          ? "ring-2 ring-accent ring-offset-2 ring-offset-page rounded-lg"
          : ""
      }`}
    >
      <div
        onClick={(e) => {
          if (isLimitUp && m.symbol) {
            // 不阻止 children 的点击（深挖按钮等），仅当点击空白行时切换 pin
            const target = e.target as HTMLElement;
            if (target.closest("button, a")) return;
            setPinned(isPinned ? null : m.symbol);
          }
        }}
        className="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-surface transition-colors cursor-pointer"
      >
        <div className="flex-1 min-w-0 flex items-baseline gap-2 flex-wrap">
          <span className="text-[14px] font-medium text-ink truncate">{m.name}</span>
          <span className="font-mono text-[10px] text-ink-muted tnum">{m.symbol || "—"}</span>
          {m.concept && (
            <span className="font-mono text-[10px] text-accent border border-accent/30 rounded px-1.5 py-0.5">
              {m.concept}
            </span>
          )}
        </div>
        {m.sealing_amount !== null && m.sealing_amount !== undefined && (
          <span className="font-mono text-[11px] text-ink-muted tnum shrink-0">
            {formatAmt(m.sealing_amount)}
          </span>
        )}
        <span className={`font-mono text-[13px] tnum font-medium shrink-0 ${toneText}`}>
          {m.change_pct !== null && m.change_pct !== undefined
            ? `${m.change_pct >= 0 ? "+" : ""}${m.change_pct.toFixed(2)}%`
            : "—"}
        </span>
      </div>
      {isLimitUp && (
        <ReasonCard
          m={m}
          conceptCount={conceptCount}
          market={market}
          reportDate={reportDate}
          isPinned={isPinned}
          showSparkline={showSparkline}
          onClose={() => setPinned(null)}
        />
      )}
    </div>
  );
}

function ReasonCard({
  m,
  conceptCount,
  market,
  reportDate,
  isPinned,
  showSparkline,
  onClose,
}: {
  m: Mover;
  conceptCount: number;
  market: Market;
  reportDate: string;
  isPinned: boolean;
  showSparkline: boolean;
  onClose: () => void;
}) {
  const streak = m.limit_up_streak ?? 1;
  const aiReason = (m.note || "").trim();
  const lines: string[] = [];
  if (m.concept) {
    lines.push(
      conceptCount > 1
        ? `板块联动：${m.concept}（今日同板块涨停 ${conceptCount} 只）`
        : `所属板块：${m.concept}`
    );
  }
  if (streak >= 2) {
    lines.push(`资金接力：连续 ${streak} 个交易日涨停，市场情绪强`);
  } else {
    lines.push(`首日涨停，关注次日是否能续接`);
  }
  if (m.sealing_amount && m.sealing_amount >= 1) {
    lines.push(
      `封单金额 ${formatAmt(m.sealing_amount)}${
        m.sealing_amount >= 5 ? "，资金锁定强" : ""
      }`
    );
  } else if (m.sealing_amount !== null && m.sealing_amount !== undefined) {
    lines.push(`封单偏薄（${formatAmt(m.sealing_amount)}），警惕开板`);
  }

  return (
    <div
      className={`transition-opacity duration-150 absolute z-30 left-0 right-0 top-full mt-1 rounded-xl border border-line bg-surface shadow-xl p-4 ${
        isPinned
          ? "visible opacity-100"
          : "invisible opacity-0 group-hover:visible group-hover:opacity-100"
      }`}
    >
      <div className="flex items-baseline gap-2 pb-2 border-b border-line-subtle">
        <span className="text-[13px] font-semibold text-ink">{m.name}</span>
        <span className="font-mono text-[10px] text-ink-muted">{m.symbol || "—"}</span>
        <span className="pill bg-rise-soft text-rise-deep ml-auto">
          {STREAK_LABEL[m.limit_up_streak ?? 1] ?? `${m.limit_up_streak} 连板`}
        </span>
        {isPinned && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            className="text-[14px] text-ink-muted hover:text-ink"
            aria-label="取消固定"
          >
            ×
          </button>
        )}
      </div>
      {aiReason && (
        <div className="mt-2.5 pb-2.5 border-b border-line-subtle">
          <div className="flex items-baseline gap-1.5 mb-1">
            <span className="font-mono text-[9px] uppercase tracking-wide2 text-accent">
              AI 涨停原因
            </span>
          </div>
          <p className="text-[12.5px] leading-[1.55] text-ink">{aiReason}</p>
        </div>
      )}
      {showSparkline && m.symbol && market === "cn_a" && (
        <div className="mt-2.5 pb-2.5 border-b border-line-subtle">
          <div className="flex items-baseline gap-1.5 mb-1.5">
            <span className="font-mono text-[9px] uppercase tracking-wide2 text-ink-muted">
              当日分时
            </span>
          </div>
          <Sparkline
            market={market}
            symbol={m.symbol}
            date={reportDate}
            width={260}
            height={56}
          />
        </div>
      )}
      <ul className="mt-2.5 space-y-1.5">
        {lines.map((l, i) => (
          <li
            key={i}
            className="text-[12px] leading-[1.55] text-ink-secondary flex gap-2"
          >
            <span className="text-accent shrink-0">·</span>
            <span>{l}</span>
          </li>
        ))}
      </ul>
      <StockDeepDiveButton market={market} mover={m} />
    </div>
  );
}
