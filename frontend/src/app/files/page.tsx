"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { UploadCloud, FileText, RefreshCw, Trash2, Eye, Search, Lock, Users, Pencil } from "lucide-react";
import AppShell from "@/components/AppShell";
import UploadQueue from "@/components/UploadQueue";
import { api, ApiError } from "@/lib/api";
import { presStatus } from "@/lib/status";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Badge } from "@/components/ui/Badge";
import { Input, Select } from "@/components/ui/Input";
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
  visibility?: string;
  folder_id?: string | null;
  owner_id?: string;
  owner_name?: string | null;
}

interface Folder {
  id: string;
  name: string;
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
  const [folders, setFolders] = useState<Folder[]>([]);
  // 筛选/排序/搜索
  const [searchQ, setSearchQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [folderFilter, setFolderFilter] = useState("");
  const [visibilityFilter, setVisibilityFilter] = useState("");
  const [sortBy, setSortBy] = useState("created");
  const [mineOnly, setMineOnly] = useState(false);
  // 重命名
  const [renameTarget, setRenameTarget] = useState<Presentation | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameLoading, setRenameLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const enqueueRef = useRef<((files: FileList | File[]) => void) | null>(null);

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("include_deleted", String(includeDeleted));
      if (searchQ) params.set("q", searchQ);
      if (statusFilter) params.set("status", statusFilter);
      if (folderFilter) params.set("folder_id", folderFilter);
      if (visibilityFilter) params.set("visibility", visibilityFilter);
      if (mineOnly) params.set("mine", "true");
      params.set("sort", sortBy);
      setItems(await api.get<Presentation[]>(`/api/presentations?${params}`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadFolders() {
    try { setFolders(await api.get<Folder[]>(`/api/folders`)); }
    catch { /* 忽略 */ }
  }

  const hasProcessing = items.some(
    (p) => p.parse_progress != null || ["PARSING", "RENDERING", "ENRICHING", "UPLOADING", "VALIDATING"].includes(p.current_status || ""),
  );

  useEffect(() => {
    load();
    loadFolders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeDeleted]);

  // 筛选/排序变化时重新加载
  useEffect(() => {
    const t = setTimeout(load, 300); // debounce
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQ, statusFilter, folderFilter, visibilityFilter, sortBy, mineOnly]);

  async function toggleVisibility(p: Presentation) {
    const next = p.visibility === "private" ? "team" : "private";
    try {
      await api.patch(`/api/presentations/${p.id}`, { visibility: next });
      toast.success(next === "private" ? "已设为私有" : "已设为团队共享");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  async function moveFolder(p: Presentation, folderId: string) {
    try {
      await api.patch(`/api/presentations/${p.id}`, { folder_id: folderId || null });
      toast.success("已移动");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "移动失败");
    }
  }

  async function startRename(p: Presentation) {
    setRenameTarget(p);
    setRenameValue(p.title);
  }

  async function confirmRename() {
    if (!renameTarget) return;
    setRenameLoading(true);
    try {
      await api.patch(`/api/presentations/${renameTarget.id}`, { title: renameValue.trim() });
      toast.success("已重命名");
      setRenameTarget(null);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "重命名失败");
    } finally {
      setRenameLoading(false);
    }
  }

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
              accept=".pptx,.ppt,.pdf"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) handleFiles(e.target.files);
                if (fileRef.current) fileRef.current.value = "";
              }}
            />
          </div>
          <p className="text-xs text-mute mt-3">支持 .pptx / .ppt / .pdf(ppt 与 pdf 通过渲染 + OCR 处理,单页 PPTX 导出仅限 .pptx)。完全相同文件将提示重复。</p>
        </div>

