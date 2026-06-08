"use client";

import Link from "next/link";
import { useState, useMemo } from "react";
import { Market } from "@/lib/types";
import { formatDateline } from "@/lib/format";

interface Props {
  market: Market;
  currentDate: string;
  history: { report_date: string; status: string }[];
}

export function DateSwitcher({ market, currentDate, history }: Props) {
  const [open, setOpen] = useState(false);

  const { prev, next } = useMemo(() => {
    const sorted = [...history].sort((a, b) =>
      b.report_date.localeCompare(a.report_date)
    );
    const idx = sorted.findIndex((h) => h.report_date === currentDate);
    return {
      prev: idx >= 0 && idx + 1 < sorted.length ? sorted[idx + 1] : null,
      next: idx > 0 ? sorted[idx - 1] : null,
    };
  }, [history, currentDate]);

  const linkBase = (date?: string) =>
    date ? `/markets/${market}?date=${date}` : `/markets/${market}`;

  return (
    <div className="relative flex items-center gap-1">
      <Link
        href={prev ? linkBase(prev.report_date) : "#"}
        aria-disabled={!prev}
        className={`px-2 py-1 rounded-full text-[12px] transition-colors ${
          prev
            ? "text-ink-secondary hover:bg-raised"
            : "text-ink-muted/40 pointer-events-none"
        }`}
      >
        ← 上一日
      </Link>

      <button
        onClick={() => setOpen((o) => !o)}
        className="px-3 py-1 rounded-full text-[12px] text-ink hover:bg-raised transition-colors font-mono tabular-nums"
      >
        {formatDateline(currentDate)} · 盘后报告
      </button>

      <Link
        href={next ? linkBase(next.report_date) : "#"}
        aria-disabled={!next}
        className={`px-2 py-1 rounded-full text-[12px] transition-colors ${
          next
            ? "text-ink-secondary hover:bg-raised"
            : "text-ink-muted/40 pointer-events-none"
        }`}
      >
        下一日 →
      </Link>

      {next && (
        <Link
          href={linkBase(undefined)}
          className="ml-1 px-2 py-1 rounded-full text-[11px] text-accent hover:bg-accent-soft transition-colors"
        >
          回到最新
        </Link>
      )}

      {open && history.length > 0 && (
        <div className="absolute top-full left-0 mt-2 z-30 rounded-xl border border-line bg-surface shadow-xl p-3 w-72 max-h-80 overflow-y-auto">
          <div className="eyebrow text-ink-muted mb-2">历史报告</div>
          <ul className="space-y-0.5">
            {history.map((h) => {
              const isCurrent = h.report_date === currentDate;
              return (
                <li key={h.report_date}>
                  <Link
                    href={linkBase(h.report_date)}
                    onClick={() => setOpen(false)}
                    className={`block px-2.5 py-1.5 rounded-md font-mono text-[12px] tabular-nums transition-colors ${
                      isCurrent
                        ? "bg-accent-soft text-accent"
                        : "text-ink-secondary hover:bg-raised"
                    }`}
                  >
                    {h.report_date}
                    {h.status === "failed" && (
                      <span className="ml-2 text-[10px] text-fall">⚠ failed</span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
          <div className="mt-2 pt-2 border-t border-line-subtle text-[11px] text-ink-muted leading-snug">
            仅保留最近 3 个交易日的报告，更早的已自动清理。
          </div>
        </div>
      )}
    </div>
  );
}
