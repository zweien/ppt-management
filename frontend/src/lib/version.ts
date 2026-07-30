// 版本号获取与 CHANGELOG 展示数据。
// 版本号单一真相源在后端 backend/app/__init__.py 的 __version__,
// 前端启动时从 GET / 拉取并缓存到 localStorage(避免每个页面重复请求)。
// CHANGELOG 内容作为结构化静态数据维护,与根目录 CHANGELOG.md 保持同步。

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const VERSION_CACHE_KEY = "app_version";
const VERSION_CACHE_TS_KEY = "app_version_ts";
const ROOT_CACHE_KEY = "app_root_payload";
// 缓存有效期:1 小时(版本不常变,避免频繁请求)
const CACHE_TTL_MS = 60 * 60 * 1000;

export interface UploadLimits {
  max_size_mb: number;
  allowed_extensions: string[];
}

export interface UiConfig {
  app_name: string;
  logo_url: string | null;
  mesh_enabled: boolean;
  default_theme: "light" | "dark";
}

interface RootPayload {
  version: string;
  upload_limits?: UploadLimits;
  ui_config?: UiConfig;
}

async function fetchRoot(): Promise<RootPayload | null> {
  const cachedTs = typeof window !== "undefined" ? localStorage.getItem(VERSION_CACHE_TS_KEY) : null;
  const fresh = cachedTs && Date.now() - Number(cachedTs) < CACHE_TTL_MS;
  if (fresh) {
    const raw = typeof window !== "undefined" ? localStorage.getItem(ROOT_CACHE_KEY) : null;
    if (raw) {
      try {
        return JSON.parse(raw) as RootPayload;
      } catch {
        /* fall through to fetch */
      }
    }
  }
  try {
    const res = await fetch(`${API_BASE}/`, { cache: "no-store" });
    if (res.ok) {
      const data = (await res.json()) as RootPayload;
      if (typeof window !== "undefined") {
        localStorage.setItem(VERSION_CACHE_KEY, data.version);
        localStorage.setItem(VERSION_CACHE_TS_KEY, String(Date.now()));
        localStorage.setItem(ROOT_CACHE_KEY, JSON.stringify(data));
      }
      return data;
    }
  } catch {
    /* 离线/后端未启动 */
  }
  // fall back to whatever is cached
  const raw = typeof window !== "undefined" ? localStorage.getItem(ROOT_CACHE_KEY) : null;
  return raw ? (JSON.parse(raw) as RootPayload) : null;
}

/**
 * 获取当前版本号。优先用 localStorage 缓存(1h TTL),过期或无缓存时 fetch GET /。
 * fetch 失败时回退到缓存值或 fallback。
 */
export async function fetchVersion(fallback = ""): Promise<string> {
  const cached = typeof window !== "undefined" ? localStorage.getItem(VERSION_CACHE_KEY) : null;
  const payload = await fetchRoot();
  return payload?.version || cached || fallback;
}

/** 同步读取缓存的版本号(用于 SSR / 首屏,不触发网络请求)。 */
export function getCachedVersion(fallback = ""): string {
  if (typeof window === "undefined") return fallback;
  return localStorage.getItem(VERSION_CACHE_KEY) || fallback;
}

/** 获取上传限制(max_size_mb / allowed_extensions),复用 GET / 缓存。 */
export async function fetchUploadLimits(
  fallback: UploadLimits = { max_size_mb: 200, allowed_extensions: [".pptx"] },
): Promise<UploadLimits> {
  const payload = await fetchRoot();
  return payload?.upload_limits || fallback;
}

/** 获取 UI 配置(系统名称/logo/mesh开关/默认主题),复用 GET / 缓存。 */
export async function fetchUiConfig(
  fallback: UiConfig = {
    app_name: "PPT 素材库",
    logo_url: null,
    mesh_enabled: true,
    default_theme: "light",
  },
): Promise<UiConfig> {
  const payload = await fetchRoot();
  return payload?.ui_config || fallback;
}

