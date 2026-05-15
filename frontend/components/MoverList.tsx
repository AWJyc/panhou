import { Mover, MoveType } from "@/lib/types";

interface Props {
  movers: Mover[];
}

const MOVE_LABEL: Record<string, string> = {
  top_gainer: "领涨",
  top_loser: "领跌",
};

export function MoverList({ movers }: Props) {
  if (!movers.length) {
    return <p className="text-ink-muted text-[14px]">暂无个股数据</p>;
  }

  const grouped: Record<string, Mover[]> = {};
  for (const m of movers) {
    if (!grouped[m.move_type]) grouped[m.move_type] = [];
    grouped[m.move_type].push(m);
  }

  const order: MoveType[] = ["top_gainer", "top_loser"];

  return (
    <div className="space-y-10">
      {order.map((type) => {
        const list = grouped[type];
        if (!list?.length) return null;
        const tone = type === "top_gainer" ? "rise" : "fall";
        const toneText = tone === "rise" ? "text-rise" : "text-fall";

        return (
          <div key={type}>
            <div className="flex items-baseline gap-3 mb-3">
              <h3
                className={`text-[18px] font-semibold tracking-tight2 ${
                  tone === "rise" ? "text-rise-deep" : "text-fall-deep"
                }`}
              >
                {MOVE_LABEL[type]}
              </h3>
              <span className="font-mono text-[11px] text-ink-muted">
                {list.length} 只
              </span>
            </div>
            <div className="divide-y divide-line-subtle">
              {list.map((m, i) => (
                <div
                  key={i}
                  className="py-3 grid grid-cols-12 gap-3 items-baseline"
                >
                  <div className="col-span-6 md:col-span-3 flex items-baseline gap-2">
                    <span className="text-[15px] font-medium text-ink truncate">
                      {m.name}
                    </span>
                  </div>
                  <div className="col-span-3 md:col-span-2 font-mono text-[11px] text-ink-muted tnum">
                    {m.symbol || "—"}
                  </div>
                  <div className="col-span-12 md:col-span-5 text-[13px] text-ink-secondary leading-[1.55]">
                    {m.note || <span className="text-ink-muted">—</span>}
                  </div>
                  <div className="col-span-3 md:col-span-2 md:text-right">
                    <span
                      className={`font-mono text-[14px] font-medium tnum ${toneText}`}
                    >
                      {m.change_pct !== null && m.change_pct !== undefined
                        ? `${m.change_pct >= 0 ? "+" : ""}${m.change_pct.toFixed(2)}%`
                        : "—"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
