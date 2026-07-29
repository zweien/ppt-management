Status: done

# 01 — 项目脚手架:全栈可从零启动

## Parent

阶段一 MVP(`.scratch/phase-1-foundation/`)。

## What to build

搭建整个系统的运行骨架,使一条最薄的端到端路径可以从零启动并验证连通性:用 `docker compose up` 启动全部基础服务(web / api / postgres / redis / minio),浏览器能打开前端首页,FastAPI 健康检查能返回各依赖服务(PostgreSQL、Redis、MinIO)的可达状态。

这是后续所有 vertical slice 的地基。要求:

- **目录结构**确立 monorepo 布局(`backend/`、`frontend/`、`infra/`、`docs/`),后续 slice 不再为布局返工。
- **数据库**使用 PostgreSQL + pgvector 扩展(扩展现阶段一就装上,阶段二要用,避免后期迁移)。
- **对象存储**使用 MinIO,应用通过 S3 兼容 SDK 以对象键访问,不在 DB 存大二进制(遵守 CONTEXT.md「对象存储抽象」)。
- **配置**通过环境变量 + `.env.example` 注入,secrets 走 Docker secret / env(ADR-0006 的 Fernet 主密钥位也预留 `APP_ENCRYPTION_KEY`)。
- **健康检查**覆盖数据库、Redis、MinIO 三个有状态依赖。

注意:本 slice **不**实现任何业务功能(无认证、无上传、无解析),只搭骨架与连通性。

## Acceptance criteria

- [ ] `docker compose up` 能在干净的 Linux 环境从零启动全部基础服务,无手动干预
- [ ] 前端首页可访问,显示一个占位 landing
- [ ] FastAPI `/health` 返回数据库、Redis、MinIO 各自的可达状态(ok / fail)
- [ ] pgvector 扩展在 PostgreSQL 中已安装(`SELECT * FROM pg_extension WHERE extname='vector'` 有结果)
- [ ] MinIO bucket 已创建,应用能通过 SDK 上传/下载一个测试对象
- [ ] `.env.example` 列出全部所需环境变量,带注释说明用途
- [ ] monorepo 目录结构(`backend/`、`frontend/`、`infra/`、`docs/`)已建立

## Blocked by

None — can start immediately.