        {/* List header + 筛选栏 */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="text-sm font-medium text-body">
            文件列表 {includeDeleted ? "(含回收站)" : ""} · {items.length}
          </h2>
          <Checkbox
            checked={includeDeleted}
            onChange={(e) => setIncludeDeleted(e.target.checked)}
            label="显示已删除"
          />
        </div>

        {/* 筛选/排序/搜索栏 */}
        <div className="bg-surface rounded-md shadow-e2 p-3 space-y-2">
          {/* 搜索框占满一行 */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-mute pointer-events-none" />
            <Input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder="搜索文件名..."
              inputSize="sm"
              className="pl-9"
            />
          </div>
          {/* 下拉菜单 + checkbox 放一行,不换行。每个下拉用外层 div 限宽(Select 内部 w-full 填满)。 */}
          <div className="flex items-center gap-2 flex-nowrap overflow-x-auto">
            <div className="w-28 shrink-0">
              <Select inputSize="sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">全部状态</option>
                <option value="READY">就绪</option>
                <option value="PARSING">解析中</option>
                <option value="RENDERING">渲染中</option>
                <option value="PARTIAL_FAILED">失败</option>
              </Select>
            </div>
            <div className="w-36 shrink-0">
              <Select inputSize="sm" value={folderFilter} onChange={(e) => setFolderFilter(e.target.value)}>
                <option value="">全部文件夹</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </Select>
            </div>
            <div className="w-28 shrink-0">
              <Select inputSize="sm" value={visibilityFilter} onChange={(e) => setVisibilityFilter(e.target.value)}>
                <option value="">全部可见性</option>
                <option value="team">团队</option>
                <option value="private">私有</option>
              </Select>
            </div>
            <div className="w-28 shrink-0">
              <Select inputSize="sm" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                <option value="created">上传时间</option>
                <option value="page_count">页数</option>
                <option value="title">标题</option>
              </Select>
            </div>
            <div className="shrink-0">
              <Checkbox checked={mineOnly} onChange={(e) => setMineOnly(e.target.checked)} label="仅我上传的" />
            </div>
          </div>
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
              <TH>上传者</TH>
              <TH>可见性</TH>
              <TH>文件夹</TH>
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
                const isPrivate = p.visibility === "private";
                return (
                  <TR key={p.id}>
                    <TD>
                      <div className="flex items-center gap-1.5">
                        {p.deleted_at ? (
                          <span className="text-mute line-through">{p.title}</span>
                        ) : (
                          <Link href={`/files/${p.id}`} className="text-link hover:link-deep font-medium">
                            {p.title}
                          </Link>
                        )}
                        {!p.deleted_at && (
                          <button onClick={() => startRename(p)} className="text-mute hover:text-ink opacity-0 group-hover:opacity-100" title="重命名">
                            <Pencil className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </TD>
                    <TD className="text-mute text-xs whitespace-nowrap">{p.owner_name || "—"}</TD>
                    <TD>
                      {!p.deleted_at && (
                        <button
                          onClick={() => toggleVisibility(p)}
                          className={cn("inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full border transition",
                            isPrivate ? "text-warning-deep border-warning/30 bg-warning-soft" : "text-success-deep border-success/30 bg-success-soft")}
                          title={isPrivate ? "私有(仅你可见),点击切团队" : "团队共享,点击切私有"}
                        >
                          {isPrivate ? <Lock className="w-3 h-3" /> : <Users className="w-3 h-3" />}
                          {isPrivate ? "私有" : "团队"}
                        </button>
                      )}
                    </TD>
                    <TD>
                      {!p.deleted_at && (
                        <select
                          value={p.folder_id || ""}
                          onChange={(e) => moveFolder(p, e.target.value)}
                          className="text-xs bg-transparent border border-hairline rounded-sm h-7 px-1 text-body cursor-pointer"
                          title="移动到文件夹"
                        >
                          <option value="">—</option>
                          {folders.map((f) => (
                            <option key={f.id} value={f.id}>{f.name}</option>
                          ))}
                        </select>
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

      {/* Rename modal */}
      <Modal
        open={!!renameTarget}
        onClose={() => setRenameTarget(null)}
        title="重命名"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setRenameTarget(null)} disabled={renameLoading}>取消</Button>
            <Button variant="primary" onClick={confirmRename} loading={renameLoading}>保存</Button>
          </>
        }
      >
        <Input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} inputSize="md" autoFocus onKeyDown={(e) => e.key === "Enter" && confirmRename()} />
      </Modal>
    </AppShell>
  );
}
