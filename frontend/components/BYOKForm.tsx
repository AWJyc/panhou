"use client";

import { useEffect, useState } from "react";
import {
  BYOKConfig,
  BYOKProvider,
  PROVIDER_OPTIONS,
  clearBYOK,
  loadBYOK,
  maskKey,
  saveBYOK,
} from "@/lib/byok";

export function BYOKForm() {
  const [provider, setProvider] = useState<BYOKProvider>("deepseek");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [saved, setSaved] = useState<BYOKConfig | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    const cfg = loadBYOK();
    if (cfg) {
      setSaved(cfg);
      setProvider(cfg.provider);
      setApiKey(cfg.apiKey);
      setModel(cfg.model || "");
      setBaseUrl(cfg.baseUrl || "");
    }
  }, []);

  const opt = PROVIDER_OPTIONS.find((p) => p.value === provider)!;

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) {
      setFlash("API key 不能为空");
      return;
    }
    const cfg: BYOKConfig = {
      provider,
      apiKey: apiKey.trim(),
      model: model.trim() || undefined,
      baseUrl: baseUrl.trim() || undefined,
    };
    saveBYOK(cfg);
    setSaved(cfg);
    setFlash("已保存到此浏览器");
    setTimeout(() => setFlash(null), 2500);
  }

  function handleClear() {
    clearBYOK();
    setSaved(null);
    setApiKey("");
    setModel("");
    setBaseUrl("");
    setFlash("已清除");
    setTimeout(() => setFlash(null), 2000);
  }

  return (
    <div className="rounded-2xl border border-line bg-surface overflow-hidden">
      <div className="px-5 py-3 border-b border-line-subtle flex items-baseline justify-between">
        <span className="eyebrow">配置</span>
        {saved && (
          <span className="font-mono text-[10px] text-ink-muted">
            当前：{saved.provider} · {maskKey(saved.apiKey)}
          </span>
        )}
      </div>

      <form onSubmit={handleSave} className="p-5 space-y-5">
        <Field label="模型供应商 · Provider">
          <select
            value={provider}
            onChange={(e) => {
              const v = e.target.value as BYOKProvider;
              setProvider(v);
              const o = PROVIDER_OPTIONS.find((p) => p.value === v);
              if (o && !model) setModel(o.defaultModel);
            }}
            className="w-full bg-page border border-line text-[14px] px-3 py-2 rounded-lg focus:border-accent outline-none transition-colors"
          >
            {PROVIDER_OPTIONS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <p className="font-mono text-[11px] text-ink-muted mt-1.5">{opt.hint}</p>
        </Field>

        <Field label="API Key">
          <div className="flex gap-2">
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              autoComplete="off"
              spellCheck={false}
              className="flex-1 bg-page border border-line font-mono text-[13px] px-3 py-2 rounded-lg focus:border-accent outline-none transition-colors"
            />
            <button
              type="button"
              onClick={() => setShowKey((s) => !s)}
              className="font-mono uppercase tracking-wide2 text-[10px] px-3 py-2 border border-line rounded-lg hover:border-ink hover:text-ink text-ink-secondary transition-colors"
            >
              {showKey ? "隐藏" : "显示"}
            </button>
          </div>
          <p className="font-mono text-[11px] text-ink-muted mt-1.5">
            仅保存在你这台浏览器 · 不上传服务端 · 不进日志
          </p>
        </Field>

        <Field label={`模型 ID${opt.defaultModel ? "（留空走默认）" : "（必填）"}`}>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={opt.defaultModel || "如 deepseek-chat / gpt-4o-mini"}
            className="w-full bg-page border border-line font-mono text-[13px] px-3 py-2 rounded-lg focus:border-accent outline-none transition-colors"
          />
        </Field>

        {opt.needsBaseUrl && (
          <Field label="Base URL（自定义/自托管）">
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://your-endpoint/v1"
              className="w-full bg-page border border-line font-mono text-[13px] px-3 py-2 rounded-lg focus:border-accent outline-none transition-colors"
            />
          </Field>
        )}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            className="px-5 py-2 rounded-lg bg-inverse text-ink-inverse text-[13px] font-medium hover:bg-accent transition-colors"
          >
            保存
          </button>
          {saved && (
            <button
              type="button"
              onClick={handleClear}
              className="px-5 py-2 rounded-lg border border-fall/40 text-fall-deep text-[13px] hover:bg-fall-soft transition-colors"
            >
              清除
            </button>
          )}
          {flash && (
            <span className="font-mono text-[11px] text-accent ml-auto">{flash}</span>
          )}
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="font-mono uppercase tracking-wide2 text-[11px] text-ink-secondary mb-2 block">
        {label}
      </span>
      {children}
    </label>
  );
}
