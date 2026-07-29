"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import SlideCard from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError } from "@/lib/api";

interface SlideCardData {
  id: string;
  page_no: number;
  title: string | null;
  native_text: string | null;
  thumbnail_url: string | null;
  presentation_title?: string | null;
  is_favorite?: boolean;
}
interface HitResult {
  slide: SlideCardData;
  score: number;
  hit_reasons: string[];
}
interface TagFacet {
  id: string;
  name: string;
  category: string | null;
  count: number;
}
interface PresGroup {
  id: string;
  title: string;
  slides: { id: string; page_no: number; title: string | null; thumbnail_url: string | null; hit_reasons: string[] }[];
}

const REASON_COLORS: Record<string, string> = {
  正文命中: "bg-blue-100 text-blue-700",
  语义相似: "bg-purple-100 text-purple-700",
  标题精确: "bg-brand-100 text-brand-700",
  标题匹配: "bg-brand-50 text-brand-600",
  文件名匹配: "bg-green-100 text-green-700",
  人工标签: "bg-orange-100 text-orange-700",
  "AI 标签": "bg-gray-100 text-gray-500",
  已收藏: "bg-yellow-100 text-yellow-700",
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HitResult[]>([]);
  const [groups, setGroups] = useState<PresGroup[]>([]);
  const [facets, setFacets] = useState<TagFacet[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [includeHistorical, setIncludeHistorical] = useState(false);
  const [sort, setSort] = useState("relevance");
  const [view, setView] = useState<"slides" | "presentations">("slides");
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [msg, setMsg] = useState("");
  const [active, setActive] = useState<SlideCardData | null>(null);

  const doSearch = useCallback(async () => {
    setLoading(true);
    setSearched(true);
    setMsg("");
    const tagParam = selectedTags.join(",");
    try {
      const [hits, gs, fc] = await Promise.all([
        api.get<HitResult[]>(
          `/api/search/slides?q=${encodeURIComponent(query)}&tag_ids=${tagParam}&favorite_only=${favoriteOnly}&include_historical=${includeHistorical}&sort=${sort}`
        ),
        api.get<PresGroup[]>(
          `/api/search/presentations?q=${encodeURIComponent(query)}&tag_ids=${tagParam}`
        ),
        api.get<TagFacet[]>(`/api/search/tag-facets?q=${encodeURIComponent(query)}`),
      ]);
      setResults(hits);
      setGroups(gs);
      setFacets(fc);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "搜索失败");
    } finally {
      setLoading(false);
    }
  }, [query, selectedTags, favoriteOnly, includeHistorical, sort]);

  useEffect(() => {
    doSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTags, favoriteOnly, sort]);

  function toggleTag(id: string) {
    setSelectedTags((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));
  }

  async function toggleFavorite(slide: SlideCardData) {
    const target = !slide.is_favorite;
    setResults((prev) =>
      prev.map((h) => (h.slide.id === slide.id ? { ...h, slide: { ...h.slide, is_favorite: target } } : h))
    );
    try {
      if (target) {
        await api.post(`/api/favorites`, { slide_ids: [slide.id] });
      } else {
        await api.delete(`/api/favorites/${slide.id}`);
      }
    } catch (e) {
      // 回滚
      setResults((prev) =>
        prev.map((h) => (h.slide.id === slide.id ? { ...h, slide: { ...h.slide, is_favorite: !target } } : h))
      );
      setMsg(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  function onDrawerToggleFav(slideId: string, isFav: boolean) {
    setResults((prev) =>
      prev.map((h) => (h.slide.id === slideId ? { ...h, slide: { ...h.slide, is_favorite: isFav } } : h))
    );
  }

  const facetsByCategory = facets.reduce<Record<string, TagFacet[]>>((acc, f) => {
    const key = f.category || "其他";
    (acc[key] ||= []).push(f);
    return acc;
  }, {});

  return (
    <AppShell title="搜索首页">
      <div className="max-w-6xl mx-auto">
        {/* search bar */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              placeholder="输入关键词或描述,如:无人系统总体架构、紫色科技风..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-400 focus:border-brand-400 outline-none"
            />
            <button onClick={doSearch} disabled={loading} className="px-6 py-3 bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50 font-medium">
              {loading ? "搜索中..." : "搜索"}
            </button>
          </div>
          <div className="mt-3 flex items-center justify-between flex-wrap gap-3">
            <div className="flex gap-2 flex-wrap">
              {["无人系统", "总体架构", "项目研究目标", "能力现状"].map((t) => (
                <button key={t} onClick={() => { setQuery(t); }} className="px-3 py-1 text-xs bg-brand-50 text-brand-600 rounded-full hover:bg-brand-100">
                  {t}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3 text-xs">
              <label className="flex items-center gap-1 text-gray-500">
                <input type="checkbox" checked={favoriteOnly} onChange={(e) => setFavoriteOnly(e.target.checked)} />
                仅看收藏
              </label>
              <label className="flex items-center gap-1 text-gray-500">
                <input type="checkbox" checked={includeHistorical} onChange={(e) => setIncludeHistorical(e.target.checked)} />
                包含历史版本
              </label>
              <select value={sort} onChange={(e) => setSort(e.target.value)} className="border border-gray-300 rounded px-2 py-1">
                <option value="relevance">相关度</option>
                <option value="recent">上传时间</option>
                <option value="title">标题</option>
              </select>
              <div className="flex border border-gray-300 rounded overflow-hidden">
                <button onClick={() => setView("slides")} className={`px-3 py-1 ${view === "slides" ? "bg-brand-500 text-white" : "text-gray-500"}`}>
                  页面卡片
                </button>
                <button onClick={() => setView("presentations")} className={`px-3 py-1 ${view === "presentations" ? "bg-brand-500 text-white" : "text-gray-500"}`}>
                  文件聚合
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* tag facets */}
        {facets.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-4 mb-5">
            <div className="text-xs text-gray-400 mb-2">标签筛选(可多选)</div>
            {Object.entries(facetsByCategory).map(([cat, tags]) => (
              <div key={cat} className="mb-2 last:mb-0">
                <span className="text-xs text-gray-400 mr-2">{cat}:</span>
                {tags.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => toggleTag(t.id)}
                    className={`inline-block px-2.5 py-0.5 mr-1.5 mb-1 rounded-full text-xs border transition ${
                      selectedTags.includes(t.id)
                        ? "bg-brand-500 text-white border-brand-500"
                        : "bg-gray-50 text-gray-600 border-gray-200 hover:border-brand-300"
                    }`}
                  >
                    {t.name} ({t.count})
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}

        {msg && <div className="text-sm text-red-600 mb-4">{msg}</div>}

        {/* results */}
        {searched && !loading && results.length === 0 && groups.length === 0 && (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
            未找到匹配页面
          </div>
        )}

        {view === "slides" ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {results.map((h) => (
              <div key={h.slide.id} className="relative">
                <SlideCard slide={h.slide} onOpen={setActive} onToggleFavorite={toggleFavorite} />
                {h.hit_reasons.length > 0 && (
                  <div className="absolute top-2 left-2 flex flex-wrap gap-1">
                    {h.hit_reasons.slice(0, 2).map((r) => (
                      <span key={r} className={`text-[10px] px-1.5 py-0.5 rounded ${REASON_COLORS[r] || "bg-gray-100 text-gray-500"}`}>
                        {r}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {groups.map((g) => (
              <div key={g.id} className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="font-medium text-gray-700 mb-3">📁 {g.title} <span className="text-xs text-gray-400">({g.slides.length} 页命中)</span></div>
                <div className="flex gap-3 overflow-x-auto pb-2">
                  {g.slides.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setActive({ id: s.id, page_no: s.page_no, title: s.title, native_text: null, thumbnail_url: s.thumbnail_url, presentation_title: g.title })}
                      className="shrink-0 w-40 bg-gray-50 rounded-lg overflow-hidden border border-gray-200 hover:border-brand-300 text-left"
                    >
                      <div className="aspect-video bg-gray-100">
                        {s.thumbnail_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={s.thumbnail_url} alt={`P${s.page_no}`} className="w-full h-full object-contain" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-300 text-xs">无预览</div>
                        )}
                      </div>
                      <div className="p-2">
                        <div className="text-xs text-gray-600 truncate">P{s.page_no} {s.title || ""}</div>
                        {s.hit_reasons[0] && <div className="text-[10px] text-brand-500">{s.hit_reasons[0]}</div>}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <SlideDetailDrawer slide={active} onClose={() => setActive(null)} onMsg={setMsg} onToggleFavorite={onDrawerToggleFav} />
    </AppShell>
  );
}
