"use client";

import Link from "next/link";
import { useState } from "react";
import { Market } from "@/lib/types";
import { useAuth } from "./AuthContext";

interface Props {
  active?: Market;
}

interface TabDef {
  code: Market | "jp" | "kr";
  zh: string;
  en: string;
  status: "live" | "soon";
}

const TABS: TabDef[] = [
  { code: "cn_a", zh: "A 股", en: "CN", status: "live" },
  { code: "us", zh: "美股", en: "US", status: "live" },
  { code: "jp", zh: "日股", en: "JP", status: "live" },
  { code: "kr", zh: "韩股", en: "KR", status: "live" },
];

export function Nav({ active }: Props) {
  return (
    <header className="sticky top-0 z-30 bg-page/90 backdrop-blur-sm border-b border-line-subtle">
      <div className="max-w-content mx-auto px-6 lg:px-8 h-16 flex items-center gap-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 shrink-0 group">
          <span className="w-2 h-2 rounded-full bg-accent group-hover:animate-livedot" />
          <span className="text-[16px] font-semibold tracking-tight2 text-ink">盘后</span>
          <span className="text-ink-muted">/</span>
          <span className="font-mono text-[11px] tracking-wide2 text-ink-secondary">
            POST-CLOSE
          </span>
        </Link>

        {/* Market tabs */}
        <nav className="flex items-center gap-1 ml-2 flex-1 overflow-x-auto no-scrollbar">
          {TABS.map((t) => {
            const isActive = active === t.code;
            const isSoon = t.status === "soon";
            const baseClass =
              "group flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-all duration-150 whitespace-nowrap";
            const stateClass = isActive
              ? "bg-inverse text-ink-inverse"
              : isSoon
              ? "text-ink-muted hover:bg-raised cursor-default"
              : "text-ink hover:bg-raised";

            const inner = (
              <>
                <span className="text-[14px] font-medium">{t.zh}</span>
                <span
                  className={`font-mono text-[10px] tracking-wide2 ${
                    isActive ? "text-ink-inverse/70" : "text-ink-muted"
                  }`}
                >
                  {t.en}
                </span>
                {isSoon && (
                  <span className="font-mono text-[9px] tracking-wide2 text-accent ml-0.5">
                    SOON
                  </span>
                )}
              </>
            );

            if (isSoon) {
              return (
                <span key={t.code} className={`${baseClass} ${stateClass}`}>
                  {inner}
                </span>
              );
            }
            return (
              <Link
                key={t.code}
                href={`/markets/${t.code}`}
                className={`${baseClass} ${stateClass}`}
              >
                {inner}
              </Link>
            );
          })}
        </nav>

        {/* Right: auth + settings */}
        <NavRight />
      </div>
    </header>
  );
}

function NavRight() {
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);

  if (loading) return <span className="shrink-0 w-20" />;

  if (!user) {
    return (
      <div className="flex items-center gap-1 shrink-0">
        <Link
          href="/login"
          className="px-3 py-1.5 rounded-full text-[13px] text-ink-secondary hover:bg-raised transition-colors"
        >
          登录
        </Link>
        <Link
          href="/register"
          className="px-3 py-1.5 rounded-full text-[13px] bg-accent text-ink-inverse hover:opacity-90 transition-opacity"
        >
          注册
        </Link>
      </div>
    );
  }

  return (
    <div className="relative shrink-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full hover:bg-raised transition-colors"
      >
        <span className="w-6 h-6 rounded-full bg-accent text-ink-inverse text-[11px] font-medium flex items-center justify-center">
          {user.email.charAt(0).toUpperCase()}
        </span>
        <span className="text-[13px] text-ink-secondary max-w-[120px] truncate">
          {user.email}
        </span>
      </button>
      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-20"
            aria-hidden
          />
          <div className="absolute right-0 mt-2 w-44 rounded-xl border border-line bg-surface shadow-xl py-2 z-30">
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center justify-between px-4 py-2 text-[13px] text-ink hover:bg-raised"
            >
              <span>BYOK 设置</span>
              <span className="font-mono text-[10px] text-accent">→</span>
            </Link>
            <button
              onClick={async () => {
                setOpen(false);
                await logout();
              }}
              className="w-full text-left px-4 py-2 text-[13px] text-ink-secondary hover:bg-raised"
            >
              退出登录
            </button>
          </div>
        </>
      )}
    </div>
  );
}
