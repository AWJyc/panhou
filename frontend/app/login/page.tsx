"use client";

import { Suspense, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { useAuth } from "@/components/AuthContext";

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="p-8 text-ink-muted">加载中...</div>}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const sp = useSearchParams();
  const next = sp.get("next") || "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email, password);
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
            登录
          </h1>
          <p className="text-[14px] text-ink-secondary mb-8">
            登录后可在多设备同步你的 BYOK 配置并使用 AI 深挖。
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
                密码
              </label>
              <input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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
              {busy ? "登录中..." : "登录"}
            </button>
          </form>

          <p className="mt-6 text-[13px] text-ink-secondary">
            没有账号？{" "}
            <Link href={`/register?next=${encodeURIComponent(next)}`} className="text-accent hover:underline">
              立即注册
            </Link>
          </p>
        </section>
      </main>
    </>
  );
}
