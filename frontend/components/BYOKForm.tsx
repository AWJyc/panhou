"use client";

import { useEffect, useState } from "react";
import { BYOKProvider, PROVIDER_OPTIONS } from "@/lib/byok";

interface ServerBYOK {
  provider: BYOKProvider;
  model: string;
  base_url: string;
  has_key: boolean;
}

async function fetchServerBYOK(): Promise<ServerBYOK | null> {
  const res = await fetch("/api/user/byok", { credentials: "include" });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`load failed ${res.status}`);
  const body = (await res.json()) as ServerBYOK | null;
  return body;
}

async function saveServerBYOK(payload: {
  provider: string;
  api_key: string;
  model: string;
  base_url: string;
}): Promise<ServerBYOK> {
  const res = await fetch("/api/user/byok", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = await res.text();
    try {
      detail = JSON.parse(detail).detail ?? detail;
    } catch {
      /* keep */
    }
    throw new Error(detail || `save failed ${res.status}`);
  }
  return (await res.json()) as ServerBYOK;
}

async function deleteServerBYOK(): Promise<void> {
  const res = await fetch("/api/user/byok", {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`delete failed ${res.status}`);
}

export function BYOKForm() {
  const [provider, setProvider] = useState<BYOKProvider>("deepseek");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [saved, setSaved] = useState<ServerBYOK | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchServerBYOK()
      .then((cfg) => {
        if (cfg) {
          setSaved(cfg);
          setProvider(cfg.provider);
          setModel(cfg.model || "");
          setBaseUrl(cfg.base_url || "");
        }
      })
      .catch(() => {
        /* ignore */
      })
      .finally(() => setLoading(false));
  }, []);

  const opt = PROVIDER_OPTIONS.find((p) => p.value === provider)!;

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) {
      setFlash("API key 不能为空");
      return;
    }
    setBusy(true);
    setFlash(null);
    try {
      const cfg = await saveServerBYOK({
        provider,
        api_key: apiKey.trim(),
        model: model.trim(),
        base_url: baseUrl.trim(),
      });
      setSaved(cfg);
      setApiKey("");
      setFlash("已加密保存到服务端");
      setTimeout(() => setFlash(null), 2500);
    } catch (e) {
      setFlash(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleClear() {
    setBusy(true);
    try {
      await deleteServerBYOK();
      setSaved(null);
      setApiKey("");
      setModel("");
      setBaseUrl("");
      setFlash("已清除");
      setTimeout(() => setFlash(null), 2000);
    } catch (e) {
      setFlash(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <div className="text-[13px] text-ink-muted">加载已保存的配置...</div>;
  }

  return (
    <div className="rounded-2xl border border-line bg-surface overflow-hidden">
      <div className="px-5 py-3 border-b border-line-subtle flex items-baseline justify-between">
        <span className="eyebrow">配置</span>
        {saved?.has_key && (
          <span className="font-mono text-[10px] text-rise">
            ✓ 已配置 · {saved.provider} · {saved.model || "默认 model"}
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
              placeholder={saved?.has_key ? "重新输入以更新（不显示历史值）" : "sk-..."}
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
            服务端用 Fernet 加密落库 · 明文不进日志、不返回前端
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
            disabled={busy}
            className="px-5 py-2 rounded-lg bg-inverse text-ink-inverse text-[13px] font-medium hover:bg-accent transition-colors disabled:opacity-50"
          >
            {busy ? "保存中..." : "保存"}
          </button>
          {saved?.has_key && (
            <button
              type="button"
              onClick={handleClear}
              disabled={busy}
              className="px-5 py-2 rounded-lg border border-fall/40 text-fall-deep text-[13px] hover:bg-fall-soft transition-colors disabled:opacity-50"
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
