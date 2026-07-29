"use client";

import { useCallback, useEffect, useState } from "react";
import { Search as SearchIcon, FolderOpen } from "lucide-react";
import AppShell from "@/components/AppShell";
import SlideCard from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { Checkbox } from "@/components/ui/Checkbox";
import { Tabs } from "@/components/ui/Tabs";
import { Badge } from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/Toast";

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

// Hit-reason → semantic tone (Vercel palette). Kept centralized for consistency.
const REASON_TONE: Record<string, "info" | "violet" | "primary" | "success" | "warning" | "default"> = {
  正文命中: "info",
  语义相似: "violet",
  标题精确: "primary",
  标题匹配: "primary",
  文件名匹配: "success",
  人工标签: "warning",
  "AI 标签": "default",
  已收藏: "warning",
};

export default function SearchPage() {
  const toast = useToast();
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
  const [active, setActive] = useState<SlideCardData | null>(null);

  const doSearch = useCallback(async () => {
    setLoading(true);
    setSearched(true);
    const tagParam = selectedTags.join(",");
    try {
      const [hits, gs, fc] = await Promise.all([
        api.get<HitResult[]>(
          `/api/search/slides?q=${encodeURIComponent(query)}&tag_ids=${tagParam}&favorite_only=${favoriteOnly}&include_historical=${includeHistorical}&sort=${sort}`,
        ),
        api.get<PresGroup[]>(`/api/search/presentations?q=${encodeURIComponent(query)}&tag_ids=${tagParam}`),
        api.get<TagFacet[]>(`/api/search/tag-facets?q=${encodeURIComponent(query)}`),
      ]);
      setResults(hits);
      setGroups(gs);
      setFacets(fc);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "搜索失败");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      prev.map((h) => (h.slide.id === slide.id ? { ...h, slide: { ...h.slide, is_favorite: target } } : h)),
    );
    try {
      if (target) {
        await api.post(`/api/favorites`, { slide_ids: [slide.id] });
        toast.success("已收藏");
      } else {
        await api.delete(`/api/favorites/${slide.id}`);
        toast.success("已取消收藏");
      }
    } catch (e) {
      setResults((prev) =>
        prev.map((h) => (h.slide.id === slide.id ? { ...h, slide: { ...h.slide, is_favorite: !target } } : h)),
      );
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  function onDrawerToggleFav(slideId: string, isFav: boolean) {
    setResults((prev) =>
      prev.map((h) => (h.slide.id === slideId ? { ...h, slide: { ...h.slide, is_favorite: isFav } } : h)),
    );
  }

  const facetsByCategory = facets.reduce<Record<string, TagFacet[]>>((acc, f) => {
    const key = f.category || "其他";
    (acc[key] ||= []).push(f);
    return acc;
  }, {});

  return (
    <AppShell title="搜索">
      <div className="space-y-5">
        {/* Search bar */}
        <div className="bg-surface rounded-md shadow-e2 p-5">
          {/* Search input row */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <SearchIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-mute pointer-events-none" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doSearch()}
                placeholder="输入关键词或描述,如:无人系统总体架构、紫色科技风..."
                inputSize="lg"
                className="pl-9"
              />
            </div>
            <Button variant="primary" size="lg" onClick={doSearch} loading={loading}>
              搜索
            </Button>
          </div>

          {/* Quick-term presets — sit directly under the input as search hints */}
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono uppercase tracking-wider text-mute shrink-0">试试</span>
            <div className="flex items-center gap-1.5 flex-wrap">
              {["无人系统", "总体架构", "项目研究目标", "能力现状"].map((t) => (
                <button
                  key={t}
                  onClick={() => setQuery(t)}
                  className="h-7 inline-flex items-center text-xs px-2.5 text-body bg-canvas-soft-2 border border-hairline rounded-pill hover:text-ink hover:border-hairline-strong transition"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Result controls — filters / sort / view, all h-7, grouped with dividers */}
          <div className="mt-3 pt-3 border-t border-hairline flex items-center gap-2 flex-wrap">
            <Checkbox checked={favoriteOnly} onChange={(e) => setFavoriteOnly(e.target.checked)} label="仅看收藏" />
            <Checkbox
              checked={includeHistorical}
              onChange={(e) => setIncludeHistorical(e.target.checked)}
              label="包含历史版本"
            />
            <span className="w-px h-5 bg-hairline mx-1" aria-hidden />
            <Select inputSize="xs" value={sort} onChange={(e) => setSort(e.target.value)} className="w-28">
              <option value="relevance">相关度</option>
              <option value="recent">上传时间</option>
              <option value="title">标题</option>
            </Select>
            <div className="ml-auto">
              <Tabs
                items={[
                  { key: "slides", label: "页面卡片" },
                  { key: "presentations", label: "文件聚合" },
                ]}
                value={view}
                onChange={setView}
              />
            </div>
          </div>
        </div>

        {/* Tag facets */}
        {facets.length > 0 && (
          <div className="bg-surface rounded-md shadow-e2 p-4">
            <div className="text-xs font-mono uppercase tracking-wider text-mute mb-2">标签筛选(可多选)</div>
            {Object.entries(facetsByCategory).map(([cat, tags]) => (
              <div key={cat} className="mb-2 last:mb-0 flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-mute mr-1">{cat}:</span>
                {tags.map((t) => {
                  const on = selectedTags.includes(t.id);
                  return (
                    <button
                      key={t.id}
                      onClick={() => toggleTag(t.id)}
                      className={cn(
                        "inline-flex items-center text-xs px-2.5 py-1 rounded-full border transition",
                        on
                          ? "bg-primary text-on-primary border-transparent"
                          : "bg-canvas text-body border-hairline hover:border-hairline-strong hover:text-ink",
                      )}
                    >
                      {t.name} <span className={on ? "opacity-70 ml-1" : "text-mute ml-1"}>{t.count}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        {/* Results */}
        {searched && !loading && results.length === 0 && groups.length === 0 && (
          <EmptyState
            icon={<SearchIcon className="w-5 h-5" />}
            title="未找到匹配页面"
            description="尝试换一个关键词,或调整筛选条件。"
          />
        )}

        {view === "slides" ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {results.map((h) => (
              <div key={h.slide.id} className="relative">
                <SlideCard slide={h.slide} onOpen={setActive} onToggleFavorite={toggleFavorite} />
                {h.hit_reasons.length > 0 && (
                  <div className="absolute top-2 left-2 flex flex-wrap gap-1 z-10">
                    {h.hit_reasons.slice(0, 2).map((r) => (
                      <Badge key={r} tone={REASON_TONE[r] || "default"}>
                        {r}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {groups.map((g) => (
              <div key={g.id} className="bg-surface rounded-md shadow-e2 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <FolderOpen className="w-4 h-4 text-body" />
                  <span className="font-medium text-ink">{g.title}</span>
                  <span className="text-xs text-mute">({g.slides.length} 页命中)</span>
                </div>
                <div className="flex gap-3 overflow-x-auto pb-2">
                  {g.slides.map((s) => (
                    <button
                      key={s.id}
                      onClick={() =>
                        setActive({
                          id: s.id,
                          page_no: s.page_no,
                          title: s.title,
                          native_text: null,
                          thumbnail_url: s.thumbnail_url,
                          presentation_title: g.title,
                        })
                      }
                      className="shrink-0 w-40 bg-surface rounded-md overflow-hidden border border-hairline hover:border-hairline-strong hover:shadow-e3 transition text-left"
                    >
                      <div className="aspect-video bg-canvas-soft-2">
                        {s.thumbnail_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={s.thumbnail_url} alt={`P${s.page_no}`} className="w-full h-full object-contain" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-mute text-xs font-mono">
                            no preview
                          </div>
                        )}
                      </div>
                      <div className="p-2">
                        <div className="text-xs text-body truncate">
                          P{s.page_no} {s.title || ""}
                        </div>
                        {s.hit_reasons[0] && (
                          <div className="mt-1">
                            <Badge tone={REASON_TONE[s.hit_reasons[0]] || "default"}>{s.hit_reasons[0]}</Badge>
                          </div>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <SlideDetailDrawer slide={active} onClose={() => setActive(null)} onToggleFavorite={onDrawerToggleFav} />
    </AppShell>
  );
}
