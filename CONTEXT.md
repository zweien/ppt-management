# CONTEXT —— PPT 素材库领域语言

本文档是 PPT 素材库项目的领域语言权威。所有 issue title、代码命名、重构提案、hypothesis、test name 命名 domain concept 时,**必须使用本 glossary 定义的 term**,不要漂移到 synonyms。

> 本文件由 `setup-matt-pocock-skills` 初始化,内容源自 PRD V1.0(2026-07-29)及开发前设计讨论。新词在实际解决时由 `/grill-with-docs` 懒添加。

## 项目一句话定位

BS 架构平台,把 PPT **页面**作为核心素材实体,实现页级检索、理解、管理与复用。

> **核心产品定义**:PPT 是文件实体,页面是素材实体;搜索结果应直接返回具体页面,并始终保留与源文件、版本和原始页码之间的可追溯关系。

## 核心实体(数据模型层)

| Term | 定义 | 注意(避免漂移到的 synonym) |
|---|---|---|
| **Presentation** | 逻辑上的同一份 PPT,可包含多个 Version。一个 `presentations` 行。 | 不要叫"文件/File"(File 含义模糊);不要和 Version 混淆 |
| **Version** | 一次上传形成的**不可变** PPTX 版本(`presentation_versions`)。源 PPTX 上传后不被覆盖,新版本生成新 `version_id`。 | 不要叫"快照/Snapshot";强调不可变 |
| **Slide** | 某个 Version 中的具体页面,是系统**核心素材实体**(`slides`)。搜索的最小单元。 | 不要叫"页/Page"(Page 多义);代码里统一用 Slide |
| **原生文字** (native_text) | 直接从 PPTX Open XML 中提取的文字。**真值**,MinerU/OCR 不覆盖。 | 不要叫"原文/Original text"(歧义);强调来源是 Open XML |
| **增强文字** | MinerU/OCR 从页面视觉中补充识别的文字。补充而非替代,与原生文字重复时索引需去重。 | 不要和原生文字混为一谈 |

## 解析架构(三路)

系统对每份 PPT 做三路解析,职责与真值性不同:

| Term | 组件 | 职责 | 是否为真值 |
|---|---|---|---|
| **原生结构层** | Open XML | 页面、文本框、表格、备注、媒体、布局、母版、关系、页码 | **是** |
| **视觉呈现层** | LibreOffice Headless | 转 PDF、生成页面 PNG 和缩略图 | 预览真值(仅用于浏览与 AI 识别,不参与源 PPTX 保存或单页导出) |
| **增强理解层** | MinerU + 视觉模型 | 阅读顺序、OCR 补充、摘要、主题、用途、形态、风格、场景 | 否,可人工修正 |

## 标签与内容优先级

| Term | 定义 | 优先级规则 |
|---|---|---|
| **AI 标签** | 模型自动生成、可被用户修改或删除的标签(`slide_tags.origin = 'ai'`) | 低于人工标签 |
| **人工标签** | 用户创建或确认的标签(`slide_tags.origin = 'manual'`,`is_confirmed = true`) | **高于 AI 标签** |
| **人工摘要** (manual_summary) | 用户编辑的页面摘要 | 优先于 AI 摘要展示 |
| **AI 摘要** (ai_summary) | 视觉模型生成的页面摘要 | AI 重跑**不得覆盖**人工内容 |

**数据优先级总则**:人工内容 > AI 内容。人工摘要/标签优先展示;AI 重跑生成新的 `slide_ai_analyses` 记录,确认有效后才切换为当前结果。

## 检索

| Term | 定义 |
|---|---|
| **混合检索** | 全文召回、向量召回、标签过滤融合后的检索方式。融合方法见 ADR-0003(RRF + 结构化加分) |
| **页面综合语义文本** | 用于 Embedding 的文本,**不只**用 OCR 结果,而按稳定模板组合(标题 + 原生文字 + 备注 + AI 摘要 + 主题 + 用途 + 形态 + 风格 + 场景 + 人工标签) |

## 复用

| Term | 定义 |
|---|---|
| **单页 PPTX** | 直接**复制源文件目标页及依赖**后生成的单页演示文稿。**禁止重建页面**(不转图、不用 python-pptx 重绘、不经过 LibreOffice 保存)。详见 ADR-0002 |

## 状态与任务

| Term | 定义 |
|---|---|
| **BASIC_READY** | 文件解析状态:基础数据(Open XML + 渲染)就绪,已可检索。阶段一所有文件停在此状态 |
| **ENRICHING → READY** | 增强阶段(MinerU + 视觉 + 向量),阶段二启用。`ENRICHING` 可选,失败不阻断 `BASIC_READY` 的可检索性 |
| **幂等键** | 任务用 `target_id + job_type + input_hash` 作为幂等键。重试不得重复创建页面、标签关联或对象文件 |

## 部署形态约束

- **单管理员**:第一版仅一个管理员账号(同时是上传者、使用者、维护者)。DB 保留 `owner_id`/`created_by`/`updated_by` 为后续多人预留。
- **不可变源文件**:上传后的源 PPTX 不被覆盖,新版本生成新 `version_id`。派生文件对象键由源哈希 + 解析器版本 + 参数决定。
- **对象存储抽象**:应用只通过对象键访问文件,不在 DB 存大二进制。对象键布局见 PRD §13.1。

## 相关文档

- 架构基线与各详细决策 → `docs/adr/0001` ~ `docs/adr/0006`
- 完整需求规格 → `PPT素材库_extracted/PPT素材库_方案包/PPT素材库_PRD与系统设计方案.md`
- 消费规则(探索 codebase 前如何读这些文件) → `docs/agents/domain.md`
