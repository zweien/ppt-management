"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, API_BASE } from "@/lib/api";
import type { SlideCardData } from "./SlideCard";

interface SlideDetail {
  id: string;
  page_no: number;
  title: string | null;
  native_text: string | null;
  notes_text: string | null;
  manual_summary: string | null;
  ai_summary: string | null;
  preview_url: string | null;
  fingerprint: string | null;
  presentation_title: string | null;
  content_json: any;
  mineru_markdown?: string | null;
}

export default function SlideDetailDrawer({
  slide,
  onClose,
  onMsg,
}: {
  slide: SlideCardData | null;
  onClose: () => void;
  onMsg?: (m: string) => void;
}) {
  const [detail, setDetail] = useState<SlideDetail | null>(null);
  const [aiTags, setAiTags] = useState<{ id: string; tag: { name: string; category: string | null }; origin: string }[]>([]);
  const [showAi, setShowAi] = useState(false);
  const [tab, setTab] = useState<"basic" | "text" | "mineru" | "tags" | "file">("basic");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState("");

  useEffect(() => {
    if (!slide) {
      setDetail(null);
      setAiTags([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setTab("basic");
    (async () => {
      try {
        const [d, tags] = await Promise.all([
          api.get<SlideDetail>(`/api/slides/${slide.id}`),
          api.get<{ id: string; tag: { name: string; category: string | null }; origin: string }[]>(
            `/api/slides/${slide.id}/tags`
          ),
        ]);
        if (!cancelled) {
          setDetail(d);
          setAiTags(tags.filter((t) => t.origin === "ai"));
        }
      } catch (e) {
        if (!cancelled) onMsg?.(e instanceof ApiError ? e.message : "加载详情失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slide]);

  if (!slide) return null;

  async function downloadPng(d: SlideDetail | null) {
    if (!d?.preview_url) {
      onMsg?.("无预览图");
      return;
    }
    const a = document.createElement("a");
    a.href = d.preview_url;
    a.download = `page-${d.page_no}.png`;
    a.click();
  }

  async function copyText(d: SlideDetail | null) {
    if (!d) return;
    const text = [d.title, d.native_text, d.notes_text].filter(Boolean).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      onMsg?.("已复制页面文字");
    } catch {
      onMsg?.("复制失败");
    }
  }

  async function exportSingleSlide() {
    if (!slide) return;
    setExporting(true);
    setExportMsg("");
    try {
      const r = await api.post<{ status: string; download_url: string }>(`/api/slides/${slide.id}/exports/pptx`);
      if (r.download_url) {
        const a = document.createElement("a");
        a.href = r.download_url;
        a.download = `slide-${slide.page_no}.pptx`;
        a.click();
        setExportMsg("已导出单页 PPTX");
      } else {
        setExportMsg("导出失败");
      }
    } catch (e) {
      setExportMsg(e instanceof ApiError ? e.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white shadow-2xl overflow-auto h-full">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
          <div>
            <div className="text-xs text-gray-400">
              {slide.presentation_title || detail?.presentation_title || "-"} · 第 {slide.page_no} 页
            </div>
            <div className="font-medium text-gray-800">{slide.title || detail?.title || "(无标题)"}</div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        <div className="p-6 space-y-4">
          {loading ? (
            <div className="text-gray-400 text-sm">加载详情...</div>
          ) : (
            <>
              <div className="bg-gray-50 rounded-lg overflow-hidden">
                {detail?.preview_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={detail.preview_url} alt="高清预览" className="w-full" />
                ) : (
                  <div className="aspect-video flex items-center justify-center text-gray-300">无高清预览</div>
                )}
              </div>

              <div className="flex gap-2 flex-wrap items-center">
                <button onClick={() => downloadPng(detail)} className="px-3 py-1.5 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600">
                  下载图片
                </button>
                <button onClick={() => copyText(detail)} className="px-3 py-1.5 text-sm border border-brand-200 text-brand-600 rounded-lg hover:bg-brand-50">
                  复制文字
                </button>
                <button
                  onClick={() => exportSingleSlide()}
                  disabled={exporting}
                  className="px-3 py-1.5 text-sm border border-brand-200 text-brand-600 rounded-lg hover:bg-brand-50 disabled:opacity-50"
                  title="复制源 PPTX 目标页及依赖,生成仅含该页的可编辑 PPTX"
                >
                  {exporting ? "导出中..." : "导出单页 PPTX"}
                </button>
                {exportMsg && <span className="text-xs text-gray-500">{exportMsg}</span>}
              </div>

              <div className="border-b border-gray-200 flex gap-1 overflow-x-auto">
                {([["basic", "基本信息"], ["text", "原始文字"], ["mineru", "MinerU"], ["tags", "标签"], ["file", "所在文件"]] as const).map(
                  ([k, label]) => (
                    <button
                      key={k}
                      onClick={() => setTab(k)}
                      className={`px-4 py-2 text-sm border-b-2 -mb-px whitespace-nowrap ${
                        tab === k ? "border-brand-500 text-brand-600 font-medium" : "border-transparent text-gray-500"
                      }`}
                    >
                      {label}
                    </button>
                  )
                )}
              </div>

              {tab === "basic" && (
                <div className="text-sm text-gray-600 space-y-2">
                  <div><span className="text-gray-400">页码:</span> 第 {slide.page_no} 页</div>
                  <div><span className="text-gray-400">标题:</span> {detail?.title || "-"}</div>
                  <div><span className="text-gray-400">人工摘要:</span> {detail?.manual_summary || "(待填写)"}</div>
                  <div>
                    <span className="text-gray-400">AI 摘要:</span>{" "}
                    {detail?.ai_summary ? (
                      <span className="text-gray-700">{detail.ai_summary}</span>
                    ) : (
                      <span className="text-gray-300">(未生成)</span>
                    )}
                  </div>
                  <div><span className="text-gray-400">备注:</span> {detail?.notes_text || "-"}</div>
                  <div>
                    <span className="text-gray-400">指纹:</span>{" "}
                    <code className="text-xs">{detail?.fingerprint?.slice(0, 16) || "-"}...</code>
                  </div>
                </div>
              )}
              {tab === "text" && (
                <div className="text-sm text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded max-h-72 overflow-auto">
                  {detail?.native_text || "(无原生文字)"}
                </div>
              )}
              {tab === "mineru" && (
                <div className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 p-3 rounded max-h-72 overflow-auto">
                  {detail?.mineru_markdown || "(MinerU 未解析或无内容)"}
                </div>
              )}
              {tab === "tags" && (
                <div className="text-sm space-y-3">
                  <div>
                    <div className="text-xs text-gray-400 mb-1">人工标签 / 已确认</div>
                    <div className="flex flex-wrap gap-1.5">
                      <span className="text-xs px-2 py-0.5 bg-gray-50 text-gray-400 border border-gray-200 rounded">
                        暂无(可在标签管理添加)
                      </span>
                    </div>
                  </div>
                  <div>
                    <button
                      onClick={() => setShowAi((s) => !s)}
                      className="text-xs text-brand-600 hover:underline mb-1"
                    >
                      {showAi ? "隐藏" : "显示"} AI 建议 {aiTags.length > 0 && `(${aiTags.length})`}
                    </button>
                    {showAi && (
                      <div className="flex flex-wrap gap-1.5">
                        {aiTags.length === 0 ? (
                          <span className="text-xs text-gray-400">(无 AI 标签)</span>
                        ) : (
                          aiTags.map((t) => (
                            <span key={t.id} className="text-xs px-2 py-0.5 bg-purple-50 text-purple-600 border border-purple-200 rounded">
                              {t.tag.name}
                              {t.tag.category && <span className="text-purple-300 ml-1">{t.tag.category}</span>}
                            </span>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
              {tab === "file" && (
                <div className="text-sm text-gray-600 space-y-2">
                  <div>
                    <span className="text-gray-400">所属文件:</span> {slide.presentation_title || detail?.presentation_title || "-"}
                  </div>
                  {slide.presentation_title && (
                    <Link href="/files" className="text-brand-600 hover:underline">
                      前往文件管理
                    </Link>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
