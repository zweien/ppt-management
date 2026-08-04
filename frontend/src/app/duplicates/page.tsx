"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Copy, Layers, RefreshCw } from "lucide-react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import Spinner from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";

interface DupSlide {
  slide_id: string;
  page_no: number;
  title: string | null;
  presentation_id: string;
  presentation_title: string | null;
  thumbnail_url: string | null;
  distance: number | null;
}

interface DupGroup {
  kind: "exact" | "similar";
  slides: DupSlide[];
}

export default function DuplicatesPage() {
  const toast = useToast();
  const [groups, setGroups] = useState<DupGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load(showSpinner = false) {
    if (showSpinner) setRefreshing(true);
    try {
      setGroups(await api.get<DupGroup[]>("/api/duplicates"));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exactGroups = groups.filter((g) => g.kind === "exact");
  const similarGroups = groups.filter((g) => g.kind === "similar");
  const totalSlides = groups.reduce((n, g) => n + g.slides.length, 0);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* 头部 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink">重复页面</h1>
            <p className="text-sm text-mute mt-1">
              全库扫描高度重复的页面(文本完全相同的「完全重复」+ 视觉高度相似的「高度相似」),
              共 {groups.length} 组 / {totalSlides} 页。重复页无法从源文件中单独删除,
              若整个文件冗余可在「文件管理」中删除该文件。
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => load(true)}
            disabled={refreshing}
          >
            <RefreshCw className={refreshing ? "w-4 h-4 animate-spin" : "w-4 h-4"} />
            重新扫描
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-mute text-sm">
            <Spinner className="w-4 h-4" /> 扫描中...
          </div>
        ) : groups.length === 0 ? (
          <EmptyState
            icon={<Copy className="w-5 h-5" />}
            title="未发现重复页面"
            description="库中各页面文本与视觉均无高度重复。随着素材增多,重复组会自动出现在这里。"
          />
        ) : (
          <div className="space-y-4">
            {groups.map((g, gi) => (
              <div key={gi} className="bg-surface rounded-md shadow-e2 p-4 space-y-3">
                {/* 组头 */}
                <div className="flex items-center gap-2">
                  {g.kind === "exact" ? (
                    <Badge tone="error">完全重复</Badge>
                  ) : (
                    <Badge tone="warning">高度相似</Badge>
                  )}
                  <span className="text-sm text-body">
                    {g.slides.length} 页
                    {g.kind === "exact" && "(文本完全相同)"}
                  </span>
                  {/* 涉及的不同文件数 */}
                  <span className="text-xs text-mute">
                    涉及 {new Set(g.slides.map((s) => s.presentation_id)).size} 个文件
                  </span>
                </div>
                {/* 组内页面卡片(横向滚动对比) */}
                <div className="flex gap-3 overflow-x-auto pb-1">
                  {g.slides.map((s) => (
                    <Link
                      key={s.slide_id}
                      href={`/files/${s.presentation_id}`}
                      className="shrink-0 w-44 group/card"
                    >
                      <div className="bg-canvas border border-hairline rounded-sm overflow-hidden transition group-hover/card:border-hairline-strong group-hover/card:shadow-e3">
                        <div className="aspect-video bg-canvas-soft-2 flex items-center justify-center overflow-hidden">
                          {s.thumbnail_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={s.thumbnail_url}
                              alt={`P${s.page_no}`}
                              className="w-full h-full object-contain"
                            />
                          ) : (
                            <Layers className="w-5 h-5 text-mute" />
                          )}
                        </div>
                        <div className="p-2 space-y-0.5">
                          <div className="text-xs font-medium text-ink truncate">
                            P{s.page_no} {s.title || "(无标题)"}
                          </div>
                          <div className="text-[13px] text-mute truncate">
                            {s.presentation_title}
                          </div>
                          {s.distance !== null && (
                            <div className="text-[13px] text-mute">
                              视觉距离 {s.distance}
                              {s.distance === 0 ? "(几乎一致)" : s.distance <= 4 ? "(极相似)" : ""}
                            </div>
                          )}
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
