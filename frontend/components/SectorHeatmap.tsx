import { Sector } from "@/lib/types";

interface Props {
  sectors: Sector[];
}

export function SectorHeatmap({ sectors }: Props) {
  if (!sectors.length) {
    return (
      <p className="text-ink-muted text-[14px]">暂无板块数据</p>
    );
  }

  const withPct = sectors.filter((s) => s.change_pct !== null && s.change_pct !== undefined);
  const maxAbs = withPct.length
    ? Math.max(...withPct.map((s) => Math.abs(s.change_pct!)), 1)
    : 1;

  return (
    <div className="divide-y divide-line-subtle">
      {sectors.map((s, i) => {
        const pct = s.change_pct;
        const hasPct = pct !== null && pct !== undefined;
        const isUp = hasPct && pct! >= 0;
        const intensity = hasPct ? Math.min(1, Math.abs(pct!) / maxAbs) : 0;

        return (
          <div
            key={i}
            className="py-4 grid grid-cols-12 gap-3 lg:gap-5 items-baseline"
          >
            <div className="col-span-12 lg:col-span-3 flex items-baseline gap-3">
              <span className="text-[15px] font-medium text-ink truncate">{s.name}</span>
              {hasPct && (
                <span
                  className={`font-mono text-[13px] font-medium tnum shrink-0 ${
                    isUp ? "text-rise" : "text-fall"
                  }`}
                >
                  {pct! >= 0 ? "+" : ""}
                  {pct!.toFixed(2)}%
                </span>
              )}
            </div>

            <div className="col-span-12 lg:col-span-7 text-[13px] text-ink-secondary leading-[1.6]">
              {s.note || <span className="text-ink-muted">—</span>}
            </div>

            <div className="col-span-12 lg:col-span-2">
              {hasPct ? (
                <div className="h-1.5 bg-line-subtle rounded-full overflow-hidden relative">
                  <div
                    className={`absolute top-0 bottom-0 ${
                      isUp ? "bg-rise" : "bg-fall"
                    }`}
                    style={{
                      width: `${Math.max(4, intensity * 100)}%`,
                      left: 0,
                    }}
                  />
                </div>
              ) : (
                <span className="font-mono text-[10px] text-ink-muted">—</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
