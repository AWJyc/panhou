export function formatDateline(iso: string): string {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
  return `${y}.${m}.${day} · 周${weekdays[d.getDay()]}`;
}

export function formatChineseDate(iso: string): string {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  return `${y}年${m}月${day}日`;
}

export function formatPct(p: number | null | undefined): string {
  if (p === null || p === undefined || Number.isNaN(p)) return "—";
  const sign = p > 0 ? "+" : "";
  return `${sign}${p.toFixed(2)}%`;
}

export function editionNumber(iso: string): string {
  const start = new Date("2026-05-01T00:00:00");
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  const days = Math.max(1, Math.floor((d.getTime() - start.getTime()) / 86400000) + 1);
  return days.toString().padStart(3, "0");
}
