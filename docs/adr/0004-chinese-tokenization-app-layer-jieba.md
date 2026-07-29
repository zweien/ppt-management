# ADR-0004:中文分词 —— 应用层 jieba + simple 配置 TSVECTOR

- **状态**:已接受
- **日期**:2026-07-29
- **决策者**:工程讨论确认
- **取代**:无

## 背景

PostgreSQL 全文检索**没有原生中文分词器**。默认的 `simple` 配置把整段中文当一个 token,`'紫色科技风'` 这种查询匹配不到 `'紫色'`。需要选一个中文分词方案。

这个决策改起来代价很高:分词方案一旦定,`slides.text_search TSVECTOR` 的生成方式就钉死,**后期换方案要全量重建约 2 万页的全文索引**。且本项目有领域新词("智能体簇""无人系统"),对分词词典的可演进性有要求。

## 决策

### 分词在应用层:Python `jieba`,不用 PG 扩展

后端在写入 `slides` 时,用 Python 的 `jieba` 把 `native_text` / `ai_summary` / 标题等切好词,**用空格分隔后写入一个 `simple` 配置的 `tsvector`**:

```
text_search = to_tsvector('simple', ' '.join(jieba.cut(text)))
```

查询端对齐:

```
plainto_tsquery('simple', ' '.join(jieba.cut(query)))
```

两端共用同一份切词模块与词典,保证写入与查询的分词一致。

### 词典管理:领域词典从 CONTEXT.md glossary 派生

维护 `dict/domain_terms.txt`,从 `CONTEXT.md` 的 glossary 派生,`jieba.load_userdict()` 加载。新词进了 glossary → 同步进词典 → 重跑受影响页面。**不依赖 PG 扩展词典**,改词典不触发 PG 层重建。

### 不选的方案

- **`pg_jieba` 扩展**:部署/升级是 PG 扩展地狱(需编译、与 PG 主版本严格匹配、Docker 镜像要自打、改词典触发重建),与"Linux + Docker 单管理员"部署形态不匹配。
- **`simple` + `pg_trgm` 模糊匹配**:trigram 是子串匹配不是语义分词,召回质量差(搜"架构"会命中"重构架构师"噪音);中文 trigram 索引膨胀大;`ts_rank` 在 trigram 上语义弱。对一个"检索质量"是成功标准的产品是硬伤。

## 理由

- 分词是**业务逻辑**(领域有新词),业务逻辑放应用层比放 DB 扩展可控得多。
- 零 PG 扩展依赖,Docker 部署干净。
- jieba 是 Python 生态最成熟的中文分词,领域新词支持好,词典可热更新。
- 代价仅是多一点点应用层复杂度(维护分词模块),换来部署简单 + 词典可演进。

## 后果

- **正面**:部署无扩展依赖;领域词典可随 glossary 演进;写入/查询分词逻辑集中可控。
- **负面**:`text_search` 列**不能靠 PG 触发器用 `to_tsvector` 全自动维护**(PG 的 `to_tsvector` 不做中文分词),必须应用层切好词再写入;需保证写入端与查询端切词配置一致(同一份词典);改词典后需重跑受影响页面的 `text_search`。
- **实现约束**:切词模块作为共享依赖,被写入路径(Open XML 解析后)与查询路径(search API)共同引用。

## 关联

- 上游:ADR-0001(PostgreSQL)。
- 关联:ADR-0003(分词质量直接影响全文路召回,进而影响 RRF 融合)。
- 下游:`slides.text_search` 列由应用层填充;`dict/domain_terms.txt` 与 `CONTEXT.md` glossary 同步。
