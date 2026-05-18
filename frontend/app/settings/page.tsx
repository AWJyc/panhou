"use client";

import Link from "next/link";
import { Nav } from "@/components/Nav";
import { BYOKForm } from "@/components/BYOKForm";
import { useAuth } from "@/components/AuthContext";

export default function Settings() {
  const { user, loading } = useAuth();

  return (
    <>
      <Nav />
      <main className="bg-page">
        <section className="max-w-content mx-auto px-6 lg:px-8 pt-12 lg:pt-16 pb-20">
          <span className="eyebrow">USER PREFERENCES</span>
          <h1 className="mt-3 text-[44px] md:text-[56px] font-semibold tracking-tight3 leading-tight text-ink">
            设置 · BYOK
          </h1>

          <div className="mt-10 grid grid-cols-12 gap-10">
            <div className="col-span-12 lg:col-span-7">
              <p className="text-[16px] leading-[1.7] text-ink-secondary">
                <span className="font-medium text-ink">Bring Your Own Key.</span> 填入你自己的 AI 模型 API key，系统会用它和当日盘后报告做对话、做个股深挖。
              </p>
              <p className="text-[14px] leading-[1.7] text-ink-secondary mt-4">
                <span className="font-medium text-ink">隐私承诺：</span>
                登录后 key 会在服务端用 Fernet 对称加密落库，
                <em>明文从不出现在日志、从不返回给前端</em>。
                问答时服务端临时解密调用，调完即丢。模型消费由你的 API 账户结算。
              </p>

              <div className="mt-8">
                {loading ? (
                  <div className="text-[13px] text-ink-muted">加载中...</div>
                ) : user ? (
                  <BYOKForm />
                ) : (
                  <LoginGate />
                )}
              </div>
            </div>
            <aside className="col-span-12 lg:col-span-5">
              <div className="rounded-2xl border border-line bg-surface p-6">
                <span className="eyebrow">支持的供应商</span>
                <ul className="mt-4 space-y-3 text-[14px] text-ink-secondary leading-[1.6]">
                  <li>
                    <strong className="text-ink">DeepSeek</strong> · 中文金融语境表现好、便宜
                  </li>
                  <li>
                    <strong className="text-ink">OpenAI</strong> · GPT-4o / GPT-4o-mini
                  </li>
                  <li>
                    <strong className="text-ink">Anthropic</strong> · Claude Haiku 4.5 / Opus 4.7
                  </li>
                  <li>
                    <strong className="text-ink">豆包（火山方舟）</strong> · 需先创建 endpoint
                  </li>
                  <li>
                    <strong className="text-ink">通义千问</strong> · qwen-plus / qwen-max
                  </li>
                  <li>
                    <strong className="text-ink">OpenAI 兼容自定义</strong> · 自托管 / 第三方
                  </li>
                </ul>
              </div>
              <div className="mt-4 text-[13px] text-ink-muted leading-[1.6]">
                保存后回到 A 股 / 美股详情页，右栏的「与报告对话」和涨停股的「AI 深挖」按钮就能用了。
              </div>
            </aside>
          </div>
        </section>
      </main>
    </>
  );
}

function LoginGate() {
  return (
    <div className="rounded-2xl border border-accent/40 bg-accent-soft/40 p-6">
      <h2 className="text-[18px] font-semibold text-ink mb-2">
        登录后保存
      </h2>
      <p className="text-[13.5px] text-ink-secondary leading-[1.6]">
        BYOK 现在需要登录才能保存。登录后 key 会加密存到服务端，跨设备同步。
      </p>
      <div className="mt-5 flex items-center gap-2">
        <Link
          href="/login?next=/settings"
          className="px-4 py-2 rounded-lg bg-accent text-ink-inverse text-[13px] font-medium hover:opacity-90 transition-opacity"
        >
          登录
        </Link>
        <Link
          href="/register?next=/settings"
          className="px-4 py-2 rounded-lg border border-line text-[13px] text-ink hover:bg-raised transition-colors"
        >
          注册新账号
        </Link>
      </div>
    </div>
  );
}
