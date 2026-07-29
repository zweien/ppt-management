# ADR-0001:技术栈与架构基线

- **状态**:已接受
- **日期**:2026-07-29
- **决策者**:产品/工程(基于 PRD V1.0 §17.1–17.3)
- **取代**:无

## 背景

PPT 素材库的 PRD 已确定部署形态为"Linux + Docker,单管理员,后续团队化扩展",并给出了完整的技术栈建议。在进入开发前,需要把技术栈选择固化为架构基线,后续所有详细设计(检索、渲染、解析、模型层)都建立在此之上。

## 决策

采用 PRD §17.3 推荐的技术栈作为项目基线:

| 层 | 选型 |
|---|---|
| 前端 | Next.js + TypeScript + shadcn/ui + Tailwind CSS + TanStack Query |
| 后端 | Python + FastAPI + SQLAlchemy 2 + Alembic + Pydantic |
| 任务 | Celery + Redis(worker 分四组:basic / render / mineru / ai) |
| 数据库 | PostgreSQL + pgvector(可选 pg_trgm) |
| 存储 | MinIO(底层可挂 NAS) |
| PPT 处理 | zipfile/lxml 自研 Open XML 解析与导出 + LibreOffice Headless 渲染 |
| 文档增强 | MinerU 独立服务 |
| 模型 | OpenAI 兼容 HTTP API |
| 部署 | Docker Compose,Linux |

## 理由

- **BS 架构 + 页级检索**需要前端富交互(Next.js)与高性能后端 API(FastAPI),二者生态成熟。
- **页级素材 + 混合检索**天然需要 PostgreSQL 的全文检索能力与 pgvector 的向量能力,合并在一个库里避免数据搬运。
- **重计算任务(PPT 解析/渲染/模型调用)异步化**,用 Celery 分组 worker,避免阻塞 API。
- **对象存储抽象(MinIO)**保证源 PPTX 与派生文件的不可变性,数据卷可挂 NAS 便于扩展。
- 全部组件开源、可内网/本地部署,符合"可替换模型与解析组件"的产品目标。

## 后果

- **正面**:栈成熟、社区大、Docker Compose 一键起全栈;前后端边界清晰;检索能力(全文+向量)收敛在 PostgreSQL 一个引擎内。
- **负面**:四组 Celery worker + LibreOffice + MinerU + 模型服务的运维复杂度不低,需要配套任务中心与可观测性(PRD §18.3)。MinIO/PostgreSQL/Redis 多个有状态服务,备份策略需统一版本点。
- **中性**:Open XML 解析与单页导出需自研(PRD 已决定不依赖 python-pptx 重绘),见 ADR-0002。

## 关联

- 单页 PPTX 导出的"禁止重建页面"约束 → ADR-0002
- 混合检索的融合方法 → ADR-0003
- 中文分词方案 → ADR-0004
- LibreOffice 渲染并发模型 → ADR-0005
- 模型配置与密钥管理 → ADR-0006
