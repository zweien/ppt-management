<div align="center">

# 📊 PPT 素材库

**面向 PPT 页级素材检索、理解、管理与复用的 BS 架构平台**

把每一页 PPT 当作可检索、可理解、可复用的独立素材 —— 搜索结果直达「哪份文件的第几页」,并保留与源文件、版本、原始页码的可追溯关系。

[功能特性](#-功能特性) ·
[快速开始](#-快速开始) ·
[系统架构](#-系统架构) ·
[技术栈](#-技术栈) ·
[路线图](#-路线图) ·
[文档](#-文档)

</div>

---

> 💡 **核心理念**:PPT 是文件实体,**页面**是素材实体。文件名搜索只能定位到文件,而本系统让你按页面主题、用途、视觉风格与自然语言语义,直接定位到具体那一页,并一键复用页面图片、文字或单页 PPTX。

## ✨ 功能特性

- 🔍 **混合检索(关键词 + 语义 + 标签)** —— RRF 排序融合全文召回、pgvector 向量召回与结构化加分,命中原因可视化(「正文命中 / 语义相似 / 标签匹配」)
- 🧠 **AI 页面理解** —— 视觉模型对整页生成结构化分析(摘要、主题、用途、内容形态、视觉风格、适用场景)与 AI 标签,人工标签优先、可修订
- 📄 **三路解析** —— Open XML 原生结构(真值)+ LibreOffice 渲染(预览)+ MinerU 增强 OCR,任一失败不阻断基础可检索
- 🖼️ **页级复用** —— 下载页面 PNG、复制页面文字、下载源 PPTX、(阶段三)导出仅含目标页的单页 PPTX(关系图遍历,保留原生可编辑对象)
- 🏷️ **标签与收藏** —— AI 自动标签 + 用户自定义标签 + 批量维护 + 收藏夹 + 软删除回收站
- ⚙️ **模型配置中心** —— 文本/视觉/Embedding 三类 OpenAI 兼容配置独立维护,API Key 加密存储、脱敏显示、连接测试
- 🔐 **单管理员、内网友好** —— 全开源组件,可本地/内网部署,不绑定云厂商

## 🚀 快速开始

### 前置要求

- [Docker](https://docs.docker.com/get-docker/) 20+ 与 Docker Compose v2
- Linux / macOS(渲染依赖 LibreOffice Headless,容器内已内置)
- *(可选)* 本地 MinerU 服务(增强 OCR),或 OpenAI 兼容的视觉/Embedding 模型端点

### 一键启动

```bash
git clone https://github.com/zweien/ppt-management.git
cd ppt-management

# 配置环境(端口、管理员账号、密钥)
cp .env.example .env

# 启动全部服务
docker compose up -d
```

启动完成后访问:

| 服务 | 地址 | 说明 |
|---|---|---|
| **前端工作台** | http://localhost:13000 | 登录后使用(默认 `admin` / `changeme123`) |
| API 文档 | http://localhost:18000/docs | FastAPI Swagger |
| MinIO 控制台 | http://localhost:19001 | 对象存储(`minioadmin` / `minioadmin`) |

> 默认端口已偏移以避免与本机冲突,可在 `.env` 中通过 `*_HOST_PORT` 调整。

### 启用 AI 增强(可选)

在「模型配置」页填入 OpenAI 兼容端点,即可解锁:

- **Embedding**(如 bge-m3 / text-embedding-3-small)→ 语义检索
- **视觉模型**(如 gpt-4o)→ 页面摘要与 AI 标签

配置完成后对已上传文件点「重新解析」即可触发。MinerU 增强解析需单独启动 `mineru-api` 服务(见 [文档](#-文档))。

## 🧱 系统架构

```
                       ┌──────────────┐
                       │   浏览器      │
                       └──────┬───────┘
                              │
                       ┌──────▼───────┐
                       │  Next.js Web │
                       └──────┬───────┘
                              │
                       ┌──────▼───────┐
                       │  Nginx / API │   FastAPI(认证 / 业务 API)
                       └──┬───┬───┬───┘
            ┌─────────────┘   │   └─────────────┐
            │                 │                 │
   ┌────────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
   │ PostgreSQL    │  │   Redis      │  │   MinIO      │
   │ + pgvector    │  │  (队列/缓存) │  │  (对象存储)  │
   └───────────────┘  └──────────────┘  └──────────────┘
            │
   ┌────────┴─────────────────────────────┐
   │        Celery Workers(异步任务)      │
   ├──────────────┬──────────────┬────────┴────────┐
   │ worker-basic │ worker-render│ worker-mineru   │ worker-ai
   │ Open XML 解析│ LibreOffice  │ MinerU 增强     │ 视觉/embedding
   │ /索引/导出   │ 转 PDF/PNG   │ (宿主机 HTTP)   │ 模型调用
   └──────────────┴──────────────┴─────────────────┘
```

### 三路解析流水线

每份 PPT 上传后,系统按页建立索引,三路解析职责分离、真值性不同:

| 层 | 组件 | 产出 | 真值性 |
|---|---|---|---|
| **原生结构层** | Open XML(lxml 自研) | 页码、文本、表格、备注、依赖关系图 | ✅ 真值 |
| **视觉呈现层** | LibreOffice Headless | PDF、高清 PNG、缩略图 | 预览真值 |
| **增强理解层** | MinerU + 视觉模型 | OCR 文字、摘要、主题、风格、标签 | 可人工修订 |

基础数据就绪即进入 `BASIC_READY` 可检索状态;增强层(ENRICHED → READY)可选、失败不阻断。

## 🛠️ 技术栈

| 层 | 技术 |
|---|---|
| **前端** | Next.js 14 · TypeScript · Tailwind CSS · 清华紫主题 |
| **后端** | Python · FastAPI · SQLAlchemy 2 · Alembic · Pydantic |
| **任务** | Celery + Redis(四组 worker:basic / render / mineru / ai) |
| **数据库** | PostgreSQL 16 + pgvector(向量)+ pg_trgm(模糊)|
| **存储** | MinIO(对象存储,可挂 NAS) |
| **PPT 处理** | zipfile/lxml 自研 Open XML 解析 · LibreOffice Headless · MinerU |
| **中文检索** | 应用层 jieba 分词 + simple tsvector(可演进领域词典) |
| **检索融合** | RRF(Reciprocal Rank Fusion)+ 结构化加分 |
| **部署** | Docker Compose,Linux |

## 📑 文档

- **[PRD 与系统设计](PPT素材库_extracted/PPT素材库_方案包/PPT素材库_PRD与系统设计方案.md)** —— 完整需求规格与系统设计
- **[领域语言(CONTEXT.md)](CONTEXT.md)** —— Presentation / Version / Slide / 原生文字 等术语权威定义
- **架构决策记录(ADR)** —— `docs/adr/`
  - [0001 技术栈基线](docs/adr/0001-record-architecture-decisions.md)
  - [0002 单页 PPTX 导出:关系图遍历 + 复制或拒绝](docs/adr/0002-single-slide-pptx-export.md)
  - [0003 混合检索:RRF + 结构化加分](docs/adr/0003-hybrid-search-rrf-fusion.md)
  - [0004 中文分词:应用层 jieba](docs/adr/0004-chinese-tokenization-app-layer-jieba.md)
  - [0005 LibreOffice 渲染:多容器单并发](docs/adr/0005-libreoffice-rendering-concurrency.md)
  - [0006 模型配置中心:embedding 配置驱动 / Fernet / MinerU 时机](docs/adr/0006-model-config-and-secrets.md)
  - [0007 阶段二:模型配置 / MinerU / 视觉 / RRF 落地](docs/adr/0007-phase-2-models-mineru-hybrid-search.md)

## 🗺️ 路线图

- [x] **阶段一 · 基础素材库** —— 上传、Open XML 解析、渲染、关键词全文搜索、页级复用、任务中心、标签与回收站
- [x] **阶段二 · AI 理解与语义检索** —— 模型配置中心、MinerU 增强、视觉分析、pgvector、RRF 混合检索、命中解释
- [ ] **阶段三 · 版本与复用增强** —— 版本链与页面变化匹配、单页 PPTX 导出(关系图遍历 + 校验)、任务中心完善

后续演进:团队化多用户 / NAS 自动采集 / 以图搜图 / 元素级素材拆解 / 多页组装新 PPT。

## 📂 项目结构

```
├── backend/              FastAPI 后端
│   ├── app/
│   │   ├── api/routers/  REST 端点(auth/uploads/presentations/search/tags/jobs/model_configs)
│   │   ├── models/       SQLAlchemy ORM(Presentation/Version/Slide/Job/...)
│   │   ├── services/     ModelProvider / hybrid_search / openxml / mineru_client / vision_analyzer
│   │   └── tasks/        Celery 任务(basic/render/mineru/ai)
│   ├── alembic/          数据库迁移
│   └── dict/             领域分词词典(jieba)
├── frontend/             Next.js 前端(11 个页面 + 共享组件)
├── infra/docker/         Dockerfile(api/web/worker-basic/worker-render)
├── docs/adr/             架构决策记录
├── CONTEXT.md            领域语言
└── docker-compose.yml    全栈编排
```

## 🤝 贡献

欢迎 Issue 与 PR。本项目以 PRD 为需求基线,新增需求需明确标记为「MVP 内变更」或「后续路线」,避免范围无边界扩张(见 PRD 末「进入开发前的唯一门槛」)。

## 📄 许可证

本项目仅供学习与内部使用。依赖组件(LibreOffice、MinerU、MinIO、pgvector 等)各有自己的开源许可证。

<div align="center">

<sub>Built with FastAPI · Next.js · PostgreSQL+pgvector · Celery · LibreOffice · MinerU</sub>

</div>
