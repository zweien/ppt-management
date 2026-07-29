"use client";

import { useEffect, useState } from "react";
import { Images, Tag as TagIcon, Star } from "lucide-react";
import AppShell from "@/components/AppShell";
import SlideCard, { type SlideCardData } from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Select } from "@/components/ui/Input";
import EmptyState from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/Toast";

interface Tag {
  id: string;
  name: string;
  category: string | null;
}

export default function PagesPage() {
  const toast = useToast();
  const [slides, setSlides] = useState<SlideCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<SlideCardData | null>(null);

  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [tags, setTags] = useState<Tag[]>([]);
  const [batchTagId, setBatchTagId] = useState("");

  async function load() {
    try {
      setSlides(await api.get<SlideCardData[]>(`/api/pages`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    api.get<Tag[]>(`/api/tags`).then(setTags).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      toast.error("请选择标签和至少一个页面");
      return;
    }
    try {
      await api.post(`/api/slides/batch-tags`, { slide_ids: [...selected], tag_id: batchTagId });
      toast.success(`已为 ${selected.size} 个页面添加标签`);
      setSelected(new Set());
      setSelectMode(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  async function batchFavorite() {
    if (selected.size === 0) return;
    try {
      await api.post(`/api/favorites`, { slide_ids: [...selected] });
      toast.success(`已收藏 ${selected.size} 个页面`);
      const sel = selected;
      setSlides((prev) => prev.map((s) => (sel.has(s.id) ? { ...s, is_favorite: true } : s)));
      setSelected(new Set());
      setSelectMode(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  async function toggleFavorite(slide: SlideCardData) {
    const target = !slide.is_favorite;
    setSlides((prev) => prev.map((s) => (s.id === slide.id ? { ...s, is_favorite: target } : s)));
    try {
      if (target) {
        await api.post(`/api/favorites`, { slide_ids: [slide.id] });
        toast.success("已收藏");
      } else {
        await api.delete(`/api/favorites/${slide.id}`);
        toast.success("已取消收藏");
      }
    } catch (e) {
      setSlides((prev) => prev.map((s) => (s.id === slide.id ? { ...s, is_favorite: !target } : s)));
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  function onDrawerToggleFav(slideId: string, isFav: boolean) {
    setSlides((prev) => prev.map((s) => (s.id === slideId ? { ...s, is_favorite: isFav } : s)));
  }

  return (
    <AppShell title="页面浏览">
      <div className="space-y-4">
        {/* Batch toolbar */}
        <div className="bg-surface rounded-md shadow-e2 p-4 flex items-center gap-3 flex-wrap">
          <Checkbox
            checked={selectMode}
            onChange={(e) => {
              setSelectMode(e.target.checked);
              setSelected(new Set());
            }}
            label="批量选择模式"
          />
          {selectMode && (
            <>
              <span className="text-sm text-mute">已选 {selected.size} 个</span>
              <Select inputSize="sm" value={batchTagId} onChange={(e) => setBatchTagId(e.target.value)} className="w-40">
                <option value="">选择标签…</option>
                {tags.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
              <Button size="sm" variant="secondary" leadingIcon={<TagIcon className="w-3.5 h-3.5" />} onClick={batchAddTag} disabled={selected.size === 0 || !batchTagId}>
                批量加标签
              </Button>
              <Button size="sm" variant="secondary" leadingIcon={<Star className="w-3.5 h-3.5" />} onClick={batchFavorite} disabled={selected.size === 0}>
                批量收藏
              </Button>
            </>
          )}
        </div>

        {loading ? (
          <div className="text-mute text-sm">加载中...</div>
        ) : slides.length === 0 ? (
          <EmptyState icon={<Images className="w-5 h-5" />} title="暂无页面" description="上传 PPTX 后,解析出的页面会出现在这里。" />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {slides.map((s) => (
              <div key={s.id} className="relative">
                {selectMode && (
                  <input
                    type="checkbox"
                    checked={selected.has(s.id)}
                    onChange={() => toggleSelect(s.id)}
                    className={cn(
                      "absolute top-2 right-2 z-20 w-5 h-5 accent-[rgb(var(--primary))] bg-canvas border border-hairline-strong rounded",
                    )}
                  />
                )}
                <div className={cn(selected.has(s.id) && "outline outline-1 outline-primary rounded-md")}>
                  <SlideCard
                    slide={s}
                    selected={selected.has(s.id)}
                    onOpen={selectMode ? undefined : setActive}
                    onToggleFavorite={selectMode ? undefined : toggleFavorite}
                  />
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