/** 强制刷新 GET / 缓存(配置改动后调用)。 */
export async function refreshRoot(): Promise<void> {
  if (typeof window !== "undefined") {
    localStorage.removeItem(VERSION_CACHE_TS_KEY);
  }
  await fetchRoot();
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
    version: "0.6.0",
    date: "2026-07-30",
    sections: [
      {
        kind: "✨ 新功能",
        items: [
          "UI 配置(品牌定制):设置页「界面」Tab — logo 上传(MinIO 代理流式返回)、系统名称(全站联动)、mesh 渐变开关、默认主题",
          "支持 .ppt / .pdf 格式:渲染 + OCR 路径(LibreOffice + MinerU),pptx 保持原生解析;source_format + detect_format + 单页导出门控",
        ],
      },
      {
        kind: "🐛 修复",
        items: ["上传去重未排除已软删除版本(join Presentation.deleted_at)"],
      },
    ],
  },
  {
    version: "0.5.0",
    date: "2026-07-30",
    sections: [
      {
        kind: "✨ 新功能",
        items: [
          "管理员设置页:业务可调配置(上传限制/AI服务地址/Token过期/CORS)DB 化,运行时可改、立即生效(DB 优先 + 缓存 30s);新增 AppSetting 表 + runtime_config + require_superuser;前端 5 Tabs(上传/AI/访问/模型配置/系统信息脱敏),模型配置并入设置,/models 重定向",
          "上传体验优化:去双传(客户端算 SHA-256 → /api/uploads/check 预检 → 只传一次)+ UploadQueue 浮层(多文件/并发3/独立进度+取消/重复确认)+ 客户端选择即校验 + 文件列表解析进度条",
        ],
      },
    ],
  },
  {
    version: "0.4.0",
    date: "2026-07-30",
    sections: [
      {
        kind: "✨ 新功能",
        items: [
          "任务中心展示更多信息:后端 JobOut 加 target 名称/parent_id/page_no,GET /api/jobs 批量解析(N+1 安全);前端富表格显示友好类型标签、stage 中文、对象名称、派生耗时、进度条,失败行展开看 error 详情",
          "任务操作列「查看对象」:每行加跳转链接到对应文件详情页",
          "新增 Checkbox 原语(固定尺寸 + shrink-0 + whitespace-nowrap,baseline 对齐)",
        ],
      },
      {
        kind: "🐛 修复",
        items: [
          "侧边栏底部固定:sticky top-0 h-screen,长页面 footer 始终贴底",
          "搜索栏布局:控件高度不齐 + 换行,重设计三行 + 统一 h-7 + Input xs 尺寸 + Tabs 压缩",
          "checkbox 文字竖排:label 被压缩致文字逐字换行,加 shrink-0 + whitespace-nowrap",
        ],
      },
    ],
  },
  {
    version: "0.3.0",
    date: "2026-07-29",
    sections: [
      {
        kind: "✨ 新功能",
        items: [
          "浅色 / 深色双主题:CSS 变量 token 体系 + 自建 ThemeProvider(useEffect 后置切换,避免 SSR hydration 警告),默认浅色,侧边栏 Sun/Moon 切换并持久化",
          "统一 Modal + Toast 原语:替换全部 confirm/prompt/内联 msg;模型新建从 3 连 prompt 改为表单模态",
          "分组导航 IA:资源 / 整理 / 系统三组,caption-mono 小标题分隔,选中态 ink indicator bar",
          "mesh 渐变作品牌符号:首页 hero 与登录页背景使用 Vercel 四对渐变,仅 hero 规模",
        ],
      },
      {
        kind: "♻️ 重构",
        items: [
          "设计 token 化:Tailwind 颜色全部引用 CSS 变量,支持透明度与主题切换",
          "完整共享原语库(Button/Card/Input/Badge/Modal/Toast/EmptyState/DataTable/Tabs/Spinner)",
          "字体 Geist 替代 Inter + JetBrains Mono(next/font 自托管);emoji 全部替换为 lucide-react 线条图标",
          "缩略图改 Vercel card-marketing 范式;状态色统一走 Vercel 三档语义色",
          "重写全部 11 个页面 + SlideCard + SlideDetailDrawer",
        ],
      },
      {
        kind: "🐛 修复",
        items: [
          "SSR hydration 警告:弃用 next-themes,改自建轻量 ThemeProvider(useEffect 后置切换);ToastProvider portal 加 mounted gate 延迟到 hydration 后",
        ],
      },
    ],
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
