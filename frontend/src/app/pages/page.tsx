"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import SlideCard, { type SlideCardData } from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError } from "@/lib/api";

export default function PagesPage() {
  const [slides, setSlides] = useState<SlideCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [active, setActive] = useState<SlideCardData | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await api.get<SlideCardData[]>(`/api/pages`);
        setSlides(data);
      } catch (e) {
        setMsg(e instanceof ApiError ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <AppShell title="页面浏览">
      <div className="space-y-4">
        {msg && <div className="text-sm text-red-600">{msg}</div>}
        {loading ? (
          <div className="text-gray-400">加载中...</div>
        ) : slides.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
            暂无页面
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {slides.map((s) => (
              <SlideCard key={s.id} slide={s} onOpen={setActive} />
            ))}
          </div>
        )}
      </div>

      <SlideDetailDrawer slide={active} onClose={() => setActive(null)} onMsg={setMsg} />
    </AppShell>
  );
}
