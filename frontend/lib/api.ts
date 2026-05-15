import { Report, Market } from "./types";

const BACKEND =
  typeof window === "undefined"
    ? process.env.BACKEND_URL || "http://127.0.0.1:8000"
    : ""; // browser uses Next.js rewrites

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BACKEND}${path}`;
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`api ${res.status} ${res.statusText} :: ${body.slice(0, 200)}`);
  }
  return res.json();
}

export async function fetchTodayReports(): Promise<Report[]> {
  return api<Report[]>("/api/reports/today");
}

export async function fetchLatestReport(market: Market): Promise<Report> {
  return api<Report>(`/api/reports/${market}/latest`);
}

export async function fetchReportByDate(market: Market, date: string): Promise<Report> {
  return api<Report>(`/api/reports/${market}/${date}`);
}

export async function fetchReportHistory(market: Market, limit = 30) {
  return api<{ market: Market; report_date: string; status: string }[]>(
    `/api/reports/${market}?limit=${limit}`
  );
}
