import { notFound } from "next/navigation";
import { Nav } from "@/components/Nav";
import { SummaryProse } from "@/components/SummaryProse";
import { ChatWithReport } from "@/components/ChatWithReport";
import { LimitUpLadder } from "@/components/LimitUpLadder";
import { ThemesNarrative } from "@/components/ThemesNarrative";
import { PinProvider } from "@/components/PinContext";
import { SectorTreemap } from "@/components/SectorTreemap";
import { MoverList } from "@/components/MoverList";
import { fetchLatestReport, fetchReportByDate, fetchReportHistory } from "@/lib/api";
import { DateSwitcher } from "@/components/DateSwitcher";
import { Market, Report } from "@/lib/types";
import { formatChineseDate } from "@/lib/format";

export const dynamic = "force-dynamic";

const ALLOWED: Market[] = ["cn_a", "us", "jp", "kr"];

function extractHeadline(md: string): { title: string; sub: string } {
  if (!md.trim()) return { title: "数据生成中", sub: "" };
  const cleaned = md
    .replace(/\\n/g, "\n")
    .replace(/^#{1,6}\s.*$/gm, "")
    .replace(/^\s*[-*]\s*/gm, "")
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 8);

  const firstBold = md.match(/\*\*([^*]{4,40})\*\*/);
  const title = (firstBold?.[1] ?? cleaned[0] ?? "今日盘后")
    .replace(/\*\*/g, "")
    .replace(/[。，；,;]$/, "")
    .slice(0, 30);
  const sub = (cleaned[1] || cleaned[0] || "")
    .replace(/\*\*/g, "")
    .replace(/^\*\*([^*]+)\*\*[:：]?\s*/, "$1 · ");
  return { title, sub };
}

