"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { useAuth } from "@/components/AuthContext";

export default function ForgotPasswordPage() {
  const { forgotPassword } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await forgotPassword(email);
      // 不管邮箱是否存在都跳到 reset 页 —— 防枚举
      router.push(`/reset-password?email=${encodeURIComponent(email)}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="bg-page min-h-screen">
        <section className="max-w-md mx-auto px-6 py-20">
          <h1 className="text-[40px] font-semibold tracking-tight3 text-ink mb-2">
            重置密码
          </h1>
          <p className="text-[14px] text-ink-secondary mb-8">
            输入注册邮箱，我们会发一封 6 位数字验证码。
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-[12px] text-ink-muted uppercase tracking-wide2 mb-1.5">
                注册邮箱
              </label>
              <input
                type="email"
                required
                autoFocus
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-line bg-surface text-ink text-[14px] focus:outline-none focus:border-accent"
              />
            </div>

            {err && (
              <div className="text-[13px] text-fall border border-fall/30 bg-fall/5 rounded-lg px-3 py-2">
                {err}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full py-2.5 rounded-lg bg-accent text-ink-inverse font-medium text-[14px] hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {busy ? "发送中..." : "发送验证码"}
            </button>
          </form>

          <p className="mt-6 text-[13px] text-ink-secondary">
            想起密码了？{" "}
            <Link href="/login" className="text-accent hover:underline">
              去登录
            </Link>
          </p>
        </section>
      </main>
    </>
  );
}
