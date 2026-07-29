Status: done

# 04 — Open XML 解析:页面/文本/结构提取(基础可检索)

## Parent

阶段一 MVP(`.scratch/phase-1-foundation/`)。

## What to build

一条解析 vertical slice:上传的源 PPTX 触发 Open XML 原生解析,提取每一页的页码、标题占位符、原生文字、备注、表格文字、内容结构 JSON,并在 DB 为每页建立 `slides` 记录。解析完成后,这些原生文字已成为**真值**(CONTEXT.md「原生结构层」),即使渲染/MinerU 还没跑,文件也已进入基础可检索状态。

这是 worker-basic 的核心任务之一(`parse_openxml`,PRD §15.1)。

端到端穿过:任务队列(Celery)、解析模块(zipfile/lxml 自研,不用 python-pptx)、schema(slides 表)、test。

约束(遵守 PRD §9.2、§12.2、CONTEXT.md):

- **原生结构层是真值**:页码、文本框、表格、备注、媒体引用、布局/母版/关系全部从 Open XML 提取。
- **保留结构化 JSON**:`slides.content_json` 存形状/表格/关系结构,便于后续高亮与单页导出(ADR-0002 的关系图遍历会复用这些关系数据)。
- **记录依赖关系**:每页引用的 slideLayout/slideMaster/theme/media/chart/embeddings,写入结构 JSON(为阶段三单页导出的关系图遍历打基础)。
- **指纹**:`slides.fingerprint`(原生文字归一化哈希)在本 slice 生成,为版本差异(阶段三)预留。
- **幂等**:任务用 `target_id + job_type + input_hash` 幂等键,重试不重复创建 slides(ADR-0006、PRD §15.3)。
- **状态**:解析成功后,Version 状态推进到「基础解析完成」(为 #09 任务中心可见)。

注意:本 slice **不**做渲染(那是 #05)、**不**建全文索引(那是 #07,依赖 jieba)。本 slice 只产出 slides 原始数据。

## Acceptance criteria

- [ ] 上传完成后自动触发 `parse_openxml` 任务(由 #03 的 job 推进)
- [ ] 为每一页建立 `slides` 记录:page_no、title、native_text、notes_text、content_json、fingerprint
- [ ] `content_json` 包含形状、表格文字、备注,以及该页引用的 layout/master/theme/media/chart/embeddings 关系
- [ ] `UNIQUE(version_id, page_no)` 约束生效
- [ ] 幂等:重复触发同一任务不产生重复 slides
- [ ] 解析失败有明确错误码与日志,不污染已成功的页面(PRD §18.2)
- [ ] 解析成功后 Version 状态可查询(为 #09 可见)
- [ ] 典型 40 页 PPT 能稳定完成解析,不阻塞其他文件上传(PRD §19.2)

## Blocked by

- 03 — PPTX 上传 + 校验 + 去重(需要已落盘的源 PPTX 与 Version 记录)
