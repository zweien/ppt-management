"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";

interface Tag { id: string; name: string; category: string | null; source: string; status: string; }

export default function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    try { setTags(await api.get<Tag[]>(`/api/tags`)); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "加载失败"); }
  }
  useEffect(() => { load(); }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.post(`/api/tags`, { name: name.trim(), category: category.trim() || null });
      setName(""); setCategory(""); await load();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "创建失败"); }
  }

  async function toggleStatus(t: Tag) {
    const next = t.status === "active" ? "disabled" : "active";
    try { await api.patch(`/api/tags/${t.id}`, { status: next }); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "操作失败"); }
  }

  return (
    <AppShell title="标签管理">
      <div className="max-w-3xl space-y-6">
        {msg && <div className="text-sm text-red-600">{msg}</div>}
        <form onSubmit={create} className="bg-white rounded-xl border border-gray-200 p-5 flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="标签名"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="分类(如:主题/用途)"
            className="w-48 px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          <button type="submit" className="px-4 py-2 bg-brand-500 text-white rounded-lg text-sm hover:bg-brand-600">新建</button>
        </form>
        <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
          {tags.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">暂无标签</div>
          ) : tags.map((t) => (
            <div key={t.id} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3">
                <span className={`px-2 py-0.5 rounded text-xs ${t.status === "active" ? "bg-brand-100 text-brand-700" : "bg-gray-100 text-gray-400"}`}>
                  {t.name}
                </span>
                {t.category && <span className="text-xs text-gray-400">{t.category}</span>}
                <span className="text-xs text-gray-300">{t.source}</span>
              </div>
              <button onClick={() => toggleStatus(t)} className="text-xs text-gray-500 hover:text-brand-600">
                {t.status === "active" ? "停用" : "启用"}
              </button>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
