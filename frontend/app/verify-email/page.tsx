"use client";

import { Suspense, useEffect, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { useAuth } from "@/components/AuthContext";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="p-8 text-ink-muted">加载中...</div>}>
      <VerifyEmailForm />
    </Suspense>
  );
}

function VerifyEmailForm() {
  const { user, loading, verifyEmail, resendVerifyCode } = useAuth();
  const router = useRouter();
  const sp = useSearchParams();
  const next = sp.get("next") || "/settings";

  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    if (!loading && user?.email_verified) router.push(next);
  }, [loading, user, next, router]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setTimeout(() => setResendCooldown((v) => v - 1), 1000);
    return () => clearTimeout(t);
  }, [resendCooldown]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setInfo(null);
    if (!/^\d{6}$/.test(code)) {
      setErr("请输入 6 位数字验证码");
      return;
    }
    setBusy(true);
    try {
      await verifyEmail(code);
      router.push(next);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setErr(null);
    setInfo(null);
    try {
      await resendVerifyCode();
      setInfo("已重新发送验证码，请查收邮箱（也看一下垃圾邮件）");
      setResendCooldown(60);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      const m = msg.match(/(\d+)\s*秒/);
      if (m) setResendCooldown(parseInt(m[1], 10));
      setErr(msg);
    }
  }

  return (
    <>
      <Nav />
      <main className="bg-page min-h-screen">
        <section className="max-w-md mx-auto px-6 py-20">
          <h1 className="text-[40px] font-semibold tracking-tight3 text-ink mb-2">
            验证邮箱
          </h1>
          <p className="text-[14px] text-ink-secondary mb-8">
            我们刚给{" "}
            <span className="text-ink font-medium">{user?.email ?? "..."}</span>{" "}
            发了一封 6 位数字验证码邮件，输入后即可解锁 AI 问答。
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-[12px] text-ink-muted uppercase tracking-wide2 mb-1.5">
                6 位验证码
              </label>
              <input
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                required
                autoFocus
                value={code}
                onChange={(e) =>
                  setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
                className="w-full px-3 py-2.5 rounded-lg border border-line bg-surface text-ink text-[20px] tracking-[0.5em] text-center font-mono focus:outline-none focus:border-accent"
                placeholder="000000"
              />
            </div>

            {err && (
              <div className="text-[13px] text-fall border border-fall/30 bg-fall/5 rounded-lg px-3 py-2">
                {err}
              </div>
            )}
            {info && (
              <div className="text-[13px] text-accent border border-accent/30 bg-accent/5 rounded-lg px-3 py-2">
                {info}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full py-2.5 rounded-lg bg-accent text-ink-inverse font-medium text-[14px] hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {busy ? "验证中..." : "验证"}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-between text-[13px] text-ink-secondary">
            <button
              type="button"
              onClick={onResend}
              disabled={resendCooldown > 0}
              className="text-ink-muted hover:text-accent hover:underline disabled:opacity-50 disabled:no-underline disabled:cursor-not-allowed"
            >
              {resendCooldown > 0 ? `重发验证码 (${resendCooldown}s)` : "重发验证码"}
            </button>
            <Link href="/" className="text-ink-muted hover:text-accent">
              稍后再说
            </Link>
          </div>

          <p className="mt-8 text-[12px] text-ink-muted leading-relaxed">
            验证码 15 分钟内有效，最多尝试 5 次。如果一直没收到，请检查垃圾邮件文件夹。
          </p>
        </section>
      </main>
    </>
  );
}
