"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Star, X, Download, Copy, FileDown, Pencil, Check } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { SlideCardData } from "./SlideCard";
import Button from "./ui/Button";
import { Tabs } from "./ui/Tabs";
import { useToast } from "./ui/Toast";

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
  user_note?: string | null;
  is_favorite?: boolean;
  source_format?: string;
}

interface SlideTagRow {
  id: string;
  tag: { name: string; category: string | null };
  origin: string;
}

interface SimilarSlide {
  slide_id: string;
  page_no: number;
  title: string | null;
  presentation_id: string;
  presentation_title: string | null;
  thumbnail_url: string | null;
  distance: number | null;
}

type TabKey = "basic" | "text" | "mineru" | "tags" | "file";

export default function SlideDetailDrawer({
  slide,
  onClose,
  onToggleFavorite,
}: {
  slide: SlideCardData | null;
  onClose: () => void;
  onMsg?: (m: string) => void;
  onToggleFavorite?: (slideId: string, isFav: boolean) => void;
}) {
  const toast = useToast();
  const [detail, setDetail] = useState<SlideDetail | null>(null);
  const [slideTags, setSlideTags] = useState<SlideTagRow[]>([]);
  const [allTags, setAllTags] = useState<{ id: string; name: string; category: string | null }[]>([]);
  const [addTagId, setAddTagId] = useState("");
  const [tagBusy, setTagBusy] = useState(false);
  const [tab, setTab] = useState<TabKey>("basic");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [noteEditing, setNoteEditing] = useState(false);
  const [fav, setFav] = useState(false);
  const [togglingFav, setTogglingFav] = useState(false);
  const [similars, setSimilars] = useState<SimilarSlide[]>([]);

  useEffect(() => {
    if (!slide) {
      setDetail(null);
      setSlideTags([]);
      setSimilars([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setTab("basic");
    (async () => {
      try {
        const [d, tags, all, sims] = await Promise.all([
          api.get<SlideDetail>(`/api/slides/${slide.id}`),
          api.get<SlideTagRow[]>(`/api/slides/${slide.id}/tags`),
          api.get<{ id: string; name: string; category: string | null }[]>(`/api/tags`),
          api.get<SimilarSlide[]>(`/api/slides/${slide.id}/similar`).catch(() => [] as SimilarSlide[]),
        ]);
        if (!cancelled) {
          setDetail(d);
          setSlideTags(tags);
          setAllTags(all);
          setSimilars(sims);
          setAddTagId("");
          setNoteDraft(d.user_note || "");
          setNoteEditing(false);
          setFav(!!d.is_favorite);
        }
      } catch (e) {
        if (!cancelled) toast.error(e instanceof ApiError ? e.message : "加载详情失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slide]);

  useEffect(() => {
    if (!slide) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [slide, onClose]);

  if (!slide) return null;

  async function downloadPng(d: SlideDetail | null) {
    if (!d?.preview_url) {
      toast.info("无预览图");
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
      toast.success("已复制页面文字");
    } catch {
      toast.error("复制失败");
    }
  }

  async function exportSingleSlide() {
    if (!slide) return;
    setExporting(true);
    try {
      const r = await api.post<{ status: string; download_url: string }>(
        `/api/slides/${slide.id}/exports/pptx`,
      );
      if (r.download_url) {
        const a = document.createElement("a");
        a.href = r.download_url;
        a.download = `slide-${slide.page_no}.pptx`;
        a.click();
        toast.success("已导出单页 PPTX");
      } else {
        toast.error("导出失败");
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  async function saveNote() {
    if (!slide) return;
    setSavingNote(true);
    try {
      await api.patch(`/api/slides/${slide.id}`, { user_note: noteDraft });
      setDetail((d) => (d ? { ...d, user_note: noteDraft } : d));
      setNoteEditing(false);
      toast.success("备注已保存");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setSavingNote(false);
    }
  }

  async function toggleFavorite() {
    if (!slide) return;
    setTogglingFav(true);
    const target = !fav;
    try {
      if (target) {
        await api.post("/api/favorites", { slide_ids: [slide.id] });
        toast.success("已收藏");
      } else {
        await api.delete(`/api/favorites/${slide.id}`);
        toast.success("已取消收藏");
      }
      setFav(target);
      setDetail((d) => (d ? { ...d, is_favorite: target } : d));
      onToggleFavorite?.(slide.id, target);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setTogglingFav(false);
    }
  }

  async function addTag() {
    if (!slide || !addTagId) return;
    const tag = allTags.find((t) => t.id === addTagId);
    if (!tag) return;
    const tagId = addTagId;
    if (slideTags.some((st) => st.tag.name === tag.name)) {
      setAddTagId("");
      return;
    }
    const prev = slideTags;
    const newRow: SlideTagRow = {
      id: `tmp-${tagId}`,
      tag: { name: tag.name, category: tag.category },
      origin: "manual",
    };
    setSlideTags((p) => [...p, newRow]);
    setAddTagId("");
    setTagBusy(true);
    try {
      await api.post(`/api/slides/${slide.id}/tags/${tagId}`);
      const fresh = await api.get<SlideTagRow[]>(`/api/slides/${slide.id}/tags`);
      setSlideTags(fresh);
    } catch (e) {
      setSlideTags(prev);
      toast.error(e instanceof ApiError ? e.message : "添加标签失败");
    } finally {
      setTagBusy(false);
    }
  }

  async function removeTag(row: SlideTagRow) {
    if (!slide) return;
    const prev = slideTags;
    setSlideTags((p) => p.filter((st) => st.id !== row.id));
    try {
      const tagId = allTags.find((t) => t.name === row.tag.name)?.id;
      if (!tagId) throw new Error("标签不存在");
      await api.delete(`/api/slides/${slide.id}/tags/${tagId}`);
    } catch (e) {
      setSlideTags(prev);
      toast.error(e instanceof ApiError ? e.message : "移除标签失败");
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-canvas-soft shadow-e5 overflow-auto h-full animate-slide-in-right">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-canvas border-b border-hairline px-6 h-16 flex items-center justify-between">
          <div className="min-w-0">
            <div className="text-xs font-mono text-mute truncate">
              {slide.presentation_title || detail?.presentation_title || "-"} · 第 {slide.page_no} 页
            </div>
            <div className="font-medium text-ink truncate">{slide.title || detail?.title || "(无标题)"}</div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant={fav ? "primary" : "secondary"}
              size="sm"
              onClick={toggleFavorite}
              loading={togglingFav}
              leadingIcon={<Star className="w-3.5 h-3.5" fill={fav ? "currentColor" : "none"} />}
            >
              {fav ? "已收藏" : "收藏"}
            </Button>
            <button
              onClick={onClose}
              aria-label="关闭"
              className="text-mute hover:text-ink p-1.5 rounded-md hover:bg-canvas-soft-2"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-5">
          {loading ? (
            <div className="text-mute text-sm">加载详情...</div>
          ) : (
            <>
              {/* Preview */}
              <div className="rounded-md overflow-hidden border border-hairline bg-canvas-soft-2">
                {detail?.preview_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={detail.preview_url} alt="高清预览" className="w-full" />
                ) : (
                  <div className="aspect-video flex items-center justify-center text-mute font-mono text-sm">
                    无高清预览
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-2 flex-wrap items-center">
                <Button size="sm" variant="secondary" leadingIcon={<Download className="w-3.5 h-3.5" />} onClick={() => downloadPng(detail)}>
                  下载图片
                </Button>
                <Button size="sm" variant="secondary" leadingIcon={<Copy className="w-3.5 h-3.5" />} onClick={() => copyText(detail)}>
                  复制文字
                </Button>
                {detail?.source_format !== "ppt" && detail?.source_format !== "pdf" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    leadingIcon={<FileDown className="w-3.5 h-3.5" />}
                    onClick={exportSingleSlide}
                    loading={exporting}
                    title="复制源 PPTX 目标页及依赖,生成仅含该页的可编辑 PPTX"
                  >
                    导出单页 PPTX
                  </Button>
                )}
                {(detail?.source_format === "ppt" || detail?.source_format === "pdf") && (
                  <span className="text-xs text-mute self-center" title="单页 PPTX 导出仅支持 .pptx 源">
                    单页导出仅支持 .pptx
                  </span>
                )}
              </div>

              {/* Tabs */}
              <Tabs<TabKey>
                value={tab}
                onChange={setTab}
                items={[
                  { key: "basic", label: "基本信息" },
                  { key: "text", label: "原始文字" },
                  { key: "mineru", label: "MinerU" },
                  { key: "tags", label: "标签" },
                  { key: "file", label: "所在文件" },
                ]}
              />

              {/* Basic */}
              {tab === "basic" && (
                <div className="text-sm space-y-2.5">
                  <Row label="页码">第 {slide.page_no} 页</Row>
                  <Row label="标题">{detail?.title || "-"}</Row>
                  <Row label="人工摘要">{detail?.manual_summary || "(待填写)"}</Row>
                  <Row label="AI 摘要">
                    {detail?.ai_summary ? (
                      <span className="text-ink">{detail.ai_summary}</span>
                    ) : (
                      <span className="text-mute">(未生成)</span>
                    )}
                  </Row>
                  {similars.length > 0 && (
                    <Row label="相似页面">
                      <div className="space-y-1.5 flex-1">
                        <span className="text-xs text-mute">
                          库中有 {similars.length} 页与本页高度相似
                        </span>
                        <div className="flex gap-2 overflow-x-auto pb-1">
                          {similars.map((sm) => (
                            <Link
                              key={sm.slide_id}
                              href={`/files/${sm.presentation_id}`}
                              className="shrink-0 w-24 group/sim"
                              title={`${sm.presentation_title} P${sm.page_no}`}
                            >
                              <div className="bg-canvas border border-hairline rounded-sm overflow-hidden group-hover/sim:border-hairline-strong">
                                <div className="aspect-video bg-canvas-soft-2 flex items-center justify-center overflow-hidden">
                                  {sm.thumbnail_url ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={sm.thumbnail_url} alt={`P${sm.page_no}`} className="w-full h-full object-contain" />
                                  ) : (
                                    <span className="text-[14px] text-mute">P{sm.page_no}</span>
                                  )}
                                </div>
                                <div className="px-1.5 py-1">
                                  <div className="text-[13px] text-ink truncate">P{sm.page_no}</div>
                                  <div className="text-[14px] text-mute truncate">{sm.presentation_title}</div>
                                </div>
                              </div>
                            </Link>
                          ))}
                        </div>
                      </div>
                    </Row>
                  )}
                  <div className="flex gap-2">
                    <span className="w-20 shrink-0 text-mute">备注</span>
                    {noteEditing ? (
                      <span className="inline-flex items-center gap-2 flex-1">
                        <input
                          value={noteDraft}
                          onChange={(e) => setNoteDraft(e.target.value)}
                          className="flex-1 h-8 px-2 text-sm bg-canvas border border-hairline rounded-sm outline-none focus:border-hairline-strong"
                          placeholder="添加你的备注"
                        />
                        <Button size="sm" variant="primary" onClick={saveNote} loading={savingNote} leadingIcon={<Check className="w-3 h-3" />}>
                          保存
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setNoteEditing(false);
                            setNoteDraft(detail?.user_note || "");
                          }}
                        >
                          取消
                        </Button>
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 flex-1">
                        <span className="text-body">{detail?.user_note || "(无)"}</span>
                        <button
                          onClick={() => setNoteEditing(true)}
                          className="text-link hover:underline inline-flex items-center gap-1 text-xs"
                        >
                          <Pencil className="w-3 h-3" /> 编辑
                        </button>
                      </span>
                    )}
                  </div>
                  <Row label="演讲备注">{detail?.notes_text || "-"}</Row>
                  <Row label="指纹">
                    <code className="text-xs font-mono text-mute">{detail?.fingerprint?.slice(0, 16) || "-"}...</code>
                  </Row>
                </div>
              )}

              {/* Native text */}
              {tab === "text" && (
                <div className="text-sm text-ink whitespace-pre-wrap font-mono bg-canvas-soft-2 p-4 rounded-md max-h-72 overflow-auto border border-hairline">
                  {detail?.native_text || "(无原生文字)"}
                </div>
              )}

              {/* MinerU */}
              {tab === "mineru" && (
                <div className="text-sm text-ink whitespace-pre-wrap bg-canvas-soft-2 p-4 rounded-md max-h-72 overflow-auto border border-hairline">
                  {detail?.mineru_markdown || "(MinerU 未解析或无内容)"}
                </div>
              )}

              {/* Tags */}
              {tab === "tags" && (
                <div className="text-sm space-y-4">
                  <div>
                    <div className="text-xs font-mono uppercase tracking-wider text-mute mb-2">已打标签</div>
                    {slideTags.length === 0 ? (
                      <span className="text-xs text-mute">暂无标签,从下方添加</span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {slideTags.map((t) => {
                          const isAi = t.origin === "ai";
                          return (
                            <span
                              key={t.id}
                              className={cn(
                                "group inline-flex items-center gap-1 text-xs px-2 py-1 border rounded-full",
                                isAi
                                  ? "bg-violet-soft text-violet border-transparent"
                                  : "bg-canvas-soft-2 text-ink border-hairline",
                              )}
                            >
                              {t.tag.name}
                              {t.tag.category && <span className="text-mute">{t.tag.category}</span>}
                              {isAi && (
                                <span className="text-[14px] font-mono uppercase opacity-70">AI</span>
                              )}
                              <button
                                type="button"
                                onClick={() => removeTag(t)}
                                className="text-mute hover:text-error leading-none ml-0.5"
                                title="移除标签"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="text-xs font-mono uppercase tracking-wider text-mute mb-2">添加标签</div>
                    {(() => {
                      const usedNames = new Set(slideTags.map((t) => t.tag.name));
                      const available = allTags.filter((t) => !usedNames.has(t.name));
                      return (
                        <div className="flex items-center gap-2">
                          <select
                            value={addTagId}
                            onChange={(e) => setAddTagId(e.target.value)}
                            disabled={available.length === 0 || tagBusy}
                            className="flex-1 h-9 px-3 text-sm bg-canvas text-ink border border-hairline rounded-sm outline-none focus:border-hairline-strong disabled:bg-canvas-soft-2 disabled:text-mute"
                          >
                            <option value="">{available.length === 0 ? "所有标签已添加" : "选择标签…"}</option>
                            {available.map((t) => (
                              <option key={t.id} value={t.id}>
                                {t.name}
                                {t.category ? ` (${t.category})` : ""}
                              </option>
                            ))}
                          </select>
                          <Button size="md" variant="primary" onClick={addTag} disabled={!addTagId || tagBusy} loading={tagBusy}>
                            添加
                          </Button>
                        </div>
                      );
                    })()}
                    {allTags.length === 0 && (
                      <div className="text-xs text-mute mt-1.5">还没有任何标签,请先到「标签管理」创建。</div>
                    )}
                  </div>
                </div>
              )}

              {/* File */}
              {tab === "file" && (
                <div className="text-sm space-y-2">
                  <Row label="所属文件">
                    {slide.presentation_title || detail?.presentation_title || "-"}
                  </Row>
                  {slide.presentation_title && (
                    <Link href="/files" className="text-link hover:underline inline-block">
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

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="w-20 shrink-0 text-mute">{label}</span>
      <span className="text-body flex-1">{children}</span>
    </div>
  );
}
