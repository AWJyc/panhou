"use client";

import { useMemo } from "react";
import { hierarchy, treemap, treemapSquarify } from "d3-hierarchy";
import { Sector } from "@/lib/types";

interface Props {
  sectors: Sector[];
}

const VIEW_W = 1000;
const VIEW_H = 560;
const PAD_OUTER = 2;
const PAD_INNER = 2;

function fillFor(pct: number | null | undefined, maxAbs: number): string {
  if (pct === null || pct === undefined) return "rgba(120,120,120,0.18)";
  const norm = Math.min(1, Math.abs(pct) / Math.max(maxAbs, 1));
  const alpha = 0.18 + 0.62 * norm;
  if (pct >= 0) return `rgba(214, 36, 42, ${alpha.toFixed(3)})`;
  return `rgba(14, 138, 85, ${alpha.toFixed(3)})`;
}

function textColorFor(pct: number | null | undefined, maxAbs: number): string {
  if (pct === null || pct === undefined) return "rgba(60,60,60,0.85)";
  const norm = Math.min(1, Math.abs(pct) / Math.max(maxAbs, 1));
  return norm > 0.55 ? "#FFFFFF" : "#1A1A1A";
}

export function SectorTreemap({ sectors }: Props) {
  const layout = useMemo(() => {
    if (!sectors.length) return null;

    // 权重：abs(change_pct)，加一个 floor 避免 0% 板块被压成一根线
    const weighted = sectors.map((s) => ({
      ...s,
      _w: s.change_pct === null || s.change_pct === undefined
        ? 0.3
        : Math.max(0.3, Math.abs(s.change_pct)),
    }));

    const maxAbs = Math.max(
      ...weighted.map((s) => (s.change_pct === null || s.change_pct === undefined ? 0 : Math.abs(s.change_pct))),
      1
    );

    const root = hierarchy<{ children?: typeof weighted; _w?: number }>({
      children: weighted,
    })
      .sum((d) => (d as any)._w ?? 0)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

    treemap<{ children?: typeof weighted }>()
      .tile(treemapSquarify)
      .size([VIEW_W, VIEW_H])
      .paddingOuter(PAD_OUTER)
      .paddingInner(PAD_INNER)(root as any);

    return {
      leaves: root.leaves() as any[],
      maxAbs,
    };
  }, [sectors]);

  if (!sectors.length) {
    return <p className="text-ink-muted text-[14px]">暂无板块数据</p>;
  }
  if (!layout) return null;

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="w-full h-auto rounded-xl bg-raised/30"
        preserveAspectRatio="none"
        style={{ aspectRatio: `${VIEW_W} / ${VIEW_H}` }}
      >
        {layout.leaves.map((leaf, i) => {
          const w = leaf.x1 - leaf.x0;
          const h = leaf.y1 - leaf.y0;
          const s = leaf.data as Sector;
          const fill = fillFor(s.change_pct, layout.maxAbs);
          const txt = textColorFor(s.change_pct, layout.maxAbs);
          const showNote = w > 110 && h > 60 && !!s.note;
          const showPct = w > 60 && h > 38;
          const showName = w > 40 && h > 22;
          const fontSize = Math.min(18, Math.max(11, Math.sqrt(w * h) / 7));
          const pctFontSize = Math.min(16, Math.max(10, fontSize - 2));

          return (
            <g key={i} transform={`translate(${leaf.x0},${leaf.y0})`}>
              <rect
                width={w}
                height={h}
                fill={fill}
                stroke="rgba(255,255,255,0.5)"
                strokeWidth={0.5}
                rx={4}
              />
              {showName && (
                <text
                  x={8}
                  y={fontSize + 6}
                  fill={txt}
                  fontSize={fontSize}
                  fontWeight={500}
                  fontFamily="ui-sans-serif, system-ui"
                  style={{ pointerEvents: "none" }}
                >
                  {s.name}
                </text>
              )}
              {showPct && s.change_pct !== null && s.change_pct !== undefined && (
                <text
                  x={8}
                  y={fontSize + pctFontSize + 12}
                  fill={txt}
                  fontSize={pctFontSize}
                  fontFamily="ui-monospace, SFMono-Regular, monospace"
                  fontWeight={600}
                  style={{ pointerEvents: "none" }}
                >
                  {s.change_pct >= 0 ? "+" : ""}
                  {s.change_pct.toFixed(2)}%
                </text>
              )}
              {showNote && (
                <foreignObject
                  x={8}
                  y={fontSize + pctFontSize + 18}
                  width={w - 16}
                  height={h - (fontSize + pctFontSize + 22)}
                >
                  <div
                    style={{
                      color: txt,
                      fontSize: `${Math.max(10, fontSize - 4)}px`,
                      lineHeight: 1.4,
                      opacity: 0.92,
                      overflow: "hidden",
                      display: "-webkit-box",
                      WebkitLineClamp: Math.floor((h - 50) / 16),
                      WebkitBoxOrient: "vertical" as any,
                    }}
                  >
                    {s.note}
                  </div>
                </foreignObject>
              )}
            </g>
          );
        })}
      </svg>

      <div className="mt-3 flex items-center justify-between text-[11px] text-ink-muted">
        <span className="font-mono">块面积 ∝ |涨跌幅|</span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: "rgba(214,36,42,0.8)" }} />
            上涨
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: "rgba(14,138,85,0.8)" }} />
            下跌
          </span>
        </div>
      </div>
    </div>
  );
}
