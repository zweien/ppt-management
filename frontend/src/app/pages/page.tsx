"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import SlideCard, { type SlideCardData } from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError } from "@/lib/api";

interface Tag {
  id: string;
  name: string;
  category: string | null;
}

export default function PagesPage() {
  const [slides, setSlides] = useState<SlideCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [active, setActive] = useState<SlideCardData | null>(null);

  // 批量选择(SL-03)
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [tags, setTags] = useState<Tag[]>([]);
  const [batchTagId, setBatchTagId] = useState("");

  async function load() {
    try {
      setSlides(await api.get<SlideCardData[]>(`/api/pages`));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    api.get<Tag[]>(`/api/tags`).then(setTags).catch(() => {});
  }, []);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function batchAddTag() {
    if (!batchTagId || selected.size === 0) {
      setMsg("请选择标签和至少一个页面");
      return;
    }
    try {
      await api.post(`/api/slides/batch-tags`, {
        slide_ids: [...selected],
        tag_id: batchTagId,
      });
      setMsg(`已为 ${selected.size} 个页面添加标签`);
      setSelected(new Set());
      setSelectMode(false);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  async function batchFavorite() {
    if (selected.size === 0) return;
    try {
      await api.post(`/api/favorites`, { slide_ids: [...selected] });
      setMsg(`已收藏 ${selected.size} 个页面`);
      setSelected(new Set());
      setSelectMode(false);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  return (
    <AppShell title="页面浏览">
      <div className="space-y-4">
        {msg && <div className="text-sm text-brand-600 bg-brand-50 px-3 py-2 rounded">{msg}</div>}

        {/* 批量操作工具栏 */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3 flex-wrap">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={selectMode}
              onChange={(e) => {
                setSelectMode(e.target.checked);
                setSelected(new Set());
              }}
            />
            批量选择模式
          </label>
          {selectMode && (
            <>
              <span className="text-sm text-gray-500">已选 {selected.size} 个</span>
              <select value={batchTagId} onChange={(e) => setBatchTagId(e.target.value)} className="border border-gray-300 rounded px-2 py-1 text-sm">
                <option value="">选择标签…</option>
                {tags.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <button
                onClick={batchAddTag}
                disabled={selected.size === 0 || !batchTagId}
                className="px-3 py-1 text-sm bg-brand-500 text-white rounded disabled:opacity-50"
              >
                批量加标签
              </button>
              <button
                onClick={batchFavorite}
                disabled={selected.size === 0}
                className="px-3 py-1 text-sm border border-yellow-300 text-yellow-600 rounded disabled:opacity-50"
              >
                批量收藏
              </button>
            </>
          )}
        </div>

        {loading ? (
          <div className="text-gray-400">加载中...</div>
        ) : slides.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
            暂无页面
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {slides.map((s) => (
              <div key={s.id} className="relative">
                {selectMode && (
                  <input
                    type="checkbox"
                    checked={selected.has(s.id)}
                    onChange={() => toggleSelect(s.id)}
                    className="absolute top-2 right-2 z-10 w-5 h-5"
                  />
                )}
                <div className={selected.has(s.id) ? "ring-2 ring-brand-400 rounded-xl" : ""}>
                  <SlideCard slide={s} onOpen={selectMode ? undefined : setActive} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <SlideDetailDrawer slide={active} onClose={() => setActive(null)} onMsg={setMsg} />
    </AppShell>
  );
}
