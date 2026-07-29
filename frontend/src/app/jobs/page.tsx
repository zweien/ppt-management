"use client";

import { useEffect, useState } from "react";
import { ListChecks, RefreshCw, ChevronRight, AlertCircle } from "lucide-react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import {
  jobStatus,
  jobTypeLabel,
  stageLabel,
  formatDuration,
} from "@/lib/status";
import { cn } from "@/lib/cn";
import Button from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import { Table, THead, TH, TBody, TR, TD } from "@/components/ui/DataTable";
import { useToast } from "@/components/ui/Toast";

interface Job {
  id: string;
  job_type: string;
  target_type: string;
  target_id: string;
  status: string;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  stage: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  target_name?: string | null;
  target_parent_name?: string | null;
  target_page_no?: number | null;
}

/** Build the "object" display for a job's target. */
function targetDisplay(j: Job): { primary: string; secondary: string | null } {
  const uuid = j.target_id.slice(0, 8);
  if (j.target_type === "slide") {
    const page = j.target_page_no ? `第 ${j.target_page_no} 页` : null;
    const primary = [page, j.target_name].filter(Boolean).join(" · ") || `slide ${uuid}`;
    return { primary, secondary: j.target_parent_name ?? null };
  }
  // version
  const primary = j.target_name || `version ${uuid}`;
  return { primary, secondary: j.target_parent_name ?? null };
}

export default function JobsPage() {
  const toast = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [retrying, setRetrying] = useState<string | null>(null);

  async function load() {
    try {
      setJobs(await api.get<Job[]>(`/api/jobs?limit=100`));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "加载失败");
    }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function retry(id: string) {
    setRetrying(id);
    try {
      await api.post(`/api/jobs/${id}/retry`);
      toast.success("已提交重试");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "重试失败");
    } finally {
      setRetrying(null);
    }
  }

  return (
    <AppShell title="任务中心">
      {jobs.length === 0 ? (
        <EmptyState
          icon={<ListChecks className="w-5 h-5" />}
          title="暂无任务"
          description="上传文件后,解析、渲染、AI 分析任务会出现在这里,每 3 秒自动刷新。"
        />
      ) : (
        <Table>
          <THead>
            <TH>任务</TH>
            <TH>对象</TH>
            <TH>状态</TH>
            <TH>耗时</TH>
            <TH>创建时间</TH>
            <TH className="text-right">操作</TH>
          </THead>
          <TBody>
            {jobs.map((j) => {
              const st = jobStatus(j.status);
              const dur = formatDuration(j.started_at, j.finished_at);
              const tgt = targetDisplay(j);
              const isOpen = expanded.has(j.id);
              const isRunning = j.status === "running" || j.status === "pending";
              const hasError = !!(j.error_code || j.error_message);
              const rowClickable = hasError || isRunning;
              return (
                <>
                  <TR
                    key={j.id}
                    className={cn(rowClickable && "cursor-pointer")}
                    onClick={() => rowClickable && toggleExpand(j.id)}
                  >
                    <TD>
                      <div className="flex items-center gap-2">
                        {rowClickable && (
                          <ChevronRight
                            className={cn(
                              "w-3.5 h-3.5 text-mute shrink-0 transition",
                              isOpen && "rotate-90",
                            )}
                          />
                        )}
                        <div className="min-w-0">
                          <div className="font-medium text-ink">{jobTypeLabel(j.job_type)}</div>
                          {j.stage && (
                            <div className="text-xs text-mute mt-0.5">{stageLabel(j.stage)}</div>
                          )}
                        </div>
                      </div>
                    </TD>
                    <TD>
                      <div className="min-w-0">
                        <div className="text-ink truncate max-w-[220px]" title={tgt.primary}>
                          {tgt.primary}
                        </div>
                        {tgt.secondary && (
                          <div
                            className="text-xs text-mute truncate max-w-[220px]"
                            title={tgt.secondary}
                          >
                            {tgt.secondary}
                          </div>
                        )}
                      </div>
                    </TD>
                    <TD>
                      <div className="flex flex-col gap-1.5 min-w-[120px]">
                        <Badge tone={st.tone} dot>
                          {st.label}
                        </Badge>
                        {isRunning && (
                          <div className="w-full h-1 bg-canvas-soft-2 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-300"
                              style={{ width: `${Math.max(j.progress, 3)}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </TD>
                    <TD className="text-mute font-mono text-xs">{dur || "-"}</TD>
                    <TD className="text-mute text-xs whitespace-nowrap">
                      {new Date(j.created_at).toLocaleString("zh-CN")}
                    </TD>
                    <TD className="text-right">
                      {j.status === "failed" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          loading={retrying === j.id}
                          leadingIcon={<RefreshCw className="w-3.5 h-3.5" />}
                          onClick={(e) => {
                            e.stopPropagation();
                            retry(j.id);
                          }}
                        >
                          重试
                        </Button>
                      )}
                    </TD>
                  </TR>
                  {isOpen && (
                    <tr key={`${j.id}-detail`} className="bg-canvas-soft">
                      <td colSpan={6} className="px-4 py-3">
                        <div className="flex items-start gap-2 text-xs">
                          <AlertCircle className="w-4 h-4 text-error-deep shrink-0 mt-0.5" />
                          <div className="min-w-0 flex-1 space-y-1">
                            {hasError ? (
                              <>
                                {j.error_code && (
                                  <div className="font-mono text-error-deep">
                                    {j.error_code}
                                  </div>
                                )}
                                {j.error_message && (
                                  <pre className="font-mono text-body whitespace-pre-wrap break-all bg-canvas border border-hairline rounded p-2 max-h-40 overflow-auto">
                                    {j.error_message}
                                  </pre>
                                )}
                              </>
                            ) : (
                              <div className="text-mute space-y-0.5 font-mono">
                                <div>started: {j.started_at || "-"}</div>
                                <div>finished: {j.finished_at || "-"}</div>
                                <div>target_id: {j.target_id}</div>
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </TBody>
        </Table>
      )}
    </AppShell>
  );
}
