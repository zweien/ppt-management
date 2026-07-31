"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  UploadCloud,
  X,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api, API_BASE } from "@/lib/api";
import { computeSha256, validateFile, formatSize } from "@/lib/upload";
import { fetchUploadLimits } from "@/lib/version";
import type { UploadLimits } from "@/lib/version";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import Modal, { ConfirmFooter } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

type TaskStatus =
  | "queued" // 等待并发槽位
  | "hashing" // 计算 SHA-256
  | "checking" // 预检查重
  | "awaiting-duplicate" // 命中重复,等待用户确认
  | "uploading"
  | "done"
  | "error"
  | "cancelled";

interface UploadTask {
  id: string;
  file: File;
  status: TaskStatus;
  progress: number; // 0-100
  error?: string;
  // 重复确认信息
  duplicateTitle?: string;
  duplicateId?: string;
  // XHR 引用,用于取消
  xhr?: XMLHttpRequest;
}

const MAX_CONCURRENT = 3;

interface UploadQueueProps {
  /** 受控:暴露一个入队函数给父组件。父组件通过 ref 调用。 */
  registerEnqueue?: (fn: (files: FileList | File[]) => void) => void;
  /** 任一文件完成时回调(供父组件刷新文件列表)。 */
  onAnyDone?: () => void;
}

