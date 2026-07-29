"use client";

import { useEffect, useState } from "react";
import { Plus, Cpu, Plug, Trash2, Star } from "lucide-react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import Button from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input, Field, Select } from "@/components/ui/Input";
import EmptyState from "@/components/ui/EmptyState";
import Modal, { ConfirmFooter } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

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
  const toast = useToast();
  const [items, setItems] = useState<ModelConfig[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  // Create modal state.
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", capability: "vision", base_url: "https://api.openai.com", model: "", api_key: "" });
  const [creating, setCreating] = useState(false);

  // Delete confirm state.
  const [deleteTarget, setDeleteTarget] = useState<ModelConfig | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    try {
      setItems(await api.get<ModelConfig[]>(`/api/model-configs`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function create() {
    if (!form.name.trim()) {
      toast.error("请填写配置名称");
      return;
    }
    setCreating(true);
    try {
      await api.post(`/api/model-configs`, {
        name: form.name.trim(),
        capability: form.capability,
        base_url: form.base_url,
        model: form.model,
        api_key: form.api_key || undefined,
        is_enabled: true,
      });
      toast.success("已创建");
      setShowCreate(false);
      setForm({ name: "", capability: "vision", base_url: "https://api.openai.com", model: "", api_key: "" });
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function toggleDefault(m: ModelConfig) {
    try {
      await api.post(`/api/model-configs/${m.id}/set-default`);
      toast.success("已设为默认");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  async function test(m: ModelConfig) {
    setBusy(m.id);
    try {
      const r = await api.post<{
        success: boolean;
        latency_ms: number;
        model_returned: string | null;
        error: string | null;
        sample: string | null;
      }>(`/api/model-configs/${m.id}/test`);
      if (r.success) {
        toast.success(`测试成功 · ${r.latency_ms}ms · 模型:${r.model_returned || "-"}`);
      } else {
        toast.error(`测试失败:${r.error}`);
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "测试失败");
    } finally {
      setBusy(null);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/api/model-configs/${deleteTarget.id}`);
      toast.success("已删除");
      setDeleteTarget(null);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AppShell title="模型配置">
      <div className="max-w-4xl space-y-5">
        <div className="flex justify-between items-center gap-4 flex-wrap">
          <p className="text-xs text-mute max-w-xl">
            文本/视觉/Embedding 三类 OpenAI 兼容配置。API Key 加密保存,界面脱敏。
          </p>
          <Button variant="primary" leadingIcon={<Plus className="w-3.5 h-3.5" />} onClick={() => setShowCreate(true)}>
            新建配置
          </Button>
        </div>

        {items.length === 0 ? (
          <EmptyState
            icon={<Cpu className="w-5 h-5" />}
            title="暂无模型配置"
            description="新建一个文本/视觉/Embedding 配置以启用 AI 理解与语义检索。"
            action={<Button variant="primary" leadingIcon={<Plus className="w-3.5 h-3.5" />} onClick={() => setShowCreate(true)}>新建配置</Button>}
          />
        ) : (
          <div className="space-y-3">
            {items.map((m) => (
              <div key={m.id} className="bg-surface rounded-md shadow-e2 p-4">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className="font-medium text-ink">{m.name}</span>
                      <Badge tone="info">{CAP_LABELS[m.capability] || m.capability}</Badge>
                      {m.is_default && (
                        <Badge tone="success" dot>
                          默认
                        </Badge>
                      )}
                      {!m.is_enabled && <Badge tone="default">已停用</Badge>}
                    </div>
                    <div className="text-xs text-mute space-y-1 font-mono">
                      <div>Base URL:{m.base_url || "-"}</div>
                      <div>模型:{m.model || "-"}</div>
                      <div>API Key:{m.api_key_masked || "(未设)"}</div>
                      <div>
                        发图:{m.allow_send_raw_image ? "✓" : "✗"} · 发文:{m.allow_send_raw_text ? "✓" : "✗"}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5 items-end shrink-0">
                    <Button size="sm" variant="secondary" loading={busy === m.id} onClick={() => test(m)} leadingIcon={<Plug className="w-3.5 h-3.5" />}>
                      连接测试
                    </Button>
                    <Button
                      size="sm"
                      variant={m.is_default ? "ghost" : "secondary"}
                      disabled={m.is_default}
                      leadingIcon={<Star className="w-3.5 h-3.5" fill={m.is_default ? "currentColor" : "none"} />}
                      onClick={() => toggleDefault(m)}
                    >
                      {m.is_default ? "已是默认" : "设为默认"}
                    </Button>
                    <Button size="sm" variant="ghost" className="text-error-deep hover:text-error" leadingIcon={<Trash2 className="w-3.5 h-3.5" />} onClick={() => setDeleteTarget(m)}>
                      删除
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create modal (replaces 3-step prompt) */}
      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="新建模型配置"
        description="配置一个 OpenAI 兼容的文本/视觉/Embedding 模型。"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowCreate(false)} disabled={creating}>
              取消
            </Button>
            <Button variant="primary" onClick={create} loading={creating}>
              创建
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="配置名称" htmlFor="m-name">
            <Input
              id="m-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如:内网视觉模型"
            />
          </Field>
          <Field label="能力类型">
            <Select value={form.capability} onChange={(e) => setForm({ ...form, capability: e.target.value })}>
              <option value="vision">视觉</option>
              <option value="text">文本</option>
              <option value="embedding">Embedding</option>
            </Select>
          </Field>
          <Field label="Base URL" htmlFor="m-base">
            <Input id="m-base" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.openai.com" />
          </Field>
          <Field label="模型" htmlFor="m-model">
            <Input id="m-model" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} placeholder="如 gpt-4o" />
          </Field>
          <Field label="API Key" hint="留空则不设;加密保存,界面脱敏。" htmlFor="m-key">
            <Input
              id="m-key"
              type="password"
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              placeholder="sk-..."
            />
          </Field>
        </div>
      </Modal>

      {/* Delete confirm */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="删除模型配置?"
        description={`《${deleteTarget?.name || ""}》将被永久删除。`}
        size="sm"
        footer={
          <ConfirmFooter
            destructive
            confirmText="删除"
            loading={deleting}
            onCancel={() => setDeleteTarget(null)}
            onConfirm={confirmDelete}
          />
        }
      />
    </AppShell>
  );
}
