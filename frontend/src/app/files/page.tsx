"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { UploadCloud, FileText, RefreshCw, Trash2, Eye } from "lucide-react";
import AppShell from "@/components/AppShell";
import UploadQueue from "@/components/UploadQueue";
import { api, ApiError } from "@/lib/api";
import { presStatus } from "@/lib/status";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Badge } from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import { Table, THead, TH, TBody, TR, TD } from "@/components/ui/DataTable";
import Modal, { ConfirmFooter } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

interface Version {
  id: string;
  version_no: number;
  status: string;
  page_count: number;
  original_filename: string;
  file_size: number;
  created_at: string;
}
interface Presentation {
  id: string;
  title: string;
  page_count: number;
  current_version_id: string;
  current_status: string | null;
  created_at: string;
  versions: Version[];
  deleted_at: string | null;
  parse_progress?: number | null;
  parse_stage?: string | null;
}

export default function FilesPage() {
  const toast = useToast();
  const [items, setItems] = useState<Presentation[]>([]);
  const [loading, setLoading] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [reparsingId, setReparsingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Presentation | null>(null);
  const [deleting, setDeleting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const enqueueRef = useRef<((files: FileList | File[]) => void) | null>(null);

  async function load() {
    setLoading(true);
    try {
      setItems(await api.get<Presentation[]>(`/api/presentations?include_deleted=${includeDeleted}`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  const hasProcessing = items.some(
    (p) => p.parse_progress != null || ["PARSING", "RENDERING", "ENRICHING", "UPLOADING", "VALIDATING"].includes(p.current_status || ""),
  );

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeDeleted]);

  // Poll faster (2s) while any file is still processing.
  useEffect(() => {
    if (!hasProcessing) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasProcessing]);

  function handleFiles(files: FileList | File[]) {
    enqueueRef.current?.(files);
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/api/presentations/${deleteTarget.id}`);
      toast.success("已移入回收站");
      setDeleteTarget(null);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  }

  async function handleRestore(id: string) {
    try {
      await api.post(`/api/presentations/${id}/restore`);
      toast.success("已恢复");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "恢复失败");
    }
  }

  async function handleReparse(id: string) {
    setReparsingId(id);
    try {
      const r = await api.post<{ detail: string }>(`/api/presentations/${id}/reparse`);
      toast.success(`${r.detail}(可在任务中心查看进度)`);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "重新解析失败");
    } finally {
      setReparsingId(null);
    }
  }

  return (
    <AppShell title="文件管理">
      <div className="space-y-6">
        {/* Upload dropzone */}
        <div className="bg-surface rounded-md shadow-e2 p-5">
          <div
            className={cn(
              "border-2 border-dashed rounded-md p-6 text-center transition",
              dragOver ? "border-link bg-link-soft" : "border-hairline-strong",
            )}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files);
            }}
          >
            <UploadCloud className="w-8 h-8 mx-auto mb-2 text-mute" />
            <div className="text-sm text-body mb-3">拖拽 PPTX 到此处,或点击选择文件(支持多选)</div>
            <Button variant="primary" size="md" onClick={() => fileRef.current?.click()}>
              选择文件上传
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".pptx"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) handleFiles(e.target.files);
                if (fileRef.current) fileRef.current.value = "";
              }}
            />
          </div>
          <p className="text-xs text-mute mt-3">仅支持 .pptx(不支持 .ppt / 加密文件)。完全相同文件将提示重复。</p>
        </div>

        {/* List header */}
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-body">
            文件列表 {includeDeleted ? "(含回收站)" : ""} · {items.length}
          </h2>
          <Checkbox
            checked={includeDeleted}
            onChange={(e) => setIncludeDeleted(e.target.checked)}
            label="显示已删除"
          />
        </div>

        {loading ? (
          <div className="text-mute text-sm">加载中...</div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<FileText className="w-5 h-5" />}
            title="暂无文件"
            description="上传一份 PPTX 开始,系统会自动解析、渲染与建立索引。"
          />
        ) : (
          <Table>
            <THead>
              <TH>文件名</TH>
              <TH>页数</TH>
              <TH>状态</TH>
              <TH>大小</TH>
              <TH>上传时间</TH>
              <TH className="text-right">操作</TH>
            </THead>
            <TBody>
              {items.map((p) => {
                const st = presStatus(p.current_status || "");
                const processing = p.parse_progress != null;
                return (
                  <TR key={p.id}>
                    <TD>
                      {p.deleted_at ? (
                        <span className="text-mute line-through">{p.title}</span>
                      ) : (
                        <Link href={`/files/${p.id}`} className="text-link hover:link-deep font-medium">
                          {p.title}
                        </Link>
                      )}
                    </TD>
                    <TD>{p.page_count}</TD>
                    <TD>
                      <div className="flex flex-col gap-1.5 min-w-[120px]">
                        <Badge tone={st.tone} dot>
                          {st.label}
                        </Badge>
                        {processing && (
                          <div className="w-full h-1 bg-canvas-soft-2 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-500"
                              style={{ width: `${Math.max(p.parse_progress || 0, 3)}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </TD>
                    <TD className="text-mute">
                      {p.versions[0] ? `${(p.versions[0].file_size / 1024).toFixed(0)} KB` : "-"}
                    </TD>
                    <TD className="text-mute text-xs">{new Date(p.created_at).toLocaleString("zh-CN")}</TD>
                    <TD className="text-right">
                      {p.deleted_at ? (
                        <Button size="sm" variant="ghost" onClick={() => handleRestore(p.id)}>
                          恢复
                        </Button>
                      ) : (
                        <div className="inline-flex gap-1">
                          <Link href={`/files/${p.id}`}>
                            <Button size="sm" variant="ghost" leadingIcon={<Eye className="w-3.5 h-3.5" />}>
                              浏览
                            </Button>
                          </Link>
                          <Button
                            size="sm"
                            variant="ghost"
                            loading={reparsingId === p.id}
                            onClick={() => handleReparse(p.id)}
                            leadingIcon={<RefreshCw className="w-3.5 h-3.5" />}
                          >
                            重新解析
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-error-deep hover:text-error"
                            leadingIcon={<Trash2 className="w-3.5 h-3.5" />}
                            onClick={() => setDeleteTarget(p)}
                          >
                            删除
                          </Button>
                        </div>
                      )}
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </div>

      {/* Upload queue (floating) */}
      <UploadQueue
        registerEnqueue={(fn) => {
          enqueueRef.current = fn;
        }}
        onAnyDone={load}
      />

      {/* Delete confirm */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="移入回收站?"
        description={`《${deleteTarget?.title || ""}》将被软删除,可在回收站恢复。`}
        size="sm"
        footer={
          <ConfirmFooter
            destructive
            confirmText="移入回收站"
            loading={deleting}
            onCancel={() => setDeleteTarget(null)}
            onConfirm={handleDelete}
          />
        }
      />
    </AppShell>
  );
}
