import Link from "next/link";
import { Nav } from "@/components/Nav";
import { fetchTodayReports } from "@/lib/api";
import { Market, MARKET_LABEL, Report } from "@/lib/types";
import { formatDateline } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function Home() {
  let reports: Report[] = [];
  let error: string | null = null;
  try {
    reports = await fetchTodayReports();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const byMarket = new Map<Market, Report>();
  for (const r of reports) byMarket.set(r.market, r);

  return (
    <>
      <Nav />
      <main className="bg-page min-h-screen">
        <section className="max-w-content mx-auto px-6 lg:px-8 pt-14 lg:pt-20 pb-10">
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <span className="pill bg-accent-soft text-accent">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-livedot" />
              GLOBAL
            </span>
            <span className="dateline">
              {formatDateline(new Date().toISOString().slice(0, 10))} · 盘后总览
            </span>
          </div>
          <h1 className="text-[44px] md:text-[56px] lg:text-[64px] font-semibold tracking-tight4 leading-[1.05] text-balance text-ink">
            今日全球盘后
          </h1>
          <p className="mt-5 text-[15px] leading-[1.7] text-ink-secondary max-w-2xl">
            每日盘后由 LLM 抓取结构化数据 + 新闻片段生成。点卡片进入完整报告。
          </p>
        </section>

        {error && (
          <section className="max-w-content mx-auto px-6 lg:px-8 pb-6">
            <div className="border border-accent/40 bg-accent-soft p-4 rounded-xl text-[13px] font-mono text-ink-muted break-all">
              {error}
            </div>
          </section>
        )}

        <section className="max-w-content mx-auto px-6 lg:px-8 pb-24">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <MarketCard market="cn_a" report={byMarket.get("cn_a")} />
            <MarketCard market="us" report={byMarket.get("us")} />
            <MarketCard market="jp" report={byMarket.get("jp")} />
            <MarketCard market="kr" report={byMarket.get("kr")} />
          </div>
        </section>
      </main>
    </>
  );
}

function MarketCard({
  market,
  report,
}: {
  market: Market;
  report?: Report;
}) {
  const limitUps = report?.movers.filter((m) => m.move_type === "limit_up") ?? [];
  const limitDowns =
    report?.movers.filter((m) => m.move_type === "limit_down") ?? [];
  const topGainers =
    report?.movers.filter((m) => m.move_type === "top_gainer") ?? [];
  const topLosers =
    report?.movers.filter((m) => m.move_type === "top_loser") ?? [];

  return (
    <Link
      href={`/markets/${market}`}
      className="group block rounded-2xl border border-line bg-surface hover:border-accent/40 hover:shadow-lg transition-all p-7"
    >
      <div className="flex items-baseline justify-between gap-3 mb-4">
        <h2 className="text-[28px] font-semibold tracking-tight3 text-ink">
          {MARKET_LABEL[market]}
        </h2>
        <span className="font-mono text-[11px] text-ink-muted group-hover:text-accent transition-colors">
          {report ? formatDateline(report.report_date) : "数据未生成"}
        </span>
      </div>

      {report?.indices && report.indices.length > 0 && (
        <div className="divide-y divide-line-subtle border-y border-line-subtle mb-5">
          {report.indices.map((idx) => {
            const isUp = (idx.change_pct ?? 0) >= 0;
            return (
              <div
                key={idx.symbol}
                className="py-2.5 flex items-baseline justify-between gap-3"
              >
                <span className="text-[13px] font-medium text-ink truncate">
                  {idx.name}
                </span>
                <div className="flex items-baseline gap-3 shrink-0">
                  <span className="font-mono text-[13px] tnum text-ink">
                    {idx.close != null
                      ? idx.close.toLocaleString("en-US", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })
                      : "—"}
                  </span>
                  <span
                    className={`font-mono text-[12.5px] font-medium tnum w-16 text-right ${
                      isUp ? "text-rise" : "text-fall"
                    }`}
                  >
                    {idx.change_pct != null
                      ? `${idx.change_pct >= 0 ? "+" : ""}${idx.change_pct.toFixed(2)}%`
                      : "—"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-5">
        {market === "cn_a" ? (
          <>
            <Stat label="涨停" value={limitUps.length} tone="rise" />
            <Stat label="跌停" value={limitDowns.length} tone="fall" />
            <Stat label="板块" value={report?.sectors.length ?? 0} />
          </>
        ) : (
          <>
            <Stat label="领涨" value={topGainers.length} tone="rise" />
            <Stat label="领跌" value={topLosers.length} tone="fall" />
            <Stat label="板块" value={report?.sectors.length ?? 0} />
          </>
        )}
      </div>

      {report && report.themes && report.themes.length > 0 && (
        <div className="mb-4">
          <span className="eyebrow text-ink-muted">AI 主线</span>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {report.themes.slice(0, 5).map((t) => (
              <span
                key={t.name}
                className="pill bg-raised text-ink border border-line"
              >
                {t.name}
                <span className="font-mono text-[9px] text-ink-muted ml-1">
                  {t.members.length}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5 pt-4 border-t border-line-subtle flex items-baseline justify-between">
        <span className="font-mono text-[11px] text-ink-muted truncate">
          {report?.model_used || "—"}
        </span>
        <span className="text-[12px] text-accent group-hover:translate-x-0.5 transition-transform">
          查看详情 →
        </span>
      </div>
    </Link>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "rise" | "fall";
}) {
  const color =
    tone === "rise"
      ? "text-rise"
      : tone === "fall"
      ? "text-fall"
      : "text-ink";
  return (
    <div>
      <div className="eyebrow text-ink-muted">{label}</div>
      <div
        className={`mt-1 text-[32px] font-semibold tracking-tight3 tnum leading-none ${color}`}
      >
        {value}
      </div>
    </div>
  );
}
