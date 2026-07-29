Status: done

# 07 — 关键词全文搜索(应用层 jieba)

## Parent

阶段一 MVP(`.scratch/phase-1-foundation/`)。

## What to build

一条检索 vertical slice:搜索首页支持关键词全文搜索,命中文件名、页面标题、原生文字、备注、表格文字;结果以页面卡片网格展示,命中文字高亮。这是阶段一唯一的检索能力(向量/语义检索是阶段二)。

端到端穿过:分词模块(jieba)、schema(slides.text_search TSVECTOR)、API(search 端点)、UI(搜索首页 + 结果卡片 + 高亮)、test。

**本 slice 引入 ADR-0004 的核心:应用层 jieba 分词。** 这是个有重量的独立闭环,因此单独成 slice。

约束(遵守 PRD §8.1/§8.4、ADR-0004、CONTEXT.md):

- **分词在应用层**:用 Python jieba 切词,空格拼接后写入 `slides.text_search`(simple 配置 TSVECTOR)。查询端 `jieba.cut(query)` 后用 `plainto_tsquery('simple', ...)` 对齐。
- **领域词典**:建立 `dict/domain_terms.txt`,从 CONTEXT.md glossary 派生,`jieba.load_userdict()` 加载。新词进 glossary 同步进词典(ADR-0004)。
- **写入/查询同模块**:切词逻辑作为共享依赖,被写入路径(解析后建索引)与查询路径(search API)共同引用,保证一致。
- **字段权重**:标题、正文、备注、表格、文件名可配置权重(PRD §8.4、SE-01)。
- **排序**:支持相关度、上传时间、文件名排序(SE-05),默认相关度。
- **默认仅当前版本**:搜索默认检索每个 Presentation 的当前 version(可后续开"包含历史版本",阶段一先不做)。

注意:本 slice **只有全文路**(text_score),**不**含向量召回、**不**含 RRF 融合(ADR-0003 的融合是阶段二向量路接进来后才启用)。本 slice 的排序就是全文相关度。

## Acceptance criteria

- [ ] 搜索首页有主搜索框,输入关键词返回匹配页面卡片网格
- [ ] 命中字段:文件名、页面标题、原生文字、备注、表格文字(SE-01)
- [ ] 命中文字在卡片摘要与详情中高亮(SE-06 的命中解释,本 slice 至少做到文字高亮)
- [ ] 分词符合 ADR-0004:应用层 jieba + simple TSVECTOR + 领域词典
- [ ] 写入与查询共用同一切词模块(领域词典一致)
- [ ] 支持相关度/上传时间/文件名排序,默认相关度(SE-05)
- [ ] 默认仅检索当前 version 的页面
- [ ] 解析完成(#04)后自动为 slides 建好 text_search 索引
- [ ] 全部需登录态;无结果时空状态合理

## Blocked by

- 06 — 页面卡片 + 文件/页面浏览 UI(搜索结果需复用页面卡片展示)
