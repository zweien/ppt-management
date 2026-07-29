Status: done

# 10 — 基础标签 + 软删除回收站

## Parent

阶段一 MVP(`.scratch/phase-1-foundation/`)。

## What to build

一条维护性 vertical slice:用户能给页面加自定义标签(人工标签)、在标签管理页维护标签、删除文件走软删除(回收站),索引立即不可见、对象延迟清理。

覆盖 PRD:SL-02(收藏/备注/人工标签)、SL-03(批量)、SL-04(AI 标签分组——阶段一无 AI,本 slice 只做人工标签 + 系统标签的框架)、SL-05(软删除回收站)、§5.1 标签管理。

注意范围裁剪:

- **人工标签为主**:阶段一无 AI 标签(MinerU/视觉是阶段二)。本 slice 实现 `tags` + `slide_tags` 表结构与人工标签 CRUD,`origin` 字段预留(`manual`/`ai`),为阶段二 AI 标签接入留接口(CONTEXT.md「AI 标签/人工标签」)。
- **数据优先级**:本 slice 落实「人工标签优先于 AI 标签」的数据模型约束——虽然阶段一还没 AI 标签,但 `slide_tags.origin`/`is_confirmed` 字段现在就建对,避免阶段二改表。
- **批量操作**:支持批量加/移除标签、批量收藏(SL-03)。
- **收藏**:实现 `favorites` 表与收藏功能(SL-02)。
- **软删除**:`presentations.deleted_at` 软删除,索引立即不可见,对象延迟清理;提供回收站查看与恢复(SL-05,§13.2 不可变原则的删除分支)。
- **备注/人工摘要**:`slides.notes_text`(已有,用户备注)与 `manual_summary` 字段建好,可在详情编辑(SL-02)。

## Acceptance criteria

- [ ] `tags` 表建立,含 category/source/status 字段;`slide_tags` 含 origin/is_confirmed(为阶段二 AI 标签预留)
- [ ] 用户可在页面详情加/改/删人工标签(SL-02)
- [ ] 支持批量加/移除标签、批量收藏(SL-03)
- [ ] 收藏功能可用,favorites 表记录用户-页面关系
- [ ] 页面详情可编辑人工摘要、备注(SL-02),人工内容优先于(未来)AI 内容展示
- [ ] 标签管理页可维护标签(列表、新建、停用)
- [ ] 删除文件走软删除:索引立即不可见,回收站可查看与恢复(SL-05)
- [ ] 软删除的对象延迟清理,不立即物理删除(§13.2)
- [ ] 全部需登录态

## Blocked by

- 06 — 页面卡片 + 文件/页面浏览 UI(标签编辑挂在详情上,批量操作挂在页面浏览器上)
