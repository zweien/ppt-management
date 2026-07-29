// Shared status → Badge tone + label helpers (Vercel semantic palette).

export type BadgeTone = "default" | "primary" | "success" | "warning" | "error" | "violet" | "info";

/** Map a presentation/file status to a Badge tone + human label. */
export function presStatus(status: string): { tone: BadgeTone; label: string } {
  switch (status) {
    case "BASIC_READY":
    case "READY":
      return { tone: "success", label: "就绪" };
    case "UPLOADING":
    case "PARSING":
    case "RENDERING":
    case "PARSED":
      return { tone: "info", label: "处理中" };
    case "PARTIAL_FAILED":
    case "FAILED":
      return { tone: "error", label: "失败" };
    default:
      return { tone: "default", label: status || "-" };
  }
}

/** Map a job status to a Badge tone + label. */
export function jobStatus(status: string): { tone: BadgeTone; label: string } {
  switch (status) {
    case "success":
      return { tone: "success", label: "成功" };
    case "running":
      return { tone: "info", label: "运行中" };
    case "pending":
      return { tone: "default", label: "等待中" };
    case "failed":
      return { tone: "error", label: "失败" };
    default:
      return { tone: "default", label: status };
  }
}

/** Friendly Chinese labels for raw job_type slugs. */
export const JOB_TYPE_LABELS: Record<string, string> = {
  validate_pptx: "校验 PPTX",
  parse_openxml: "OpenXML 解析",
  render_preview: "渲染预览",
  parse_mineru: "MinerU 解析",
  analyze_visual: "视觉分析",
  build_embedding: "生成 Embedding",
};

export function jobTypeLabel(t: string): string {
  return JOB_TYPE_LABELS[t] || t;
}

/** Friendly Chinese labels for raw stage slugs. */
export const STAGE_LABELS: Record<string, string> = {
  UPLOADING: "上传中",
  VALIDATING: "校验中",
  PARSING: "解析中",
  RENDERING: "渲染中",
  ENRICHING: "增强中",
};

export function stageLabel(s: string | null | undefined): string | null {
  if (!s) return null;
  return STAGE_LABELS[s] || s;
}

/** Format a human-readable duration between two ISO timestamps.
 *  Returns e.g. "1.2s", "45s", "2m 10s", or null if not computable. */
export function formatDuration(
  startedAt?: string | null,
  finishedAt?: string | null,
): string | null {
  if (!startedAt || !finishedAt) return null;
  const start = new Date(startedAt).getTime();
  const end = new Date(finishedAt).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null;
  const ms = end - start;
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)}s`;
  const m = Math.floor(s / 60);
  const rs = Math.round(s % 60);
  return rs ? `${m}m ${rs}s` : `${m}m`;
}
