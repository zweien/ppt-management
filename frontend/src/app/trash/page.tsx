"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";

interface Presentation { id: string; title: string; page_count: number; created_at: string; deleted_at: string; }

export default function TrashPage() {
  const [items, setItems] = useState<Presentation[]>([]);
  const [msg, setMsg] = useState("");

  async function load() {
    try { setItems(await api.get<Presentation[]>(`/api/presentations?include_deleted=true`)); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "加载失败"); }
  }
  useEffect(() => { load(); }, []);

  async function restore(id: string) {
    try { await api.post(`/api/presentations/${id}/restore`); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "恢复失败"); }
  }

  const deleted = items.filter((p) => p.deleted_at);

  return (
    <AppShell title="回收站">
      <div className="space-y-4">
        {msg && <div className="text-sm text-red-600">{msg}</div>}
        <p className="text-xs text-gray-400">软删除的文件在此可恢复。索引立即不可见,对象延迟清理。</p>
        {deleted.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">回收站为空</div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs uppercase"><tr>
                <th className="text-left px-4 py-3">文件名</th>
                <th className="text-left px-4 py-3">页数</th>
                <th className="text-left px-4 py-3">删除时间</th>
                <th className="text-right px-4 py-3">操作</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-100">
                {deleted.map((p) => (
                  <tr key={p.id}>
                    <td className="px-4 py-3 text-gray-500">{p.title}</td>
                    <td className="px-4 py-3 text-gray-500">{p.page_count}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{new Date(p.deleted_at).toLocaleString("zh-CN")}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => restore(p.id)} className="text-brand-600 hover:underline text-xs">恢复</button>
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
