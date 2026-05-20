"use client";

import { Suspense, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { useAuth } from "@/components/AuthContext";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="p-8 text-ink-muted">加载中...</div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const { resetPassword, login } = useAuth();
  const router = useRouter();
  const sp = useSearchParams();

  const [email, setEmail] = useState(sp.get("email") ?? "");
  const [code, setCode] = useState("");
  const [pwd, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!/^\d{6}$/.test(code)) {
      setErr("请输入 6 位数字验证码");
      return;
    }
    if (pwd.length < 8) {
      setErr("新密码至少 8 位");
      return;
    }
    if (pwd !== confirm) {
      setErr("两次密码不一致");
      return;
    }
    setBusy(true);
    try {
      await resetPassword(email, code, pwd);
      // 直接拿新密码登录，跳到首页
      try {
        await login(email, pwd);
        router.push("/");
      } catch {
        router.push("/login");
      }
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
            设置新密码
          </h1>
          <p className="text-[14px] text-ink-secondary mb-8">
            把刚刚邮件里的 6 位数字验证码填进来，再设个新密码。
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-[12px] text-ink-muted uppercase tracking-wide2 mb-1.5">
                注册邮箱
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-line bg-surface text-ink text-[14px] focus:outline-none focus:border-accent"
              />
            </div>
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
                value={code}
                onChange={(e) =>
                  setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
                className="w-full px-3 py-2.5 rounded-lg border border-line bg-surface text-ink text-[20px] tracking-[0.5em] text-center font-mono focus:outline-none focus:border-accent"
                placeholder="000000"
              />
            </div>
            <div>
              <label className="block text-[12px] text-ink-muted uppercase tracking-wide2 mb-1.5">
                新密码（≥ 8 位）
              </label>
              <input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={pwd}
                onChange={(e) => setPwd(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-line bg-surface text-ink text-[14px] focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="block text-[12px] text-ink-muted uppercase tracking-wide2 mb-1.5">
                确认新密码
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
              {busy ? "重置中..." : "重置密码并登录"}
            </button>
          </form>

          <p className="mt-6 text-[13px] text-ink-secondary">
            没收到？{" "}
            <Link href="/forgot-password" className="text-accent hover:underline">
              重新发送
            </Link>
          </p>
        </section>
      </main>
    </>
  );
}
