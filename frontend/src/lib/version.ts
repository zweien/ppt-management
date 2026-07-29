// 版本号获取与 CHANGELOG 展示数据。
// 版本号单一真相源在后端 backend/app/__init__.py 的 __version__,
// 前端启动时从 GET / 拉取并缓存到 localStorage(避免每个页面重复请求)。
// CHANGELOG 内容作为结构化静态数据维护,与根目录 CHANGELOG.md 保持同步。

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const VERSION_CACHE_KEY = "app_version";
const VERSION_CACHE_TS_KEY = "app_version_ts";
// 缓存有效期:1 小时(版本不常变,避免频繁请求)
const CACHE_TTL_MS = 60 * 60 * 1000;

/**
 * 获取当前版本号。优先用 localStorage 缓存(1h TTL),过期或无缓存时 fetch GET /。
 * fetch 失败时回退到缓存值或 fallback。
 */
export async function fetchVersion(fallback = ""): Promise<string> {
  const cached = typeof window !== "undefined" ? localStorage.getItem(VERSION_CACHE_KEY) : null;
  const cachedTs = typeof window !== "undefined" ? localStorage.getItem(VERSION_CACHE_TS_KEY) : null;
  const fresh = cachedTs && Date.now() - Number(cachedTs) < CACHE_TTL_MS;
  if (cached && fresh) return cached;

  try {
    const res = await fetch(`${API_BASE}/`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      const v = data.version as string;
      if (v && typeof window !== "undefined") {
        localStorage.setItem(VERSION_CACHE_KEY, v);
        localStorage.setItem(VERSION_CACHE_TS_KEY, String(Date.now()));
      }
      return v || cached || fallback;
    }
  } catch {
    /* 离线/后端未启动,用缓存或 fallback */
  }
  return cached || fallback;
}

/** 同步读取缓存的版本号(用于 SSR / 首屏,不触发网络请求)。 */
export function getCachedVersion(fallback = ""): string {
  if (typeof window === "undefined") return fallback;
  return localStorage.getItem(VERSION_CACHE_KEY) || fallback;
}

// --- CHANGELOG 结构化数据 ---
// 与根目录 CHANGELOG.md 保持同步。新增版本时在数组头部插入。

export interface ChangelogEntry {
  version: string;
  date: string | null; // ISO 日期或 null(Unreleased)
  sections: { kind: string; items: string[] }[];
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    version: "Unreleased",
    date: null,
    sections: [],
  },
  {
    version: "0.2.0",
    date: "2026-07-29",
    sections: [
      {
        kind: "✨ 新功能",
        items: [
          "统一版本管理:单一真相源(后端 __version__),前端侧边栏显示版本号 + 新增「更新日志」页,AGENTS.md 加入发版流程约定",
          "单页标签管理:详情抽屉「标签」Tab 支持单页加/删标签,显示全部标签(人工 + AI)",
          "单页收藏入口:页面卡片星标 + 详情抽屉收藏按钮,卡片↔抽屉状态双向同步",
        ],
      },
      {
        kind: "🐛 修复",
        items: [
          "高清预览缩放:渲染管线真正缩放到 1920 宽,DPI 150→200,ImageMagick 缺失时优雅回退",
          "补齐 PRD 审计发现的 A 类缺口(搜索字段、上传体验、备注编辑、批量操作、性能压测、评测集)",
        ],
      },
    ],
  },
  {
    version: "0.1.0",
    date: "2026-07-29",
    sections: [
      {
        kind: "🎉 里程碑",
        items: [
          "阶段三 — 版本链 + 单页导出(文件版本识别、Open XML 关系图 BFS 单页 PPTX 导出)",
          "阶段二 — AI 理解 + 语义检索(RRF 混合检索、视觉 AI 分析、结构化加权)",
          "阶段一 — MVP 全栈实现(三层解析、FastAPI + Celery、Next.js 前端、pgvector + MinIO)",
        ],
      },
      {
        kind: "✨ 新功能",
        items: ["统一启动脚本 infra/start.sh 管理宿主机服务 + compose 栈"],
      },
      {
        kind: "🐛 修复",
        items: [
          "单页 PPTX 导出体积从 151MB 降到 1.4MB(过滤未引用 media)",
          "搜索结果卡片高度不一致",
          "MinerU per-page 解析 + reparse UI + 清理 stale error_code",
          "MinerU markdown 去掉图片引用,只保留文字",
        ],
      },
      {
        kind: "📚 文档",
        items: ["README(GitHub 风格)"],
      },
    ],
  },
];
