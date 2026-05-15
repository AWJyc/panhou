"use client";

import { useMemo, useState } from "react";
import { Mover, Theme } from "@/lib/types";
import { usePin } from "./PinContext";

interface Props {
  themes: Theme[];
  limitUps: Mover[];
}

export function ThemesNarrative({ themes, limitUps }: Props) {
  const [active, setActive] = useState<string | null>(null);

  const moversBySymbol = useMemo(() => {
    const m = new Map<string, Mover>();
    for (const x of limitUps) m.set(x.symbol, x);
    return m;
  }, [limitUps]);

  if (!themes.length) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {themes.map((t) => {
          const isActive = active === t.name;
          const memberCount = t.members.length;
          return (
            <button
              key={t.name}
              onClick={() => setActive(isActive ? null : t.name)}
              className={`text-left rounded-xl p-4 border transition-colors ${
                isActive
                  ? "border-accent bg-accent-soft"
                  : "border-line bg-surface hover:bg-raised"
              }`}
            >
              <div className="flex items-baseline justify-between gap-2 mb-1.5">
                <h3 className="text-[15px] font-semibold tracking-tight2 text-ink">
                  {t.name}
                </h3>
                <span className="font-mono text-[11px] text-ink-muted tabular-nums shrink-0">
                  {memberCount} 只
                </span>
              </div>
              {t.narrative && (
                <p className="text-[12.5px] leading-[1.6] text-ink-secondary">
                  {t.narrative}
                </p>
              )}
            </button>
          );
        })}
      </div>

      {active && (
        <ThemeMembers
          theme={themes.find((t) => t.name === active)!}
          moversBySymbol={moversBySymbol}
          onClose={() => setActive(null)}
        />
      )}
    </div>
  );
}

function ThemeMembers({
  theme,
  moversBySymbol,
  onClose,
}: {
  theme: Theme;
  moversBySymbol: Map<string, Mover>;
  onClose: () => void;
}) {
  const members = theme.members
    .map((sym) => moversBySymbol.get(sym))
    .filter((m): m is Mover => !!m)
    .sort((a, b) => (b.limit_up_streak ?? 1) - (a.limit_up_streak ?? 1));

  const { pinned, setPinned } = usePin();

  return (
    <div className="rounded-xl border border-accent/40 bg-accent-soft/30 p-4 animate-rise">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <div className="flex items-baseline gap-2">
          <span className="eyebrow-accent">主题成员</span>
          <h4 className="text-[14px] font-semibold text-ink">{theme.name}</h4>
          <span className="font-mono text-[11px] text-ink-muted">
            {members.length} 只 · 点击查看个股详情
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-[11px] text-ink-muted hover:text-ink"
        >
          收起 ×
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-1.5">
        {members.map((m) => {
          const active = pinned === m.symbol;
          return (
            <button
              key={m.symbol}
              type="button"
              onClick={() =>
                setPinned(active ? null : m.symbol || null)
              }
              className={`flex items-baseline gap-2 text-[12.5px] py-1 px-2 -mx-2 rounded-md text-left transition-colors ${
                active
                  ? "bg-accent text-ink-inverse"
                  : "hover:bg-surface"
              }`}
            >
              <span
                className={`truncate flex-1 min-w-0 ${
                  active ? "text-ink-inverse" : "text-ink"
                }`}
              >
                {m.name}
              </span>
              <span
                className={`font-mono text-[10px] tnum shrink-0 ${
                  active ? "text-ink-inverse/80" : "text-ink-muted"
                }`}
              >
                {m.symbol}
              </span>
              <span
                className={`font-mono text-[10px] tnum shrink-0 ${
                  active ? "text-ink-inverse" : "text-rise"
                }`}
              >
                {(m.limit_up_streak ?? 1) > 1
                  ? `${m.limit_up_streak}板`
                  : "首板"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
