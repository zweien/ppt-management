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
