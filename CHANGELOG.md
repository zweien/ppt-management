# 更新日志 / Changelog

本项目遵循 [SemVer](https://semver.org/lang/zh-CN/) 与 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
版本号单一真相源为 `backend/app/__init__.py` 的 `__version__`,发版流程见 `docs/agents/versioning.md`。

## [Unreleased]

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
