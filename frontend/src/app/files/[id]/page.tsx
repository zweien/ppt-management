"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Download, RefreshCw, ArrowRight, ChevronLeft } from "lucide-react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import SlideCard, { type SlideCardData } from "@/components/SlideCard";
import SlideDetailDrawer from "@/components/SlideDetailDrawer";
import { api, ApiError, API_BASE } from "@/lib/api";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Input";
import EmptyState from "@/components/ui/EmptyState";
import Modal, { ConfirmFooter } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

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
  details: Record<string, unknown>;
}

const DIFF_TONE: Record<string, "default" | "warning" | "success" | "error" | "info"> = {
  unchanged: "default",
  modified: "warning",
  added: "success",
  deleted: "error",
  rearranged: "info",
};
const DIFF_LABEL: Record<string, string> = {
  unchanged: "未变化",
  modified: "修改",
  added: "新增",
  deleted: "删除",
  rearranged: "重排",
};

export default function FileDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const toast = useToast();
  const [pres, setPres] = useState<Presentation | null>(null);
  const [slides, setSlides] = useState<SlideCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<SlideCardData | null>(null);
  const [reparsing, setReparsing] = useState(false);
  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffFrom, setDiffFrom] = useState("");
  const [diffTo, setDiffTo] = useState("");
  const [switchTarget, setSwitchTarget] = useState<Version | null>(null);
  const [switching, setSwitching] = useState(false);

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
      toast.error(e instanceof ApiError ? e.message : "加载失败");
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
      const res = await fetch(`${API_BASE}/api/presentations/${fileId}/download-source`, {
        credentials: "include", // 带 session cookie(SSO)
      });
      if (!res.ok) throw new Error("下载失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${pres?.title}.pptx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("下载失败");
    }
  }

  async function reparse() {
    setReparsing(true);
    try {
      const r = await api.post<{ detail: string }>(`/api/presentations/${id}/reparse`);
      toast.success(r.detail);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "重新解析失败");
    } finally {
      setReparsing(false);
    }
  }

  async function confirmSwitch() {
    if (!switchTarget) return;
    setSwitching(true);
    try {
      await api.post(`/api/presentations/${id}/versions/${switchTarget.id}/set-current`);
      toast.success("已切换当前版本");
      setSwitchTarget(null);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "切换失败");
    } finally {
      setSwitching(false);
    }
  }

  async function showDiff() {
    if (!diffFrom || !diffTo || diffFrom === diffTo) {
      toast.error("请选择两个不同的版本");
      return;
    }
    setDiffLoading(true);
    try {
      const d = await api.get<VersionDiff>(
        `/api/presentations/${id}/version-diff?from_vid=${diffFrom}&to_vid=${diffTo}`,
      );
      setDiff(d);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "获取差异失败");
    } finally {
      setDiffLoading(false);
    }
  }

  return (
    <AppShell title={pres ? `文件详情:${pres.title}` : "文件详情"}>
      <div className="space-y-6">
        <Link href="/files" className="inline-flex items-center gap-1 text-sm text-link hover:underline">
          <ChevronLeft className="w-4 h-4" /> 返回文件列表
        </Link>

        {pres && (
          <div className="bg-surface rounded-md shadow-e2 p-5">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="min-w-0">
                <div className="font-medium text-ink">{pres.title}</div>
                <div className="text-xs text-mute mt-1 font-mono">
                  {pres.page_count} 页 · 状态 {pres.current_status} · {pres.versions.length} 个版本
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <Button
                  variant="secondary"
                  size="md"
                  leadingIcon={<Download className="w-3.5 h-3.5" />}
                  onClick={() => downloadSource(id)}
                >
                  下载源 PPTX
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  leadingIcon={<RefreshCw className="w-3.5 h-3.5" />}
                  loading={reparsing}
                  onClick={reparse}
                  title="重新触发 MinerU 增强解析(及视觉/embedding,若已配置模型)"
                >
                  重新解析
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Version panel (multi-version only) */}
        {pres && pres.versions.length > 1 && (
          <div className="bg-surface rounded-md shadow-e2 p-5">
            <div className="text-sm font-medium text-ink mb-3">版本管理(共 {pres.versions.length} 个版本)</div>
            <div className="space-y-2 mb-4">
              {pres.versions.map((v) => {
                const current = pres.current_version_id === v.id;
                return (
                  <div
                    key={v.id}
                    className={cn(
                      "flex items-center justify-between text-sm py-2.5 px-3 rounded-md border",
                      current ? "border-success/40 bg-success-soft" : "border-hairline",
                    )}
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono font-medium text-ink">v{v.version_no}</span>
                      {current && <Badge tone="success">当前</Badge>}
                      <span className="text-xs text-mute">
                        {v.page_count} 页 · {new Date(v.created_at).toLocaleString("zh-CN")} ·{" "}
                        {(v.file_size / 1024).toFixed(0)} KB
                      </span>
                    </div>
                    {!current && (
                      <Button size="sm" variant="secondary" onClick={() => setSwitchTarget(v)}>
                        设为当前
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
            {/* Version diff */}
            <div className="flex items-center gap-2 text-xs text-body flex-wrap pt-3 border-t border-hairline">
              <span className="font-mono uppercase tracking-wider text-mute">版本对比</span>
              <Select inputSize="sm" value={diffFrom} onChange={(e) => setDiffFrom(e.target.value)} className="w-28">
                <option value="">旧版本</option>
                {pres.versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_no}
                  </option>
                ))}
              </Select>
              <ArrowRight className="w-3.5 h-3.5 text-mute" />
              <Select inputSize="sm" value={diffTo} onChange={(e) => setDiffTo(e.target.value)} className="w-28">
                <option value="">新版本</option>
                {pres.versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_no}
                  </option>
                ))}
              </Select>
              <Button size="sm" variant="primary" onClick={showDiff} loading={diffLoading}>
                对比
              </Button>
            </div>
            {diff && (
              <div className="mt-4 flex flex-wrap gap-2">
                {Object.entries(diff.summary).map(([type, count]) => (
                  <Badge key={type} tone={DIFF_TONE[type] || "default"}>
                    {DIFF_LABEL[type] || type} · {count}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}

        {loading ? (
          <div className="text-mute text-sm">加载中...</div>
        ) : slides.length === 0 ? (
          <EmptyState
            title="暂无页面数据"
            description={
              pres?.current_status === "PARSING" || pres?.current_status === "RENDERING"
                ? "解析/渲染进行中,请稍候..."
                : undefined
            }
          />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {slides.map((s) => (
              <SlideCard key={s.id} slide={s} onOpen={setActive} />
            ))}
          </div>
        )}
      </div>

      <SlideDetailDrawer slide={active} onClose={() => setActive(null)} />

      <Modal
        open={!!switchTarget}
        onClose={() => setSwitchTarget(null)}
        title="切换当前版本?"
        description={
          switchTarget ? `将设为 v${switchTarget.version_no} 为当前版本,搜索默认只检索当前版本。` : ""
        }
        size="sm"
        footer={
          <ConfirmFooter
            confirmText="切换"
            loading={switching}
            onCancel={() => setSwitchTarget(null)}
            onConfirm={confirmSwitch}
          />
        }
      />
    </AppShell>
  );
}
