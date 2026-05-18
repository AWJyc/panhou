"use client";

import { Suspense, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { useAuth } from "@/components/AuthContext";

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="p-8 text-ink-muted">加载中...</div>}>
      <RegisterForm />
    </Suspense>
  );
}

function RegisterForm() {
  const { register } = useAuth();
  const router = useRouter();
  const sp = useSearchParams();
  const next = sp.get("next") || "/settings";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) {
      setErr("密码至少 8 位");
      return;
    }
    if (password !== confirm) {
      setErr("两次密码不一致");
      return;
    }
    setBusy(true);
    try {
      await register(email, password);
      router.push(next);
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
            注册
          </h1>
          <p className="text-[14px] text-ink-secondary mb-8">
            邮箱仅用于登录，不会发送营销邮件。注册后请到设置页填入你的 AI key。
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-[12px] text-ink-muted uppercase tracking-wide2 mb-1.5">
                邮箱
              </label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-line bg-surface text-ink text-[14px] focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="block text-[12px] text-ink-muted uppercase tracking-wide2 mb-1.5">
                密码（≥ 8 位）
              </label>
              <input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-line bg-surface text-ink text-[14px] focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="block text-[12px] text-ink-muted uppercase tracking-wide2 mb-1.5">
                确认密码
              </label>
              <input
                type="password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
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
              {busy ? "注册中..." : "注册"}
            </button>
          </form>

          <p className="mt-6 text-[13px] text-ink-secondary">
            已有账号？{" "}
            <Link href={`/login?next=${encodeURIComponent(next)}`} className="text-accent hover:underline">
              去登录
            </Link>
          </p>
        </section>
      </main>
    </>
  );
}
