"use client";

import { useEffect, useState } from "react";
import { ListChecks, RefreshCw } from "lucide-react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import { jobStatus } from "@/lib/status";
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
}

export default function JobsPage() {
  const toast = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);

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

  async function retry(id: string) {
    try {
      await api.post(`/api/jobs/${id}/retry`);
      toast.success("已提交重试");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "重试失败");
    }
  }

  return (
    <AppShell title="任务中心">
      <div className="space-y-4">
        {jobs.length === 0 ? (
          <EmptyState icon={<ListChecks className="w-5 h-5" />} title="暂无任务" description="上传文件后,解析、渲染、AI 分析任务会出现在这里,每 3 秒自动刷新。" />
        ) : (
          <Table>
            <THead>
              <TH>任务类型</TH>
              <TH>阶段</TH>
              <TH>状态</TH>
              <TH>进度</TH>
              <TH>错误</TH>
              <TH>创建时间</TH>
              <TH className="text-right">操作</TH>
            </THead>
            <TBody>
              {jobs.map((j) => {
                const st = jobStatus(j.status);
                return (
                  <TR key={j.id}>
                    <TD className="font-mono text-xs text-ink">{j.job_type}</TD>
                    <TD>{j.stage || "-"}</TD>
                    <TD>
                      <Badge tone={st.tone} dot>
                        {st.label}
                      </Badge>
                    </TD>
                    <TD className="text-mute font-mono">{j.progress}%</TD>
                    <TD className="text-xs text-error-deep max-w-xs truncate" title={j.error_message || ""}>
                      {j.error_code ? `${j.error_code}: ${j.error_message || ""}` : "-"}
                    </TD>
                    <TD className="text-mute text-xs">{new Date(j.created_at).toLocaleString("zh-CN")}</TD>
                    <TD className="text-right">
                      {j.status === "failed" && (
                        <Button size="sm" variant="ghost" leadingIcon={<RefreshCw className="w-3.5 h-3.5" />} onClick={() => retry(j.id)}>
                          重试
                        </Button>
                      )}
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </div>
    </AppShell>
  );
}
