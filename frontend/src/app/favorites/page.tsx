"use client";

import { useEffect, useState } from "react";
import { Star } from "lucide-react";
import AppShell from "@/components/AppShell";
import SlideCard, { type SlideCardData } from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError } from "@/lib/api";
import EmptyState from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/Toast";

interface Fav extends SlideCardData {}

export default function FavoritesPage() {
  const toast = useToast();
  const [items, setItems] = useState<Fav[]>([]);
  const [active, setActive] = useState<Fav | null>(null);

  async function load() {
    try {
      setItems(await api.get<Fav[]>(`/api/favorites`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function toggleFavorite(slide: SlideCardData) {
    // From favorites page, un-favorite removes it from the list.
    setItems((prev) => prev.filter((s) => s.id !== slide.id));
    try {
      await api.delete(`/api/favorites/${slide.id}`);
      toast.success("已取消收藏");
    } catch (e) {
      // Restore on failure.
      setItems((prev) => (prev.find((s) => s.id === slide.id) ? prev : [...prev, slide as Fav]));
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    }
  }

  function onDrawerToggleFav(slideId: string, isFav: boolean) {
    if (!isFav) {
      setItems((prev) => prev.filter((s) => s.id !== slideId));
    }
  }

  return (
    <AppShell title="我的收藏">
      {items.length === 0 ? (
        <EmptyState icon={<Star className="w-5 h-5" />} title="暂无收藏" description="在页面浏览或搜索结果中点击星标即可收藏。" />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((s) => (
            <SlideCard key={s.id} slide={s} onOpen={setActive} onToggleFavorite={toggleFavorite} />
          ))}
        </div>
      )}

      <SlideDetailDrawer slide={active} onClose={() => setActive(null)} onToggleFavorite={onDrawerToggleFav} />
    </AppShell>
  );
}
