"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";

interface Job {
  id: string; job_type: string; target_type: string; target_id: string;
  status: string; progress: number; error_code: string | null; error_message: string | null;
  stage: string | null; started_at: string | null; finished_at: string | null; created_at: string;
}

function statusColor(s: string) {
  return { success: "bg-green-100 text-green-700", running: "bg-blue-100 text-blue-700",
           pending: "bg-gray-100 text-gray-600", failed: "bg-red-100 text-red-700" }[s] || "bg-gray-100 text-gray-600";
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [msg, setMsg] = useState("");

  async function load() {
    try { setJobs(await api.get<Job[]>(`/api/jobs?limit=100`)); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "加载失败"); }
  }
  useEffect(() => { load(); const t = setInterval(load, 3000); return () => clearInterval(t); }, []);

  async function retry(id: string) {
    try { await api.post(`/api/jobs/${id}/retry`); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "重试失败"); }
  }

  return (
    <AppShell title="任务中心">
      <div className="space-y-4">
        {msg && <div className="text-sm text-red-600">{msg}</div>}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                <th className="text-left px-4 py-3">任务类型</th>
                <th className="text-left px-4 py-3">阶段</th>
                <th className="text-left px-4 py-3">状态</th>
                <th className="text-left px-4 py-3">进度</th>
                <th className="text-left px-4 py-3">错误</th>
                <th className="text-left px-4 py-3">创建时间</th>
                <th className="text-right px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.map((j) => (
                <tr key={j.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs">{j.job_type}</td>
                  <td className="px-4 py-3 text-gray-600">{j.stage || "-"}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${statusColor(j.status)}`}>{j.status}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{j.progress}%</td>
                  <td className="px-4 py-3 text-xs text-red-500 max-w-xs truncate" title={j.error_message || ""}>
                    {j.error_code ? `${j.error_code}: ${j.error_message || ""}` : "-"}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{new Date(j.created_at).toLocaleString("zh-CN")}</td>
                  <td className="px-4 py-3 text-right">
                    {j.status === "failed" && (
                      <button onClick={() => retry(j.id)} className="text-brand-600 hover:underline text-xs">重试</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {jobs.length === 0 && <div className="p-8 text-center text-gray-400 text-sm">暂无任务</div>}
        </div>
      </div>
    </AppShell>
  );
}
