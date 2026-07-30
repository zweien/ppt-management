# 更新日志 / Changelog

本项目遵循 [SemVer](https://semver.org/lang/zh-CN/) 与 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
版本号单一真相源为 `backend/app/__init__.py` 的 `__version__`,发版流程见 `docs/agents/versioning.md`。

## [Unreleased]

## [0.7.0] - 2026-07-30

本版聚焦:权限分层 + 私有素材、文件管理增强(重命名/批量/筛选/文件夹)、回收站永久删除。

### ✨ 新功能

- **私有素材(权限分层)**:`Presentation.visibility`(private/team)。private 仅 owner + 超管可见;team 全库可见(现有行为)。上传默认 team,可改 private。新增 `visibility_filter` helper,在全部查询点(列表/详情/搜索/下载/导出/版本/回收站)与 `hybrid_search` 的文本/向量召回强制过滤;`can_access` / `can_modify` 依赖贯穿所有单资源端点;`User.is_superuser` 默认改 False(migration 0008 回填存量 admin) (`0008_visibility_folders.py`)
- **单层文件夹**:`Folder` 表(组织工具,不绑 visibility)。新增 `GET/POST/PATCH/DELETE /api/folders`;删除文件夹时其文件 `folder_id` 置空。文件页顶部文件夹下拉 + 行内「移动到文件夹」
- **文件管理增强**:行内重命名、切可见性(team/private 图标)、批量删除 / 批量重新解析(`POST /api/presentations/batch`)、列表筛选(状态/文件夹/可见性)+ 排序(上传时间/页数/标题)+ 标题模糊搜索;`PATCH /api/presentations/{id}` 统一改名/移动/改可见性
- **回收站永久删除**:单条「永久删除」(`DELETE /api/presentations/{id}/permanent`,清 MinIO 前缀 + 级联 DB:slide_tags/favorites/version_slide_matches/slides/jobs/versions)+ 顶部「清空回收站」(超管 `DELETE /api/trash/empty`)。`StorageClient` 加 `delete_object` / `delete_by_prefix` (boto3)
- **上传者字段**:文件列表加「上传者」列(`owner_name`,批量解析避免 N+1)+ 「仅我上传的」checkbox(`mine` 参数)

### 🐛 修复

- **文件页筛选栏宽度**:下拉菜单被 `w-full` 拉成满宽,改用外层 `<div>` 限宽(状态/可见性/排序 112px、文件夹 144px),Select 内部 `w-full` 填满父级;搜索框独占一行,下拉 + checkbox 单行排列不换行

## [0.6.0] - 2026-07-30

本版聚焦:UI 配置(品牌定制)+ 多格式上传(.ppt/.pdf)。

### ✨ 新功能

- **UI 配置(品牌定制)**:设置页「界面」Tab — logo 上传(MinIO 存储,代理流式返回,无需认证)、系统名称(侧边栏/登录/首页/浏览器标题联动)、mesh 渐变开关、默认主题。`GET /` 加 `ui_config`;ThemeProvider 在用户未选主题时 fallback 配置默认值 (`e493847`)
- **支持 .ppt / .pdf 格式**:走「渲染 + OCR」路径(LibreOffice 渲染 + MinerU OCR 提取文字),`.pptx` 保持高保真 OpenXML 解析。`PresentationVersion.source_format` + `detect_format`(magic bytes)+ render_preview 内建空 slide 行 + 单页导出门控(非 pptx 隐藏) (`e3efb7e`)

### 🐛 修复

- 上传去重(dedup)未排除已软删除版本:重复上传已删文件会命中软删 version,现 join `Presentation.deleted_at.is_(None)` (`e3efb7e`)

## [0.5.0] - 2026-07-30

本版聚焦:上传体验优化 + 管理员设置页(配置全量 DB 化)。

### ✨ 新功能

- **管理员设置页**:业务可调配置(上传限制、AI 服务地址、Token 过期、CORS)从 env 迁到 DB,运行时可改、立即生效(api/worker 缓存 ≤30s)。新增 `AppSetting` 表 + `runtime_config`(DB 优先 fallback env,内存缓存 TTL 30s)+ `require_superuser` 依赖 + `GET/PATCH /api/settings`。前端 5 Tabs 设置页(上传与安全 / AI 服务 / 访问与安全 / 模型配置 / 系统信息只读脱敏);模型配置从独立页并入设置,`/models` 重定向 (`000c83d`)
- **上传体验优化**:解决文件被传输两次的根因(原 suggest-version 先传一遍找相似,uploads 再传一遍)。客户端算 SHA-256 → `/api/uploads/check` 预检查重 → 只传一次;新增 `UploadQueue` 浮层(多文件、并发限 3、独立进度+取消、重复确认 Modal);客户端选择即校验(扩展名/大小,上限从 `GET /` 的 `upload_limits` 拉取);文件列表处理中行显示解析进度条(`PresentationOut` 加 `parse_progress`/`parse_stage`) (`d4dade0`)

### 🐛 修复

- 无(本版无独立修复,见 0.4.0 及之前)

## [0.4.0] - 2026-07-30

本版聚焦:任务中心信息密度增强 + 搜索栏/侧边栏 UX 修复。

### ✨ 新功能

- **任务中心展示更多信息**:JobOut 加 `target_name` / `target_parent_name` / `target_parent_id` / `target_page_no`,后端 `GET /api/jobs` 批量解析 target 名称(N+1 安全,100 条仅 3 次查询);前端富表格显示友好类型标签(`parse_mineru`→MinerU 解析)、stage 中文、对象名称(文件名/第N页)、派生耗时(`finished - started`)、进度条,失败任务行展开看 error_code + 完整 message (`771bc10`)
- **任务操作列「查看对象」**:每行加跳转链接到对应文件详情页(`/files/{parent_id}`),解决非失败任务操作列为空的问题 (`ce64c2c`)
- **Checkbox 原语**(`src/components/ui/Checkbox.tsx`):固定 16px 输入 + h-7 label + shrink-0 + whitespace-nowrap,baseline 对齐 (`eb7005f`)

### 🐛 修复

- **侧边栏底部固定**:长页面时 aside 随主内容拉高导致 footer 被推到文档底部,改 `sticky top-0 h-screen` 固定视口高度吸顶,footer 始终贴底 (`950dbca`)
- **搜索栏布局**:checkbox/select/tabs 高度不齐(28/32/40px)且换行成 96px;重设计为输入行 / 快捷词 / 结果控件三行,统一 h-7,Input 新增 xs 尺寸,Tabs 压缩到 h-7 (`0df7b6c`)
- **checkbox 文字竖排**:label flex-shrink:1 被压缩 + whiteSpace:normal 致文字逐字换行;加 shrink-0 + whitespace-nowrap (`fcf0cf6`)

## [0.3.0] - 2026-07-29

本版聚焦:按 Vercel 设计语言全量重构前端 UX,从早期 Tailwind 模板升级到专业系统级体验。

### ✨ 新功能

- **浅色 / 深色双主题**:CSS 变量 token 体系 + 自建 ThemeProvider(`useEffect` 后置切换,避免 SSR hydration 警告),默认浅色(Vercel 原生),侧边栏 Sun/Moon 切换并持久化到 localStorage
- **统一 Modal + Toast 原语**:替换全部 `window.confirm` / `window.prompt` / 内联 msg 文本——文件删除、版本切换、模型删除走统一确认弹窗;模型新建从 3 连 `prompt` 改为表单模态;操作反馈统一走 Toast
- **分组导航 IA**:侧边栏按 资源 / 整理 / 系统 三组组织,caption-mono 小标题分隔,选中态左侧 ink indicator bar
- **mesh 渐变作品牌符号**:首页 hero 与登录页背景使用 Vercel 四对渐变(青/蓝/紫红/珊瑚/琥珀),仅 hero 规模使用

### ♻️ 重构

- **设计 token 化**:Tailwind 颜色全部引用 CSS 变量(`rgb(var(--token))`),支持 `<alpha-value>` 透明度与主题切换;建立 canvas / surface / ink / hairline / primary / link / semantic 七类语义 token
- **完整共享原语库**(`src/components/ui/`):Button / Card / Input(含 Select/Textarea/Field)/ Badge / Modal / Toast(Provider + `useToast`)/ EmptyState / DataTable / Tabs / Spinner
- **字体**:Geist 替代方案 Inter + JetBrains Mono,经 `next/font/google` 自托管
- **图标**:emoji 全部替换为 `lucide-react` 线条图标
- **缩略图范式**:幻灯片卡片改为 Vercel `card-marketing`(surface + hairline + 堆叠阴影 + 16:9 不裁切)
- **状态色统一**:文件/任务状态、搜索命中原因、版本 diff 全部走 Vercel 三档语义色(success/warning/error + soft/deep)
- 重写全部 11 个页面 + SlideCard + SlideDetailDrawer,核心交互保留(乐观更新 / XHR 上传进度 / 3s 轮询 / 拖拽 / 单页标签管理)

### 🐛 修复

- **SSR hydration 警告**:弃用 next-themes(其 inline script 在 React hydrate 前改写 `<html>` 触发 #418/#423),改自建轻量 ThemeProvider(`useEffect` 后置切换);ToastProvider 的 portal 渲染加 `mounted` gate 延迟到 hydration 后,消除全部页面的 hydration 不匹配


## [0.2.0] - 2026-07-29

本版聚焦:版本管理体系建立 + 单页操作体验补全(收藏、标签)+ 预览质量修复。

### ✨ 新功能

- **统一版本管理**:建立单一版本真相源(后端 `__version__`),前端侧边栏显示版本号 + 新增「更新日志」页,AGENTS.md 加入发版流程约定 (`73a5d25` 同批次)
- **单页标签管理**:详情抽屉「标签」Tab 支持单页加/删标签,显示全部标签(人工 + AI),后端新增 `POST /api/slides/{id}/tags/{tag_id}` 单页接口 (`73a5d25`)
- **单页收藏入口**:页面卡片右上角星标 + 详情抽屉收藏按钮,卡片↔抽屉状态双向同步 (`09ec3ec`)
- 后端 `SlideOut` 新增 `is_favorite` 字段,各列表/详情接口批量填充(避免 N+1)

### 🐛 修复

- **高清预览缩放**:渲染管线真正缩放到 1920 宽(原代码注释承诺但未执行),DPI 150→200,ImageMagick 缺失时优雅回退 (`1623546`)
- 补齐 PRD 审计发现的 A 类缺口:搜索字段补全、上传拖拽/进度/取消、备注编辑、批量操作、性能压测、评测集 (`d09e13a`)

## [0.1.0] - 2026-07-29

首个完整版本,覆盖 PRD-MVP 全部能力。包含三个阶段里程碑。

### 🎉 里程碑:阶段三 — 版本链 + 单页导出 (`25b94ad`)

- 文件版本识别(fingerprint-set Jaccard 相似度)与版本页匹配(pHash)
- 单页 PPTX 导出:Open XML 关系图 BFS 遍历,复制依赖媒体

### 🎉 里程碑:阶段二 — AI 理解 + 语义检索 (`a311931`)

- 视觉 AI 分析(JSON Schema strict,生成摘要 + 五维标签)
- 混合检索(RRF 融合关键词 + 向量,bge-m3 1024 维 embedding,`9e5fbb5`)
- 结构化加权(标题/文件名精确、标签、收藏)

### 🎉 里程碑:阶段一 — MVP 全栈实现 (`3ebafca`)

- 三层解析:Open XML(真值)/ LibreOffice 渲染(预览)/ MinerU + 视觉(可编辑)
- FastAPI + SQLAlchemy 2 + Celery + Redis 后端
- Next.js 14 + TypeScript + Tailwind(清华紫主题)前端
- PostgreSQL 16 + pgvector + pg_trgm + MinIO

### ✨ 新功能(各阶段)

- 统一启动脚本 `infra/start.sh` 管理宿主机服务 + compose 栈 (`fe9d22a`)

### 🐛 修复(各阶段)

- 单页 PPTX 导出体积从 151MB 降到 1.4MB(过滤未引用 media) (`5586bd4`)
- 搜索结果卡片高度不一致 (`a95eb73`)
- MinerU per-page 解析 + reparse UI + 清理 stale error_code (`4775f03`)
- MinerU markdown 去掉图片引用,只保留文字 (`e5c4181`)

### 📚 文档

- README(GitHub 风格) (`bfab865`)