export default function UploadQueue({ registerEnqueue, onAnyDone }: UploadQueueProps) {
  const toast = useToast();
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [limits, setLimits] = useState<UploadLimits | null>(null);
  // Duplicate-confirm modal state.
  const [confirmTask, setConfirmTask] = useState<UploadTask | null>(null);

  // Keep a ref to tasks so the concurrency pump reads fresh state.
  const tasksRef = useRef<UploadTask[]>([]);
  tasksRef.current = tasks;
  const onAnyDoneRef = useRef(onAnyDone);
  onAnyDoneRef.current = onAnyDone;

  useEffect(() => {
    fetchUploadLimits().then(setLimits);
  }, []);

  const updateTask = useCallback((id: string, patch: Partial<UploadTask>) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const removeTask = useCallback((id: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== id));
  }, []);

  /** Actually upload a file via XHR (single attempt). */
  const doUpload = useCallback(
    (task: UploadTask) => {
      updateTask(task.id, { status: "uploading", progress: 0, error: undefined });
      const form = new FormData();
      form.append("file", task.file);
      const xhr = new XMLHttpRequest();
      updateTask(task.id, { xhr });
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          updateTask(task.id, { progress: Math.round((e.loaded / e.total) * 100) });
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          let isDup = false;
          try {
            const res = JSON.parse(xhr.responseText);
            isDup = !!res.is_duplicate;
          } catch {
            /* */
          }
          updateTask(task.id, { status: "done", progress: 100 });
          toast.success(isDup ? `${task.file.name}(已存在)` : `${task.file.name} 上传成功`);
          onAnyDoneRef.current?.();
        } else {
          let detail = `HTTP ${xhr.status}`;
          try {
            detail = JSON.parse(xhr.responseText).detail || detail;
          } catch {
            /* */
          }
          updateTask(task.id, { status: "error", error: detail });
        }
        pump();
      };
      xhr.onerror = () => {
        updateTask(task.id, { status: "error", error: "网络错误" });
        pump();
      };
      xhr.onabort = () => {
        updateTask(task.id, { status: "cancelled" });
        pump();
      };
      xhr.open("POST", `${API_BASE}/api/uploads`);
      xhr.withCredentials = true; // 带 session cookie(SSO)
      xhr.send(form);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [updateTask],
  );

  /** Process one task: hash → check → (duplicate? await) → upload. */
  const processTask = useCallback(
    async (task: UploadTask) => {
      // Hash(crypto.subtle 仅 secure context 可用:HTTPS 或 localhost)。
      // 非 HTTPS 局域网(如 http://192.168.x.x)下 crypto.subtle 为 undefined →
      // 跳过客户端哈希与预检,直接上传;后端 process_upload 仍会精确查重(sha256)。
      updateTask(task.id, { status: "hashing", progress: 0 });
      const sha = await computeSha256(task.file);
      if (sha) {
        // Check duplicate(仅当能算哈希时)
        updateTask(task.id, { status: "checking" });
        try {
          const check = await api.post<{ exists: boolean; presentation: { id: string; title: string } | null }>(
            `/api/uploads/check`,
            { sha256: sha, size: task.file.size },
          );
          if (check.exists && check.presentation) {
            updateTask(task.id, {
              status: "awaiting-duplicate",
              duplicateTitle: check.presentation.title,
              duplicateId: check.presentation.id,
            });
            return; // wait for user decision; does not consume a slot
          }
        } catch {
          /* check 失败不阻断,继续上传 */
        }
      }
      doUpload({ ...task });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [doUpload, updateTask],
  );

  /** Concurrency pump: start queued tasks up to MAX_CONCURRENT active. */
  const pump = useCallback(() => {
    const cur = tasksRef.current;
    const active = cur.filter(
      (t) => t.status === "uploading" || t.status === "hashing" || t.status === "checking",
    ).length;
    if (active >= MAX_CONCURRENT) return;
    const next = cur.find((t) => t.status === "queued");
    if (next) {
      // optimistically mark to avoid double-pick; processTask will set hashing
      updateTask(next.id, { status: "hashing" });
      processTask({ ...next, status: "hashing" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processTask, updateTask]);

  /** Enqueue files (exposed to parent). */
  const enqueue = useCallback(
    (files: FileList | File[]) => {
      const arr = Array.from(files);
      if (!limits) return;
      for (const f of arr) {
        const v = validateFile(f, limits);
        if (!v.ok) {
          toast.error(`${f.name}:${v.error}`);
          continue;
        }
        const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const task: UploadTask = { id, file: f, status: "queued", progress: 0 };
        setTasks((prev) => [...prev, task]);
      }
      // pump after state settles
      setTimeout(pump, 0);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [limits, pump],
  );

  useEffect(() => {
    if (registerEnqueue) registerEnqueue(enqueue);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enqueue]);

  function cancelTask(t: UploadTask) {
    if (t.xhr) t.xhr.abort();
    else updateTask(t.id, { status: "cancelled" });
  }

  // Duplicate-confirm handlers
  function confirmDuplicateUpload() {
    if (!confirmTask) return;
    const t = { ...confirmTask, status: "queued" as TaskStatus };
    updateTask(confirmTask.id, { status: "queued", duplicateTitle: undefined });
    setConfirmTask(null);
    setTimeout(pump, 0);
    void t;
  }
  function dismissDuplicate() {
    if (!confirmTask) return;
    removeTask(confirmTask.id);
    setConfirmTask(null);
  }

  // auto-hide empty
  const visible = tasks.length > 0;
  const activeCount = tasks.filter(
    (t) => t.status === "uploading" || t.status === "hashing" || t.status === "checking" || t.status === "queued",
  ).length;
  const doneCount = tasks.filter((t) => t.status === "done").length;

  if (!visible) return null;

  return (
    <>
      <div className="fixed bottom-4 right-4 z-50 w-[380px] max-w-[calc(100vw-2rem)] bg-surface rounded-md shadow-e5 border border-hairline overflow-hidden animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between px-4 h-11 border-b border-hairline bg-canvas-soft">
          <div className="flex items-center gap-2 text-sm font-medium text-ink">
            <UploadCloud className="w-4 h-4" />
            上传队列
            <span className="text-xs text-mute font-mono">
              {activeCount > 0 ? `${doneCount}/${tasks.length}` : `${tasks.length} 项`}
            </span>
          </div>
          <button
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "展开" : "折叠"}
            className="text-mute hover:text-ink p-1 rounded-md hover:bg-canvas-soft-2"
          >
            {collapsed ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>

        {/* List */}
        {!collapsed && (
          <div className="max-h-[340px] overflow-y-auto divide-y divide-hairline">
            {tasks.map((t) => (
              <TaskRow key={t.id} task={t} onCancel={() => cancelTask(t)} onRemove={() => removeTask(t.id)} onForceUpload={() => doUpload(t)} />
            ))}
          </div>
        )}
      </div>

      <Modal
        open={!!confirmTask}
        onClose={dismissDuplicate}
        title="文件已存在"
        description={
          confirmTask?.duplicateTitle
            ? `《${confirmTask.duplicateTitle}》已有相同内容(SHA-256 一致)。`
            : ""
        }
        size="sm"
        footer={
          <ConfirmFooter
            confirmText="仍上传"
            cancelText="取消"
            onCancel={dismissDuplicate}
            onConfirm={confirmDuplicateUpload}
          />
        }
      >
        <p className="text-sm text-body">
          重复上传不会创建新文件,后端将返回已存在的记录。是否继续?
        </p>
      </Modal>
    </>
  );
}

function TaskRow({
  task,
  onCancel,
  onRemove,
  onForceUpload,
}: {
  task: UploadTask;
  onCancel: () => void;
  onRemove: () => void;
  onForceUpload: () => void;
}) {
  const { file, status, progress, error } = task;
  const busy = status === "queued" || status === "hashing" || status === "checking" || status === "uploading";

  const statusLabel: Record<TaskStatus, string> = {
    queued: "等待中",
    hashing: "计算哈希",
    checking: "查重中",
    "awaiting-duplicate": "待确认",
    uploading: `上传中 ${progress}%`,
    done: "完成",
    error: "失败",
    cancelled: "已取消",
  };

  return (
    <div className="px-4 py-3">
      <div className="flex items-center gap-2">
        <StatusIcon status={status} />
        <div className="min-w-0 flex-1">
          <div className="text-sm text-ink truncate" title={file.name}>
            {file.name}
          </div>
          <div className="text-xs text-mute flex items-center gap-2">
            <span>{formatSize(file.size)}</span>
            <span>·</span>
            <span className={cn(status === "error" && "text-error-deep", status === "done" && "text-success-deep")}>
              {statusLabel[status]}
            </span>
          </div>
        </div>
        <div className="shrink-0">
          {busy && (
            <button
              onClick={onCancel}
              aria-label="取消"
              className="text-mute hover:text-error p-1 rounded-md hover:bg-canvas-soft-2"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
          {!busy && (
            <button
              onClick={onRemove}
              aria-label="移除"
              className="text-mute hover:text-ink p-1 rounded-md hover:bg-canvas-soft-2"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
      {/* Progress bar while uploading */}
      {status === "uploading" && (
        <div className="mt-2 w-full h-1 bg-canvas-soft-2 rounded-full overflow-hidden">
          <div className="h-full bg-primary transition-all duration-200" style={{ width: `${progress}%` }} />
        </div>
      )}
      {/* Error detail */}
      {status === "error" && error && (
        <div className="mt-1.5 text-xs text-error-deep bg-error-soft rounded-sm px-2 py-1 break-all">{error}</div>
      )}
      {/* Duplicate confirmation inline action */}
      {status === "awaiting-duplicate" && (
        <div className="mt-2 flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={onForceUpload}>
            仍上传
          </Button>
          <Button size="sm" variant="ghost" onClick={onRemove}>
            跳过
          </Button>
        </div>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: TaskStatus }) {
  if (status === "done") return <CheckCircle2 className="w-4 h-4 text-success-deep shrink-0" />;
  if (status === "error") return <AlertCircle className="w-4 h-4 text-error-deep shrink-0" />;
  if (status === "cancelled") return <X className="w-4 h-4 text-mute shrink-0" />;
  if (status === "awaiting-duplicate") return <AlertCircle className="w-4 h-4 text-warning-deep shrink-0" />;
  return <Loader2 className="w-4 h-4 text-mute shrink-0 animate-spin-fast" />;
}
