"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Market } from "@/lib/types";

interface Props {
  market: Market;
  symbol: string;
  date?: string; // YYYY-MM-DD, 缺省取今日
  width?: number;
  height?: number;
}

interface Point {
  t: string;
  close: number | null;
  volume: number | null;
}

interface SparklineData {
  symbol: string;
  date: string;
  points: Point[];
  prev_close: number | null;
  error?: string;
}

const cache = new Map<string, SparklineData>();
const inflight = new Map<string, Promise<SparklineData>>();

// 并发限流：同时最多 3 个请求在飞，避免前端 dev proxy 超时
const MAX_CONCURRENT = 1;
let active = 0;
const queue: Array<() => void> = [];

function acquire(): Promise<void> {
  if (active < MAX_CONCURRENT) {
    active++;
    return Promise.resolve();
  }
  return new Promise<void>((resolve) => {
    queue.push(() => {
      active++;
      resolve();
    });
  });
}

function release(): void {
  active--;
  const next = queue.shift();
  if (next) next();
}

async function loadSparkline(
  market: Market,
  symbol: string,
  date?: string
): Promise<SparklineData> {
  const key = `${market}:${symbol}:${date ?? ""}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const existing = inflight.get(key);
  if (existing) return existing;

  const url = `/api/stocks/sparkline?market=${market}&symbol=${symbol}${
    date ? `&date=${date}` : ""
  }`;
  const fail = (err: unknown): SparklineData => ({
    symbol,
    date: date ?? "",
    points: [],
    prev_close: null,
    error: String(err),
  });

  const p = (async () => {
    await acquire();
    try {
      // 单请求超时 20s，超了不阻塞下一个
      const ac = new AbortController();
      const timer = setTimeout(() => ac.abort(), 20000);
      try {
        const r = await fetch(url, { signal: ac.signal });
        const d = (await r.json()) as SparklineData;
        cache.set(key, d);
        return d;
      } finally {
        clearTimeout(timer);
      }
    } catch (e) {
      const d = fail(e);
      cache.set(key, d);
      return d;
    } finally {
      release();
    }
  })();

  inflight.set(key, p);
  p.finally(() => inflight.delete(key));
  return p;
}

export function Sparkline({
  market,
  symbol,
  date,
  width = 80,
  height = 24,
}: Props) {
  const [data, setData] = useState<SparklineData | null>(null);
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!ref.current || visible) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { rootMargin: "100px" }
    );
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, [visible]);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    loadSparkline(market, symbol, date).then((d) => {
      if (!cancelled) setData(d);
    });
    return () => {
      cancelled = true;
    };
  }, [visible, market, symbol, date]);

  const layout = useMemo(() => {
    if (!data?.points.length) return null;
    const closes = data.points
      .map((p) => p.close)
      .filter((c): c is number => typeof c === "number");
    if (closes.length < 2) return null;

    // y 轴范围：前收 +/- 涨停 11%，固定参考系，让限板曲线显示在顶部
    const prev = data.prev_close;
    let yMin: number;
    let yMax: number;
    if (prev && prev > 0) {
      const stretch = Math.max(prev * 0.105, Math.max(...closes) - prev, prev - Math.min(...closes));
      yMin = prev - stretch * 1.05;
      yMax = prev + stretch * 1.05;
    } else {
      const lo = Math.min(...closes);
      const hi = Math.max(...closes);
      const pad = (hi - lo) * 0.1 || 0.01;
      yMin = lo - pad;
      yMax = hi + pad;
    }
    const span = yMax - yMin || 1;

    const dx = width / (closes.length - 1);
    const xs = closes.map((_, i) => i * dx);
    const ys = closes.map((c) => height - ((c - yMin) / span) * height);

    const path = xs
      .map((x, i) => `${i === 0 ? "M" : "L"} ${x.toFixed(1)},${ys[i].toFixed(1)}`)
      .join(" ");
    const areaPath = `${path} L ${xs[xs.length - 1].toFixed(1)},${height} L 0,${height} Z`;

    const isUp = prev ? closes[closes.length - 1] >= prev : closes[closes.length - 1] >= closes[0];
    const prevY =
      prev && prev > 0
        ? height - ((prev - yMin) / span) * height
        : null;

    return { path, areaPath, isUp, prevY };
  }, [data, width, height]);

  return (
    <span
      ref={ref}
      className="inline-block shrink-0"
      style={{ width, height }}
    >
      {!visible || !data ? (
        <span className="block w-full h-full bg-line-subtle/40 rounded" />
      ) : !layout ? (
        <span className="block w-full h-full" />
      ) : (
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
          {layout.prevY != null && (
            <line
              x1={0}
              x2={width}
              y1={layout.prevY}
              y2={layout.prevY}
              stroke="rgba(120,120,120,0.45)"
              strokeWidth={0.5}
              strokeDasharray="2 2"
            />
          )}
          <path
            d={layout.areaPath}
            fill={layout.isUp ? "rgba(214,36,42,0.18)" : "rgba(14,138,85,0.18)"}
          />
          <path
            d={layout.path}
            fill="none"
            stroke={layout.isUp ? "rgba(214,36,42,0.85)" : "rgba(14,138,85,0.85)"}
            strokeWidth={1.2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      )}
    </span>
  );
}
