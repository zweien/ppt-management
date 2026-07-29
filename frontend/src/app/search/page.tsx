"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import SlideCard, { type SlideCardData } from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError } from "@/lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SlideCardData[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [msg, setMsg] = useState("");
  const [active, setActive] = useState<SlideCardData | null>(null);

  async function doSearch(q?: string) {
    const term = (q ?? query).trim();
    setLoading(true);
    setSearched(true);
    setMsg("");
    try {
      const data = await api.get<SlideCardData[]>(`/api/search/slides?q=${encodeURIComponent(term)}`);
      setResults(data);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "搜索失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    doSearch("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppShell title="搜索首页">
      <div className="max-w-5xl mx-auto">
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              placeholder="输入关键词或描述,如:无人系统总体架构、紫色科技风..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-400 focus:border-brand-400 outline-none"
            />
            <button
              onClick={() => doSearch()}
              disabled={loading}
              className="px-6 py-3 bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50 font-medium"
            >
              {loading ? "搜索中..." : "搜索"}
            </button>
          </div>
          <div className="mt-3 flex gap-2 flex-wrap">
            {["无人系统", "总体架构", "项目研究目标", "能力现状"].map((t) => (
              <button
                key={t}
                onClick={() => {
                  setQuery(t);
                  doSearch(t);
                }}
                className="px-3 py-1 text-xs bg-brand-50 text-brand-600 rounded-full hover:bg-brand-100"
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {msg && <div className="text-sm text-red-600 mb-4">{msg}</div>}

        {searched && !loading && results.length === 0 && (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center text-gray-400">
            未找到匹配页面
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {results.map((s) => (
            <SlideCard key={s.id} slide={s} onOpen={setActive} />
          ))}
        </div>
      </div>

      <SlideDetailDrawer slide={active} onClose={() => setActive(null)} onMsg={setMsg} />
    </AppShell>
  );
}