export default async function MarketDetail({
  params,
  searchParams,
}: {
  params: { market: string };
  searchParams?: { date?: string };
}) {
  if (!ALLOWED.includes(params.market as Market)) notFound();
  const market = params.market as Market;
  const dateParam = searchParams?.date;

  let report: Report | null = null;
  let error: string | null = null;
  try {
    report = dateParam
      ? await fetchReportByDate(market, dateParam)
      : await fetchLatestReport(market);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  let history: { report_date: string; status: string }[] = [];
  try {
    history = await fetchReportHistory(market, 60);
  } catch {
    /* ignore */
  }

  const todayIso = report?.report_date ?? new Date().toISOString().slice(0, 10);
  const { title: heroTitle, sub: heroSub } = report
    ? extractHeadline(report.summary_md)
    : { title: "尚无报告", sub: "" };

  const limitUps = report?.movers.filter((m) => m.move_type === "limit_up") ?? [];
  const limitDowns = report?.movers.filter((m) => m.move_type === "limit_down") ?? [];
  const otherMovers =
    report?.movers.filter(
      (m) => m.move_type !== "limit_up" && m.move_type !== "limit_down"
    ) ?? [];

  return (
    <>
      <Nav active={market} />

      <main className="bg-page">
        {error && (
          <section className="max-w-content mx-auto px-6 lg:px-8 py-8">
            <div className="border border-accent/40 bg-accent-soft p-5 rounded-xl">
              <p className="eyebrow-accent">SYSTEM</p>
              <p className="text-[16px] mt-2 font-medium">无法连接后端</p>
              <p className="font-mono text-[12px] text-ink-muted mt-1 break-all">
                {error}
              </p>
            </div>
          </section>
        )}

        {/* ─────────── HERO ─────────── */}
        <section className="max-w-content mx-auto px-6 lg:px-8 pt-12 lg:pt-16 pb-6 lg:pb-8">
          <div className="grid grid-cols-12 gap-8 lg:gap-14 items-start">
            {/* Left: dateline + headline + AI line */}
            <div className="col-span-12 lg:col-span-7 animate-rise">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="pill bg-accent-soft text-accent">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-livedot" />
                  {dateParam ? "ARCHIVE" : "LIVE"}
                </span>
                <DateSwitcher
                  market={market}
                  currentDate={todayIso}
                  history={history}
                />
              </div>

              <h1 className="mt-6 text-[44px] md:text-[64px] lg:text-[72px] font-semibold tracking-tight4 leading-[1.05] text-balance text-ink">
                {heroTitle}
              </h1>

              {report && (
                <div className="mt-7 flex items-start gap-3">
                  <span className="pill bg-raised text-ink shrink-0 mt-0.5">
                    <span className="text-[9px] text-accent">AI</span>
                    <span>
                      {(report.model_used.split(":")[1] || report.model_used || "—").trim()}
                    </span>
                  </span>
                  <p className="text-[15px] leading-[1.7] text-ink-secondary text-balance">
                    {heroSub}
                  </p>
                </div>
              )}
            </div>

            {/* Right: snapshot panel */}
            <aside className="col-span-12 lg:col-span-5 lg:pl-6 animate-rise" style={{ animationDelay: "120ms" }}>
              {report && <SnapshotPanel
                report={report}
                market={market}
                limitUpCount={limitUps.length}
                limitDownCount={limitDowns.length}
                moverCount={otherMovers.length}
              />}
            </aside>
          </div>
        </section>

        {/* ─────────── MAIN CONTENT ─────────── */}
        {report && (
          <section className="max-w-content mx-auto px-6 lg:px-8 pb-24">
            <div className="grid grid-cols-12 gap-8 lg:gap-12">
              {/* Left main column */}
              <div className="col-span-12 lg:col-span-8 space-y-16">
                <PinProvider>
                <Block eyebrow="盘后综述" title="今日叙事">
                  {report.status === "failed" ? (
                    <div className="border-l-2 border-fall pl-4 prose-ai">
                      <p>{report.summary_md}</p>
                    </div>
                  ) : (
                    <SummaryProse md={report.summary_md} />
                  )}
                </Block>

                {report.themes && report.themes.length > 0 && (
                  <Block
                    eyebrow="AI THEMES"
                    title="主线聚类"
                    aside={
                      <span className="font-mono text-[12px] text-ink-muted">
                        {report.themes.length} 个主题 · LLM 聚合
                      </span>
                    }
                  >
                    <ThemesNarrative
                      themes={report.themes}
                      limitUps={limitUps}
                    />
                  </Block>
                )}

                {limitUps.length > 0 && (
                  <Block
                    eyebrow="LIMIT-UP POOL"
                    title="涨停板池"
                    aside={
                      <span className="font-mono text-[12px] text-ink-muted">
                        <span className="text-rise">{limitUps.length}↑</span>
                        {limitDowns.length > 0 && (
                          <>
                            {" · "}
                            <span className="text-fall">{limitDowns.length}↓</span>
                          </>
                        )}
                      </span>
                    }
                  >
                    <LimitUpLadder
                      limitUps={limitUps}
                      limitDowns={limitDowns}
                      market={market}
                      reportDate={todayIso}
                    />
                  </Block>
                )}
                </PinProvider>

                {report.sectors.length > 0 && (
                  <Block
                    eyebrow="SECTORS"
                    title="板块涨跌"
                    aside={
                      <span className="font-mono text-[12px] text-ink-muted">
                        {report.sectors.length} 项
                      </span>
                    }
                  >
                    <SectorTreemap sectors={report.sectors} />
                  </Block>
                )}

                {otherMovers.length > 0 && (
                  <Block eyebrow="MOVERS" title="个股">
                    <MoverList movers={otherMovers} />
                  </Block>
                )}
              </div>

              {/* Right column: AI chat */}
              <div className="col-span-12 lg:col-span-4">
                <div className="lg:sticky lg:top-24">
                  <ChatWithReport market={market} />
                </div>
              </div>
            </div>
          </section>
        )}

        <Footer todayIso={todayIso} model={report?.model_used} />
      </main>
    </>
  );
}

function Block({
  eyebrow,
  title,
  aside,
  children,
}: {
  eyebrow: string;
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-baseline justify-between gap-4 pb-3 border-b border-line">
        <div className="flex items-baseline gap-3">
          <span className="eyebrow">{eyebrow}</span>
          <h2 className="text-[24px] md:text-[28px] font-semibold tracking-tight2 text-ink">
            {title}
          </h2>
        </div>
        {aside}
      </div>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function SnapshotPanel({
  report,
  market,
  limitUpCount,
  limitDownCount,
  moverCount,
}: {
  report: Report;
  market: Market;
  limitUpCount: number;
  limitDownCount: number;
  moverCount: number;
}) {
  const stats: { label: string; value: string; tone?: "rise" | "fall" | "default" }[] = [];

  if (market === "cn_a") {
    stats.push(
      { label: "涨停", value: `${limitUpCount}`, tone: limitUpCount > 0 ? "rise" : "default" },
      { label: "跌停", value: `${limitDownCount}`, tone: limitDownCount > 0 ? "fall" : "default" }
    );
  } else {
    const up = report.movers.filter((m) => m.move_type === "top_gainer").length;
    const dn = report.movers.filter((m) => m.move_type === "top_loser").length;
    stats.push(
      { label: "领涨", value: `${up}`, tone: "rise" },
      { label: "领跌", value: `${dn}`, tone: "fall" }
    );
  }
  stats.push({ label: "板块", value: `${report.sectors.length}` });
  if (market !== "cn_a") stats.push({ label: "个股", value: `${moverCount}` });

  return (
    <div className="rounded-2xl border border-line bg-surface overflow-hidden">
      <div className="px-6 py-3 flex items-baseline justify-between border-b border-line-subtle">
        <span className="eyebrow">SNAPSHOT</span>
        <span className="dateline text-[11px]">
          {formatChineseDate(report.report_date)}
        </span>
      </div>

      {report.indices.length > 0 && (
        <div className="px-6 py-4 divide-y divide-line-subtle">
          {report.indices.map((idx) => {
            const isUp = (idx.change_pct ?? 0) >= 0;
            return (
              <div
                key={idx.symbol}
                className="py-2.5 flex items-baseline justify-between gap-3"
              >
                <div className="flex items-baseline gap-2 min-w-0">
                  <span className="text-[14px] font-medium text-ink truncate">
                    {idx.name}
                  </span>
                  <span className="font-mono text-[10px] text-ink-muted">
                    {idx.symbol}
                  </span>
                </div>
                <div className="flex items-baseline gap-3 shrink-0">
                  <span className="font-mono text-[14px] tnum text-ink">
                    {idx.close != null
                      ? idx.close.toLocaleString("en-US", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })
                      : "—"}
                  </span>
                  <span
                    className={`font-mono text-[13px] font-medium tnum w-16 text-right ${
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

      <dl className="px-6 py-5 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-line-subtle">
        {stats.map((it, i) => (
          <div key={i}>
            <dt className="eyebrow text-ink-muted">{it.label}</dt>
            <dd
              className={`mt-1 text-[32px] font-semibold tracking-tight3 tnum leading-none ${
                it.tone === "rise"
                  ? "text-rise"
                  : it.tone === "fall"
                  ? "text-fall"
                  : "text-ink"
              }`}
            >
              {it.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="px-6 py-3 border-t border-line-subtle flex items-baseline justify-between gap-3">
        <span className="eyebrow shrink-0">MODEL</span>
        <span className="font-mono text-[11px] text-ink-secondary text-right break-all leading-snug">
          {report.model_used || "—"}
        </span>
      </div>
    </div>
  );
}

function Footer({ todayIso, model }: { todayIso: string; model?: string }) {
  return (
    <footer className="border-t border-line-subtle bg-surface mt-12">
      <div className="max-w-content mx-auto px-6 lg:px-8 py-10 flex items-baseline justify-between flex-wrap gap-3">
        <span className="font-mono text-[11px] tracking-wide1 text-ink-muted">
          © 2026 盘后 · tradeAgent · {todayIso}
        </span>
        <span className="font-mono text-[11px] tracking-wide1 text-ink-muted">
          {model ? `${model} · ` : ""}非投资建议 · NOT INVESTMENT ADVICE
        </span>
      </div>
    </footer>
  );
}
