# ADR-0006:模型配置中心 —— embedding 选择、密钥管理、MinerU 接入时机

- **状态**:已接受
- **日期**:2026-07-29
- **决策者**:工程讨论确认
- **取代**:无

## 背景

PRD §16 定义了模型配置中心(文本/视觉/Embedding 三类 OpenAI 兼容配置),§12.1 的 `slide_embeddings(slide_id, model_config_id, embedding, source_hash)` 允许一个 slide 存多个模型配置的向量,§18.1 要求 API Key 用"应用主密钥"加密。但三个工程细节 PRD 没钉死,现在敲定以免阶段二返工。

## 决策

### 1. embedding 选择:配置驱动(方案 B)

在 `model_configs` 中设一个 **default embedding 配置**(capability=`embedding`,标记 `is_default`)。搜索时用 `WHERE model_config_id = :default_embedding_id`。

换 embedding 模型的工作流:

1. 新增一个 embedding model_config。
2. 后台异步重算受影响 slide 的向量(写入新 `slide_embeddings` 行,`source_hash` 标记来源文本)。
3. 重算完成且抽样校验通过后,把 `is_default` 切到新配置。
4. 老向量不立即删除(保留可回滚)。

**不做**多路向量融合召回(方案 C),那是演进项。

### 2. API Key 主密钥:环境变量 + Docker secret + Fernet(方案 A)

- 主密钥通过环境变量(或 Docker secret / `.env`)注入 `APP_ENCRYPTION_KEY`。
- 应用启动读取主密钥,在内存中用 `cryptography.fernet`(对称加密)对 `model_configs.api_key_ciphertext` 加解密。
- 界面/日志/接口响应中 API Key 脱敏(仅显示前后少量字符)。
- **主密钥与 DB 备份分开保管**(否则备份泄露 = 密钥泄露)。

**不引** Vault/KMS(方案 B),MVP 单管理员内网规模是杀鸡用牛刀,多一个需高可用的服务反而增加故障面。

### 3. MinerU:阶段一跳过,推阶段二(方案 A)

- 阶段一只有原生文字(Open XML 提取)+ 渲染预览,MinerU 与"模型配置中心"一起在阶段二接入。
- 阶段一所有文件解析状态停在 `BASIC_READY`(PRD §15.2 状态机已为此设计:`ENRICHING` 是可选阶段)。
- 阶段二启用 `ENRICHING`,接 MinerU + 视觉模型 + pgvector。

## 理由

**embedding 配置驱动而非"最新有效"**:和模型配置中心的设计一致(本就是配置驱动);换模型时老向量不丢、后台异步重算、重算完成才切 default,符合 PRD §16.3"确认有效后再切换为当前结果,避免批量重跑破坏已有索引"。

**密钥用 Fernet 而非 Vault**:匹配 MVP 部署形态(单管理员、内网);Vault/KMS 在团队化或合规审计需求出现时再升级。诚实边界:将来进团队化、多人访问,或合规要求审计密钥访问时,A 方案不够,届时上 Vault。

**MinerU 推阶段二**:

1. 阶段一无模型配置中心(PRD §21.2 把模型配置中心列在阶段二)。MinerU 产出的 Markdown 要进检索、要与模型层配合,强依赖未建好的模型层。
2. PRD §15.2 状态机已为"跳过"设计好(`BASIC_READY` 可检索,`ENRICHING` 可选)。
3. 减少阶段一部署复杂度(MinerU 服务可不进 docker-compose)。
4. 代价:阶段一某些"图片型 PPT 页"(整页是图片、原生文字几乎为空)检索会差——但这类页面要等视觉模型(阶段二)才能真正理解,MinerU 也只是补充,阶段一跳过不损失阶段一该有的能力。

## 后果

- **正面**:换 embedding 模型平滑可回滚;密钥管理轻量;阶段一聚焦核心闭环、部署简单。
- **负面**:阶段一无 MinerU 增强(图片型页检索弱,待阶段二补);Fernet 主密钥管理依赖运维规范(密钥与备份分离)。
- **数据模型影响**:`model_configs` 需 `is_default` 标记(或单独的 default 指针表);`slide_embeddings` 需 `source_hash` 区分文本来源版本。

## 关联

- 上游:ADR-0001(PostgreSQL + pgvector;OpenAI 兼容 API)。
- 关联:ADR-0003(向量路召回依赖 default embedding 配置)。
- 下游:阶段二工作项(模型配置中心、MinerU 接入、视觉分析、pgvector)。
