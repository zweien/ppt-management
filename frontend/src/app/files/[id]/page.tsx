"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import SlideCard, { type SlideCardData } from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError, API_BASE } from "@/lib/api";

interface Version {
  id: string;
  version_no: number;
  status: string;
  page_count: number;
  original_filename: string;
  file_size: number;
  created_at: string;
}
interface Presentation {
  id: string;
  title: string;
  page_count: number;
  current_status: string | null;
  current_version_id: string | null;
  versions: Version[];
}

interface VersionDiff {
  summary: Record<string, number>;
  details: Record<string, { from_slide_id: string | null; to_slide_id: string | null; score: number | null }[]>;
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

  const [reparsing, setReparsing] = useState(false);
  async function reparse() {
    setReparsing(true);
    setMsg("");
    try {
      const r = await api.post<{ detail: string }>(`/api/presentations/${id}/reparse`);
      setMsg(r.detail);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "重新解析失败");
    } finally {
      setReparsing(false);
    }
  }

  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffFrom, setDiffFrom] = useState("");
  const [diffTo, setDiffTo] = useState("");

  async function switchCurrent(vid: string) {
    if (!confirm("切换当前版本?搜索默认将只检索当前版本。")) return;
    try {
      await api.post(`/api/presentations/${id}/versions/${vid}/set-current`);
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "切换失败");
    }
  }

  async function showDiff() {
    if (!diffFrom || !diffTo || diffFrom === diffTo) {
      setMsg("请选择两个不同的版本");
      return;
    }
    setDiffLoading(true);
    try {
      const d = await api.get<VersionDiff>(
        `/api/presentations/${id}/version-diff?from_vid=${diffFrom}&to_vid=${diffTo}`
      );
      setDiff(d);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "获取差异失败");
    } finally {
      setDiffLoading(false);
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
                  {pres.page_count} 页 · 状态 {pres.current_status} · {pres.versions.length} 个版本
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => downloadSource(id)}
                  className="px-3 py-1.5 text-sm border border-brand-200 text-brand-600 rounded-lg hover:bg-brand-50"
                >
                  下载源 PPTX
                </button>
                <button
                  onClick={reparse}
                  disabled={reparsing}
                  title="重新触发 MinerU 增强解析(及视觉/embedding,若已配置模型)"
                  className="px-3 py-1.5 text-sm border border-brand-200 text-brand-600 rounded-lg hover:bg-brand-50 disabled:opacity-50"
                >
                  {reparsing ? "提交中..." : "重新解析"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 版本管理面板(仅多版本时显示) */}
        {pres && pres.versions.length > 1 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="font-medium text-gray-700 mb-3">版本管理(共 {pres.versions.length} 个版本)</div>
            <div className="space-y-2 mb-4">
              {pres.versions.map((v) => (
                <div key={v.id} className="flex items-center justify-between text-sm py-2 border-b border-gray-100 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-700">v{v.version_no}</span>
                    {pres.current_version_id === v.id && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">当前</span>
                    )}
                    <span className="text-xs text-gray-400">{v.page_count} 页 · {new Date(v.created_at).toLocaleString("zh-CN")}</span>
                    <span className="text-xs text-gray-400">{(v.file_size / 1024).toFixed(0)} KB</span>
                  </div>
                  {pres.current_version_id !== v.id && (
                    <button onClick={() => switchCurrent(v.id)} className="text-xs text-brand-600 hover:underline">
                      设为当前
                    </button>
                  )}
                </div>
              ))}
            </div>
            {/* 版本差异 */}
            <div className="flex items-center gap-2 text-xs text-gray-500 flex-wrap">
              <span>版本对比:</span>
              <select value={diffFrom} onChange={(e) => setDiffFrom(e.target.value)} className="border border-gray-300 rounded px-2 py-1">
                <option value="">旧版本</option>
                {pres.versions.map((v) => <option key={v.id} value={v.id}>v{v.version_no}</option>)}
              </select>
              <span>→</span>
              <select value={diffTo} onChange={(e) => setDiffTo(e.target.value)} className="border border-gray-300 rounded px-2 py-1">
                <option value="">新版本</option>
                {pres.versions.map((v) => <option key={v.id} value={v.id}>v{v.version_no}</option>)}
              </select>
              <button onClick={showDiff} disabled={diffLoading} className="px-3 py-1 bg-brand-500 text-white rounded disabled:opacity-50">
                {diffLoading ? "对比中..." : "对比"}
              </button>
            </div>
            {diff && (
              <div className="mt-4 flex flex-wrap gap-2">
                {Object.entries(diff.summary).map(([type, count]) => {
                  const colorMap: Record<string, string> = {
                    unchanged: "bg-gray-100 text-gray-600",
                    modified: "bg-yellow-100 text-yellow-700",
                    added: "bg-green-100 text-green-700",
                    deleted: "bg-red-100 text-red-700",
                    rearranged: "bg-blue-100 text-blue-700",
                  };
                  const labelMap: Record<string, string> = {
                    unchanged: "未变化", modified: "修改", added: "新增", deleted: "删除", rearranged: "重排",
                  };
                  return (
                    <span key={type} className={`text-xs px-2 py-1 rounded ${colorMap[type] || "bg-gray-100"}`}>
                      {labelMap[type] || type}: {count}
                    </span>
                  );
                })}
              </div>
            )}
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
