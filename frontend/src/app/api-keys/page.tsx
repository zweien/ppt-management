"use client";

import { useEffect, useState } from "react";
import { KeyRound, Plus, Trash2, Copy, Check } from "lucide-react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import Modal, { ConfirmFooter } from "@/components/ui/Modal";
import { Table, THead, TH, TBody, TR, TD } from "@/components/ui/DataTable";
import { useToast } from "@/components/ui/Toast";

interface ApiKeyRow {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

interface CreatedKey extends ApiKeyRow {
  full_key: string;
}

export default function ApiKeysPage() {
  const toast = useToast();
  const [items, setItems] = useState<ApiKeyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CreatedKey | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiKeyRow | null>(null);
  const [revoking, setRevoking] = useState(false);
  const [copied, setCopied] = useState(false);

  async function load() {
    try {
      setItems(await api.get<ApiKeyRow[]>("/api/api-keys"));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function create() {
    if (!name.trim()) {
      toast.error("请填写用途名称");
      return;
    }
    setCreating(true);
    try {
      const k = await api.post<CreatedKey>("/api/api-keys", { name: name.trim() });
      setCreated(k);
      setName("");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function revoke() {
    if (!revokeTarget) return;
    setRevoking(true);
    try {
      await api.delete(`/api/api-keys/${revokeTarget.id}`);
      toast.success("已撤销");
      setRevokeTarget(null);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "撤销失败");
    } finally {
      setRevoking(false);
    }
  }

  async function copyKey() {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.full_key);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("复制失败,请手动选择复制");
    }
  }

  return (
    <AppShell>
      <div className="space-y-5 max-w-3xl">
        <div>
          <h1 className="text-xl font-semibold text-ink">API 密钥</h1>
          <p className="text-sm text-mute mt-1">
            供外部 AI agent / 脚本调用开放接口(如拼 PPT <code className="text-xs">POST /api/compose</code>)的机器认证。
            请求头带 <code className="text-xs">X-API-Key</code>。完整密钥仅创建时显示一次,请立即保存。
          </p>
        </div>

        {/* 创建 */}
        <div className="bg-surface rounded-md shadow-e2 p-4 flex items-center gap-2">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="用途名称,如:AI 拼 PPT agent"
            inputSize="sm"
            className="flex-1"
            onKeyDown={(e) => e.key === "Enter" && create()}
          />
          <Button variant="primary" size="sm" leadingIcon={<Plus className="w-3.5 h-3.5" />} onClick={create} loading={creating}>
            创建密钥
          </Button>
        </div>

        {/* 列表 */}
        {loading ? (
          <div className="text-mute text-sm">加载中...</div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<KeyRound className="w-5 h-5" />}
            title="暂无 API 密钥"
            description="创建一个密钥,让外部 AI 可以调用拼 PPT 等开放接口。"
          />
        ) : (
          <div className="bg-surface rounded-md shadow-e2 overflow-hidden">
            <Table>
              <THead>
                <TR>
                  <TH>名称</TH>
                  <TH>密钥前缀</TH>
                  <TH>创建时间</TH>
                  <TH>最近使用</TH>
                  <TH className="w-20">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((k) => (
                  <TR key={k.id}>
                    <TD className="font-medium">{k.name}</TD>
                    <TD>
                      <code className="text-xs text-mute">{k.key_prefix}…</code>
                    </TD>
                    <TD className="text-mute text-xs">{new Date(k.created_at).toLocaleString("zh-CN")}</TD>
                    <TD className="text-mute text-xs">
                      {k.last_used_at ? new Date(k.last_used_at).toLocaleString("zh-CN") : "从未使用"}
                    </TD>
                    <TD>
                      <button
                        onClick={() => setRevokeTarget(k)}
                        className="text-mute hover:text-error-deep transition"
                        title="撤销"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        )}

        {/* 创建成功:展示完整 key(仅一次) */}
        <Modal open={!!created} onClose={() => setCreated(null)} title="密钥已创建">
          {created && (
            <div className="space-y-3">
              <p className="text-sm text-body">
                请立即复制保存完整密钥。<span className="text-error-deep font-medium">它只显示这一次</span>,关闭后无法再次查看。
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-canvas border border-hairline rounded-sm px-3 py-2 break-all select-all">
                  {created.full_key}
                </code>
                <Button variant="secondary" size="sm" onClick={copyKey}
                  leadingIcon={copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}>
                  {copied ? "已复制" : "复制"}
                </Button>
              </div>
              <div className="text-xs text-mute space-y-1">
                <p>调用示例:</p>
                <code className="block bg-canvas border border-hairline rounded-sm px-3 py-2 whitespace-pre-wrap break-all">
{`curl -X POST ${typeof window !== "undefined" ? window.location.origin : ""}/api/compose \\
  -H "X-API-Key: ${created.full_key.slice(0, 12)}..." \\
  -H "Content-Type: application/json" \\
  -d '{"title":"汇报","outline":[{"section":"封面","query":"项目介绍"}]}'`}
                </code>
              </div>
            </div>
          )}
        </Modal>

        {/* 撤销确认 */}
        <Modal open={!!revokeTarget} onClose={() => setRevokeTarget(null)} title="撤销密钥">
          {revokeTarget && (
            <div className="space-y-3">
              <p className="text-sm text-body">
                确定撤销密钥「{revokeTarget.name}」({revokeTarget.key_prefix}…)吗?
                使用它的调用方将立即失效,此操作不可恢复。
              </p>
              <ConfirmFooter
                onCancel={() => setRevokeTarget(null)}
                onConfirm={revoke}
                confirmText="撤销"
                loading={revoking}
                destructive
              />
            </div>
          )}
        </Modal>
      </div>
    </AppShell>
  );
}
