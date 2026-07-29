"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";

interface ModelConfig {
  id: string;
  name: string;
  capability: string;
  base_url: string | null;
  model: string | null;
  api_key_masked: string | null;
  parameters: Record<string, unknown> | null;
  allow_send_raw_image: boolean;
  allow_send_raw_text: boolean;
  is_enabled: boolean;
  is_default: boolean;
}

const CAP_LABELS: Record<string, string> = { text: "文本", vision: "视觉", embedding: "Embedding" };

export default function ModelsPage() {
  const [items, setItems] = useState<ModelConfig[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      setItems(await api.get<ModelConfig[]>(`/api/model-configs`));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "加载失败");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function create() {
    const name = prompt("配置名称(如:内网视觉模型)");
    if (!name) return;
    const capability = prompt("能力类型(text / vision / embedding)", "vision") as
      | "text"
      | "vision"
      | "embedding";
    if (!capability || !["text", "vision", "embedding"].includes(capability)) {
      setMsg("能力类型无效");
      return;
    }
    const base_url = prompt("Base URL(OpenAI 兼容,如 https://api.openai.com)", "https://api.openai.com");
    const model = prompt("模型(如 gpt-4o)", "");
    const api_key = prompt("API Key(留空则不设)", "");
    try {
      await api.post(`/api/model-configs`, {
        name,
        capability,
        base_url,
        model,
        api_key: api_key || undefined,
        is_enabled: true,
      });
      setMsg("已创建");
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "创建失败");
    }
  }

  async function toggleDefault(m: ModelConfig) {
    try {
      await api.post(`/api/model-configs/${m.id}/set-default`);
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  async function test(m: ModelConfig) {
    setBusy(m.id);
    setMsg("");
    try {
      const r = await api.post<{ success: boolean; latency_ms: number; model_returned: string | null; error: string | null; sample: string | null }>(
        `/api/model-configs/${m.id}/test`
      );
      setMsg(
        r.success
          ? `✓ 测试成功 · ${r.latency_ms}ms · 模型:${r.model_returned || "-"}${r.sample ? ` · 样本:${String(r.sample).slice(0, 40)}` : ""}`
          : `✗ 测试失败:${r.error}`
      );
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "测试失败");
    } finally {
      setBusy(null);
    }
  }

  async function remove(m: ModelConfig) {
    if (!confirm(`删除配置「${m.name}」?`)) return;
    try {
      await api.delete(`/api/model-configs/${m.id}`);
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "删除失败");
    }
  }

  return (
    <AppShell title="模型配置">
      <div className="max-w-4xl space-y-5">
        {msg && (
          <div className="text-sm bg-brand-50 text-brand-700 px-3 py-2 rounded">{msg}</div>
        )}
        <div className="flex justify-between items-center">
          <p className="text-xs text-gray-400">
            文本/视觉/Embedding 三类 OpenAI 兼容配置。API Key 加密保存,界面脱敏(清单16)。
          </p>
          <button onClick={create} className="px-4 py-2 bg-brand-500 text-white rounded-lg text-sm hover:bg-brand-600">
            + 新建配置
          </button>
        </div>

        {items.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
            暂无模型配置。请新建一个文本/视觉/Embedding 配置以启用 AI 理解与语义检索。
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((m) => (
              <div key={m.id} className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-gray-800">{m.name}</span>
                      <span className="text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded">
                        {CAP_LABELS[m.capability] || m.capability}
                      </span>
                      {m.is_default && (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">默认</span>
                      )}
                      {!m.is_enabled && (
                        <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">已停用</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 space-y-0.5">
                      <div>Base URL:{m.base_url || "-"}</div>
                      <div>模型:{m.model || "-"}</div>
                      <div>API Key:{m.api_key_masked || "(未设)"}</div>
                      <div>
                        发图:{m.allow_send_raw_image ? "✓" : "✗"} · 发文:
                        {m.allow_send_raw_text ? "✓" : "✗"}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5 items-end">
                    <button
                      onClick={() => test(m)}
                      disabled={busy === m.id}
                      className="px-3 py-1 text-xs border border-brand-200 text-brand-600 rounded hover:bg-brand-50 disabled:opacity-50"
                    >
                      {busy === m.id ? "测试中..." : "连接测试"}
                    </button>
                    <button
                      onClick={() => toggleDefault(m)}
                      className={`px-3 py-1 text-xs rounded ${
                        m.is_default
                          ? "text-gray-400"
                          : "text-brand-600 border border-brand-200 hover:bg-brand-50"
                      }`}
                    >
                      {m.is_default ? "已是默认" : "设为默认"}
                    </button>
                    <button
                      onClick={() => remove(m)}
                      className="px-3 py-1 text-xs text-red-500 hover:underline"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
