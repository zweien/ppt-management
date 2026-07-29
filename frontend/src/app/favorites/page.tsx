"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";

interface Fav { id: string; page_no: number; title: string | null; thumbnail_url: string | null; }

export default function FavoritesPage() {
  const [items, setItems] = useState<Fav[]>([]);
  const [msg, setMsg] = useState("");

  async function load() {
    try { setItems(await api.get<Fav[]>(`/api/favorites`)); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "加载失败"); }
  }
  useEffect(() => { load(); }, []);

  async function remove(id: string) {
    try { await api.delete(`/api/favorites/${id}`); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "操作失败"); }
  }

  return (
    <AppShell title="我的收藏">
      <div className="space-y-4">
        {msg && <div className="text-sm text-red-600">{msg}</div>}
        {items.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">暂无收藏</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {items.map((s) => (
              <div key={s.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="aspect-video bg-gray-100 overflow-hidden">
                  {s.thumbnail_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={s.thumbnail_url} alt={`第${s.page_no}页`} className="w-full h-full object-contain" />
                  ) : <div className="w-full h-full flex items-center justify-center text-gray-300 text-sm">无预览</div>}
                </div>
                <div className="p-3 flex items-center justify-between">
                  <span className="text-sm text-gray-700 truncate">P{s.page_no} {s.title || ""}</span>
                  <button onClick={() => remove(s.id)} className="text-yellow-500 hover:text-yellow-600 text-sm">★</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
