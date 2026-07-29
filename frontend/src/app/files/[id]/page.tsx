"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import SlideCard, { type SlideCardData } from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError, API_BASE } from "@/lib/api";

interface Presentation {
  id: string;
  title: string;
  page_count: number;
  current_status: string | null;
}

export default function FileDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [pres, setPres] = useState<Presentation | null>(null);
  const [slides, setSlides] = useState<SlideCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [active, setActive] = useState<SlideCardData | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [p, sl] = await Promise.all([
        api.get<Presentation>(`/api/presentations/${id}`),
        api.get<SlideCardData[]>(`/api/presentations/${id}/slides`),
      ]);
      setPres(p);
      setSlides(sl);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function downloadSource(fileId: string) {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/presentations/${fileId}/download-source`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("下载失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${pres?.title}.pptx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setMsg("下载失败");
    }
  }

  return (
    <AppShell title={pres ? `文件详情:${pres.title}` : "文件详情"}>
      <div className="space-y-6">
        {msg && <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">{msg}</div>}
        {pres && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-gray-800">{pres.title}</div>
                <div className="text-xs text-gray-400 mt-1">
                  {pres.page_count} 页 · 状态 {pres.current_status}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => downloadSource(id)}
                  className="px-3 py-1.5 text-sm border border-brand-200 text-brand-600 rounded-lg hover:bg-brand-50"
                >
                  下载源 PPTX
                </button>
              </div>
            </div>
          </div>
        )}

        {loading ? (
          <div className="text-gray-400">加载中...</div>
        ) : slides.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
            暂无页面数据
            {pres?.current_status === "PARSING" || pres?.current_status === "RENDERING"
              ? ",解析/渲染进行中..."
              : ""}
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
