// 上传辅助:客户端 SHA-256 计算 + 文件校验。
import type { UploadLimits } from "./version";

/**
 * 计算文件的 SHA-256(十六进制)。
 * crypto.subtle.digest 需要把整个文件读入内存;受后端 200MB 上限约束,可接受。
 * 返回 null 表示计算失败(如非 HTTPS 环境下 crypto.subtle 不可用)。
 */
export async function computeSha256(file: File): Promise<string | null> {
  try {
    if (typeof crypto === "undefined" || !crypto.subtle) return null;
    const buf = await file.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", buf);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } catch {
    return null;
  }
}

export interface ValidationResult {
  ok: boolean;
  error?: string;
}

/**
 * 选择文件后立即校验:扩展名 + 大小。
 * limits 来自 GET / 的 upload_limits(可配置)。
 */
export function validateFile(file: File, limits: UploadLimits): ValidationResult {
  const name = file.name.toLowerCase();
  const ext = name.slice(name.lastIndexOf("."));
  if (!limits.allowed_extensions.includes(ext)) {
    return { ok: false, error: `不支持的文件类型 ${ext || "(无扩展名)"},仅支持 ${limits.allowed_extensions.join(", ")}` };
  }
  const maxBytes = limits.max_size_mb * 1024 * 1024;
  if (file.size > maxBytes) {
    return { ok: false, error: `文件过大(${(file.size / 1024 / 1024).toFixed(0)} MB),上限 ${limits.max_size_mb} MB` };
  }
  if (file.size === 0) {
    return { ok: false, error: "文件为空" };
  }
  return { ok: true };
}

/** 人类可读的文件大小。 */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
