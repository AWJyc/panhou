import { Nav } from "@/components/Nav";
import { BYOKForm } from "@/components/BYOKForm";

export default function Settings() {
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
                <span className="font-medium text-ink">Bring Your Own Key.</span> 在这里填入你自己的 AI 模型 API key，系统会用它来与当日盘后报告做对话式问答。
              </p>
              <p className="text-[14px] leading-[1.7] text-ink-secondary mt-4">
                <span className="font-medium text-ink">隐私承诺：</span>
                你的 key 仅存于本浏览器的 <code className="font-mono text-[12px] bg-raised px-1.5 py-0.5 rounded">localStorage</code>
                ，问答时随请求发到后端代理一次性使用，<em>从不写入日志、从不持久化到数据库</em>。模型消费由你的 API 账户结算。
              </p>
              <div className="mt-8">
                <BYOKForm />
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
                保存后回到 A 股 / 美股详情页，右栏会出现"与报告对话"组件。
              </div>
            </aside>
          </div>
        </section>
      </main>
    </>
  );
}
