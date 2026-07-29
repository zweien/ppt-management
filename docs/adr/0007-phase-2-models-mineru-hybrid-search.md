# ADR-0007:阶段二 —— 模型配置中心、MinerU 接入、视觉分析与 RRF 混合检索

- **状态**:已接受
- **日期**:2026-07-29
- **决策者**:工程讨论确认
- **取代**:无(补充 ADR-0003 / ADR-0006 的阶段二落地细节)

## 背景

阶段一已交付基础素材库闭环(上传→Open XML 解析→渲染→全文搜索→复用),并在 ADR-0006 中主动推迟了模型配置中心、MinerU、视觉模型、pgvector 到阶段二。本 ADR 记录阶段二这些模块的工程决策。

阶段二范围(PRD §21.2):

1. 模型配置中心(OpenAI 兼容,文本/视觉/Embedding 三类)
2. MinerU 增强解析
3. 视觉模型结构化分析(摘要/主题/用途/形态/风格/场景)+ AI 标签
4. pgvector 向量召回
5. RRF 混合检索(ADR-0003 的落地)
6. 命中解释 + 高级筛选

## 决策

### 1. ModelProvider 统一适配层(ADR-0001 §16.2 落地)

后端封装统一 `ModelProvider` 接口,业务代码不直接依赖厂商 SDK:

- **文本/视觉**:Chat Completions(`POST /v1/chat/completions`),视觉任务把页面 PNG 作为 `image_url`(base64 data URL)随消息发送。
- **Embedding**:`POST /v1/embeddings`。
- 兼容性差异(字段名、返回结构)通过 provider adapter 解决;MVP 阶段二仅实现 OpenAI 兼容协议一家。

### 2. 视觉模型输入:发送前缩放

整页 PNG 渲染产物为 1920px 宽(几百 KB)。多数视觉模型对图片尺寸/Token 有限制。

- **决策**:视觉任务发送前,把 PNG 等比缩放到 **长边 ≤ 1568px**(OpenAI Vision 常见上限),编码为 base64 data URL。**原图不动**,仅用于本次调用。
- 超过模型限制的图片在调用层降级,不污染对象存储。

### 3. 视觉模型 JSON 输出:强约束 + 重试

PRD §9.5 要求受约束 JSON。决策:

- 调用时设 `response_format: {type: "json_object"}`,并在 system prompt 内嵌完整 JSON Schema(字段:summary/topics/page_purpose/content_types/visual_styles/use_cases/key_entities/confidence)。
- **失败重试 1 次**(JSON 解析失败或 Schema 校验失败);仍失败则标记 `ai_status=failed`,不阻断基础检索(与 ADR-0006 的容错哲学一致)。
- AI 输出保留 `model_config_id`、模型名、`prompt_version`、调用时间、原始响应,供审计与重跑(PRD §9.5)。

### 4. AI 标签 vs 人工标签的存储与展示

- **存储**:`slide_tags.origin ∈ {manual, ai}`、`is_confirmed` 标记。AI 生成的标签默认 `origin=ai, is_confirmed=false`。
- **数据优先级**:人工标签(origin=manual)优先于 AI 标签;CONTEXT.md「AI 重跑不得覆盖人工内容」——AI 重跑生成新的 `slide_ai_analyses` 记录,确认有效后才切换。
- **展示**:详情页标签区默认显示人工标签 + 已确认 AI 标签;提供「显示 AI 建议」开关查看未确认的 AI 标签。

### 5. 向量维度:按 default 配置迁移

pgvector 的 `embedding` 列当前是无维度 `vector`(阶段一迁移创建)。不同 embedding 模型维度不同(OpenAI text-embedding-3-small=1536,有的 768)。

- **决策**:阶段二迁移时,把 `embedding` 列改为 default embedding 配置对应的固定维度(如 1536)。切换 default embedding 配置时(ADR-0006),维度若不同需重建该列——这是 ADR-0006「换模型后台重算」工作流的一部分。

### 6. MinerU 接入:宿主机 HTTP 服务 + worker HTTP 调用

MinerU 已在宿主机部署为本地 CLI(`~/codebase/MinerU/.venv/bin/mineru`,支持 pptx/pdf/docx/xlsx/image),并自带 FastAPI 入口 `mineru-api`。模型庞大(~2.5GB + GPU),不适合打进 Docker 容器。

- **决策**:
  - **部署形态**:宿主机启动 `mineru-api` 作为独立 HTTP 服务(绑定 `0.0.0.0:8765`,符合 PRD §17.2「MinerU 独立服务」)。
  - **接入方式**:新增 `worker-mineru` Celery worker,通过 HTTP 调用 `POST /file_parse`(同步端点),上传页面 PDF/PPTX,获取 Markdown + 结构化 JSON。
  - **不把 MinerU 打进容器**:容器 worker 仅负责 HTTP 编排;MinerU 本体留在宿主机 venv,避免镜像膨胀与 GPU 透传复杂性。
  - **MinerU 端点 URL** 通过环境变量 `MINERU_API_URL` 注入(默认 `http://host.docker.internal:8765`,容器经宿主机访问)。
  - **容错**:MinerU 失败不阻断基础检索(ADR-0006);版本状态保留为 `BASIC_READY`,job 标 `failed` 可重试。
  - **输入**:用阶段一已生成的 `preview.pdf`(整份 PPTX 的 PDF)作为 MinerU 输入,产出整份 Markdown;按页拆分后回填各 slide 的 `mineru_markdown`。

### 7. RRF 混合检索落地(ADR-0003 执行)

- **全文路**:`ts_rank_cd` over simple tsvector(已有),取 top-100。
- **向量路**:pgvector `<=>` cosine 距离,取 top-100。
- **融合**:RRF `k=60`,融合后取前 N(默认 24)。
- **结构化加分**(叠加在 RRF 分数上):标题/文件名精确匹配、人工标签匹配(权重高于 AI)、收藏页加权。
- **仅当前版本**:默认检索每个 presentation 的当前 version。

### 8. 命中解释

搜索结果每条返回 `hit_reasons: {text, vector, tag, title_exact, favorite}`,前端在卡片上以小标签展示命中类型(如「正文命中」「语义相似」「标签匹配」)。

## 理由

- **Provider 适配层**:ADR-0001 已定,阶段二落地,避免业务代码绑死厂商。
- **视觉输入缩放**:避免超大图片触发模型 token 限制或费用暴增;原图不动保证导出/预览质量。
- **JSON 强约束 + 重试 1 次**:平衡可靠性与成本;彻底失败则降级不阻断。
- **MinerU HTTP 模式**:宿主机已有 CLI + FastAPI 入口,HTTP 调用是最低侵入接入;容器只做编排,避免 2.5GB 模型镜像化与 GPU 透传。
- **向量维度迁移**:pgvector 列需固定维度才能建 ivfflat/hnsw 索引;default 配置驱动避免多维度并存。

## 后果

- **正面**:模型可配置可替换(ADR-0006);MinerU 增强解析接入;视觉结构化分析 + AI 标签;向量召回 + RRF 融合;命中可解释。
- **负面**:MinerU HTTP 服务依赖宿主机进程(非 docker compose 编排),部署文档需说明;视觉/embedding 调用引入网络延迟与外部依赖;向量列迁移需停机或在线重建。
- **运维**:`mineru-api` 需作为宿主机常驻服务管理(systemd / 手动 nohup),不在 compose 内。

## 关联

- 上游:ADR-0001(技术栈)、ADR-0003(RRF 融合)、ADR-0006(模型配置/embedding/MinerU 时机)。
- 下游:阶段二实施(P2-1 ~ P2-8)。
