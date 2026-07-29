"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";

interface Version {
  id: string; version_no: number; status: string; page_count: number;
  original_filename: string; file_size: number; created_at: string;
}
interface Presentation {
  id: string; title: string; page_count: number; current_version_id: string;
  current_status: string | null; created_at: string; versions: Version[];
  deleted_at: string | null;
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    BASIC_READY: "bg-green-100 text-green-700",
    READY: "bg-green-100 text-green-700",
    UPLOADING: "bg-blue-100 text-blue-700",
    PARSING: "bg-blue-100 text-blue-700",
    RENDERING: "bg-blue-100 text-blue-700",
    PARSED: "bg-blue-100 text-blue-700",
    PARTIAL_FAILED: "bg-red-100 text-red-700",
  };
  return map[status] || "bg-gray-100 text-gray-600";
}

export default function FilesPage() {
  const [items, setItems] = useState<Presentation[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState("");
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<Presentation[]>(`/api/presentations?include_deleted=${includeDeleted}`);
      setItems(data);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [includeDeleted]);

  async function handleUpload(file: File) {
    setUploading(true); setMsg("");
    try {
      // 先做版本候选建议(ADR-0008):若与已有文件相似,问用户是否作为新版本
      let parentId: string | undefined = undefined;
      try {
        const sForm = new FormData();
        sForm.append("file", file);
        const sug = await api.postForm<{ page_count: number; candidates: { presentation_id: string; title: string; similarity: number }[] }>(
          "/api/uploads/suggest-version", sForm
        );
        if (sug.candidates.length > 0) {
          const top = sug.candidates[0];
          const choice = confirm(
            `检测到与已有文件相似:\n\n《${top.title}》(相似度 ${(top.similarity * 100).toFixed(0)}%)\n\n确定 = 作为该文件的新版本(v)\n取消 = 作为全新文件上传`
          );
          if (choice) parentId = top.presentation_id;
        }
      } catch {
        /* 建议失败不阻断,按新文件上传 */
      }

      const form = new FormData();
      form.append("file", file);
      if (parentId) form.append("parent_presentation_id", parentId);
      const res = await api.postForm<{ message: string; is_duplicate: boolean }>("/api/uploads", form);
      setMsg(res.message + (parentId ? `(已关联为新版本)` : ""));
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("确认移入回收站?")) return;
    try {
      await api.delete(`/api/presentations/${id}`);
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "删除失败");
    }
  }

  async function handleRestore(id: string) {
    try {
      await api.post(`/api/presentations/${id}/restore`);
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "恢复失败");
    }
  }

  const [reparsingId, setReparsingId] = useState<string | null>(null);
  async function handleReparse(id: string) {
    setReparsingId(id);
    setMsg("");
    try {
      const r = await api.post<{ detail: string }>(`/api/presentations/${id}/reparse`);
      setMsg(`${r.detail}(可在任务中心查看进度)`);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "重新解析失败");
    } finally {
      setReparsingId(null);
    }
  }

  return (
    <AppShell title="文件管理">
      <div className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium text-gray-700">上传 PPTX</h2>
            <label className="px-4 py-2 bg-brand-500 text-white rounded-lg hover:bg-brand-600 cursor-pointer text-sm font-medium">
              {uploading ? "上传中..." : "选择文件上传"}
              <input
                ref={fileRef}
                type="file"
                accept=".pptx"
                className="hidden"
                disabled={uploading}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUpload(f);
                }}
              />
            </label>
          </div>
          <p className="text-xs text-gray-400">仅支持 .pptx(不支持 .ppt / 加密文件)。完全相同文件将提示重复。</p>
          {msg && <div className="mt-2 text-sm text-brand-600">{msg}</div>}
        </div>

        <div className="flex items-center justify-between">
          <h2 className="font-medium text-gray-700">
            文件列表 {includeDeleted ? "(含回收站)" : ""} ({items.length})
          </h2>
          <label className="flex items-center gap-2 text-sm text-gray-500">
            <input type="checkbox" checked={includeDeleted} onChange={(e) => setIncludeDeleted(e.target.checked)} />
            显示已删除
          </label>
        </div>

        {loading ? (
          <div className="text-gray-400 text-sm">加载中...</div>
        ) : items.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
            暂无文件,请上传一份 PPTX 开始
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">文件名</th>
                  <th className="text-left px-4 py-3">页数</th>
                  <th className="text-left px-4 py-3">状态</th>
                  <th className="text-left px-4 py-3">大小</th>
                  <th className="text-left px-4 py-3">上传时间</th>
                  <th className="text-right px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      {p.deleted_at ? (
                        <span className="text-gray-400 line-through">{p.title}</span>
                      ) : (
                        <Link href={`/files/${p.id}`} className="text-brand-600 hover:underline font-medium">
                          {p.title}
                        </Link>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{p.page_count}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${statusBadge(p.current_status || "")}`}>
                        {p.current_status || "-"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {p.versions[0] ? `${(p.versions[0].file_size / 1024).toFixed(0)} KB` : "-"}
                    </td>
                    <td className="px-4 py-3 text-gray-500">{new Date(p.created_at).toLocaleString("zh-CN")}</td>
                    <td className="px-4 py-3 text-right">
                      {p.deleted_at ? (
                        <button onClick={() => handleRestore(p.id)} className="text-brand-600 hover:underline text-xs">
                          恢复
                        </button>
                      ) : (
                        <div className="flex gap-2 justify-end">
                          <Link href={`/files/${p.id}`} className="text-brand-600 hover:underline text-xs">浏览</Link>
                          <button onClick={() => handleReparse(p.id)} disabled={reparsingId === p.id} className="text-brand-600 hover:underline text-xs disabled:opacity-50">
                            {reparsingId === p.id ? "提交中" : "重新解析"}
                          </button>
                          <button onClick={() => handleDelete(p.id)} className="text-red-500 hover:underline text-xs">删除</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
