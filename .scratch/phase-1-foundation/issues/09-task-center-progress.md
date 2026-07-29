Status: done

# 09 — 任务中心:上传/解析/渲染阶段进度可见

## Parent

阶段一 MVP(`.scratch/phase-1-foundation/`)。

## What to build

一条可观测性 vertical slice:用户能在「任务中心」页看到每个 Presentation/Version 的上传、解析、渲染各阶段状态与进度,失败时能看到失败阶段与原因,并能对失败阶段单独重试。

这是 PRD §5.1「任务中心」、§15 状态机、§17.2 `jobs` 在阶段一的落地。把 #03/#04/#05 已经在写的 job 记录首次以统一界面呈现。

端到端穿过:schema(jobs 表 + Version 状态字段)、API(jobs 查询 + retry)、UI(任务中心列表)、test。

约束(遵守 PRD §15、CONTEXT.md):

- **状态机**:Version 走 `UPLOADING → VALIDATING → PARSING → RENDERING → BASIC_READY`,任一阶段可 `PARTIAL_FAILED`;基础数据可用时文件仍可搜索,失败阶段可单独重试(§15.2)。
- **幂等重试**:重试不重复创建 slides/对象/标签关联(§15.3、ADR-0006)。
- **任务记录**:每个 job 保存类型、目标、状态、进度、开始/结束时间、错误码、简化错误信息、详细日志引用(§15.3、§18.3)。
- **错误分类**:区分文件错误/渲染错误/模型错误等(§18.2),阶段一主要涉及文件错误与渲染错误。
- **结构化日志**包含 request_id/job_id/presentation_id/version_id/slide_id(§18.3)。

注意:阶段一任务类型只涉及 validate_pptx / parse_openxml / render_preview / build_search_index(建索引);MinerU/视觉/embedding 是阶段二。

## Acceptance criteria

- [ ] 任务中心页列出所有 job,按时间倒序,显示类型、目标、状态、进度、时间
- [ ] 每个 Version 的阶段进度可见(UPLOADING → ... → BASIC_READY)
- [ ] 失败 job 显示失败阶段、错误码、简化错误信息(§18.2 错误分类)
- [ ] 失败阶段可单独重试,重试不产生重复 slides/对象/标签(幂等,§15.3)
- [ ] job 记录含开始/结束时间、进度、详细日志引用
- [ ] 结构化日志含 request_id/job_id/presentation_id/version_id/slide_id(§18.3)
- [ ] 全部需登录态

## Blocked by

- 04 — Open XML 解析(parse_openxml 是可见任务之一)
- 05 — LibreOffice 渲染(render_preview 是可见任务之一)
