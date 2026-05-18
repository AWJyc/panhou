export type Market = "cn_a" | "us" | "jp" | "kr";

export const MARKET_LABEL: Record<Market, string> = {
  cn_a: "中国 A 股",
  us: "美股",
  jp: "日股",
  kr: "韩股",
};

export const MARKET_LABEL_SHORT: Record<Market, string> = {
  cn_a: "A 股",
  us: "美股",
  jp: "日股",
  kr: "韩股",
};

export const MARKET_LABEL_EN: Record<Market, string> = {
  cn_a: "MAINLAND CHINA",
  us: "UNITED STATES",
  jp: "JAPAN",
  kr: "SOUTH KOREA",
};

export type MoveType = "limit_up" | "limit_down" | "top_gainer" | "top_loser";

export interface Sector {
  name: string;
  change_pct: number | null;
  note: string;
}

export interface Mover {
  symbol: string;
  name: string;
  move_type: MoveType;
  change_pct: number | null;
  note: string;
  limit_up_streak?: number | null;
  concept?: string | null;
  sealing_amount?: number | null; // 亿元
}

export interface MarketIndex {
  symbol: string;
  name: string;
  close: number | null;
  change_pct: number | null;
}

export interface Theme {
  name: string;
  narrative: string;
  members: string[];
}

export interface Report {
  id: number;
  market: Market;
  report_date: string; // ISO date
  summary_md: string;
  generated_at: string;
  model_used: string;
  status: "ok" | "failed";
  sectors: Sector[];
  movers: Mover[];
  indices: MarketIndex[];
  themes: Theme[];
}
