"use client";

import { useEffect, useState } from "react";
import { Trash2, RotateCcw, AlertTriangle } from "lucide-react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Table, THead, TH, TBody, TR, TD } from "@/components/ui/DataTable";
import Modal, { ConfirmFooter } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

interface Presentation {
  id: string;
  title: string;
  page_count: number;
  created_at: string;
  deleted_at: string;
  owner_id?: string;
}

export default function TrashPage() {
  const toast = useToast();
  const [items, setItems] = useState<Presentation[]>([]);
  const [permTarget, setPermTarget] = useState<Presentation | null>(null);
  const [permLoading, setPermLoading] = useState(false);
  const [emptyLoading, setEmptyLoading] = useState(false);
  const [showEmpty, setShowEmpty] = useState(false);

  async function load() {
    try {
      setItems(await api.get<Presentation[]>(`/api/presentations?include_deleted=true`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const deleted = items.filter((p) => p.deleted_at);

  async function restore(id: string) {
    try {
      await api.post(`/api/presentations/${id}/restore`);
      toast.success("已恢复");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "恢复失败");
    }
  }

  async function permanentDelete() {
    if (!permTarget) return;
    setPermLoading(true);
    try {
      await api.delete(`/api/presentations/${permTarget.id}/permanent`);
      toast.success("已永久删除");
      setPermTarget(null);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "删除失败");
    } finally {
      setPermLoading(false);
    }
  }

  async function emptyTrash() {
    setEmptyLoading(true);
    try {
      const r = await api.delete<{ detail: string }>(`/api/trash/empty`);
      toast.success(r.detail);
      setShowEmpty(false);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "清空失败");
    } finally {
      setEmptyLoading(false);
    }
  }

  return (
    <AppShell title="回收站">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-xs text-mute">软删除的文件在此可恢复。永久删除不可恢复且会清理对象存储。</p>
          {deleted.length > 0 && (
            <Button variant="ghost" className="text-error-deep hover:text-error" leadingIcon={<Trash2 className="w-3.5 h-3.5" />} onClick={() => setShowEmpty(true)}>
              清空回收站({deleted.length})
            </Button>
          )}
        </div>
        {deleted.length === 0 ? (
          <EmptyState icon={<Trash2 className="w-5 h-5" />} title="回收站为空" description="删除的文件会暂存在这里,可以随时恢复。" />
        ) : (
          <Table>
            <THead>
              <TH>文件名</TH>
              <TH>页数</TH>
              <TH>删除时间</TH>
              <TH className="text-right">操作</TH>
            </THead>
            <TBody>
              {deleted.map((p) => (
                <TR key={p.id}>
                  <TD className="text-mute">{p.title}</TD>
                  <TD className="text-mute">{p.page_count}</TD>
                  <TD className="text-mute text-xs">{new Date(p.deleted_at).toLocaleString("zh-CN")}</TD>
                  <TD className="text-right">
                    <div className="inline-flex gap-1">
                      <Button size="sm" variant="secondary" leadingIcon={<RotateCcw className="w-3.5 h-3.5" />} onClick={() => restore(p.id)}>
                        恢复
                      </Button>
                      <Button size="sm" variant="ghost" className="text-error-deep hover:text-error" leadingIcon={<Trash2 className="w-3.5 h-3.5" />} onClick={() => setPermTarget(p)}>
                        永久删除
                      </Button>
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </div>

      {/* 永久删除确认 */}
      <Modal
        open={!!permTarget}
        onClose={() => setPermTarget(null)}
        title="永久删除?"
        description={`《${permTarget?.title || ""}》将被永久删除,包括对象存储中的所有文件。此操作不可恢复。`}
        size="sm"
        footer={
          <ConfirmFooter destructive confirmText="永久删除" loading={permLoading} onCancel={() => setPermTarget(null)} onConfirm={permanentDelete} />
        }
      >
        <div className="flex items-start gap-2 text-sm text-warning-deep bg-warning-soft rounded-sm p-3">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>删除后无法恢复。请确认。</span>
        </div>
      </Modal>

      {/* 清空回收站确认 */}
      <Modal
        open={showEmpty}
        onClose={() => setShowEmpty(false)}
        title="清空回收站?"
        description={`将永久删除回收站中的全部 ${deleted.length} 个文件(仅你有权删除的),清理对象存储。此操作不可恢复。`}
        size="sm"
        footer={
          <ConfirmFooter destructive confirmText="清空全部" loading={emptyLoading} onCancel={() => setShowEmpty(false)} onConfirm={emptyTrash} />
        }
      >
        <div className="flex items-start gap-2 text-sm text-warning-deep bg-warning-soft rounded-sm p-3">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>清空后无法恢复。请确认。</span>
        </div>
      </Modal>
    </AppShell>
  );
}
