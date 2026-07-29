Status: done

# 03 — PPTX 上传 + 校验 + 去重(文件落地,暂不解析)

## Parent

阶段一 MVP(`.scratch/phase-1-foundation/`)。

## What to build

一条上传 vertical slice:用户通过网页上传 PPTX,系统校验文件、计算指纹、判断重复、把源文件不可变地存入 MinIO,并在 DB 建立 Presentation / Version 记录。**本 slice 暂不触发任何解析或渲染**(那是 #04、#05)——上传成功即可验证「文件不可变存储 + SHA-256 去重」闭环。

端到端穿过 schema(Presentation/Version 模型)、API(上传端点)、UI(上传组件 + 进度)、对象存储(MinIO 落盘)、test。

覆盖 PRD 需求:UP-01~05、§6.1 前段、§13.2 不可变原则。注意范围裁剪:

- **仅 .pptx**(UP-01):不支持 .ppt、不支持加密文件,错误类型要可识别并明确提示。
- **去重只做完全相同文件**(UP-03):按 SHA-256,完全相同则提示已存在,**不**生成重复 version、**不**做版本关联(版本识别是阶段三,见 CONTEXT.md)。
- **新文件 vs 新版本**:第一版上传场景里只支持「作为新文件」;「作为某文件的新版本」(UP-04)依赖阶段三的版本管理,本 slice 暂不实现——但 UI 可保留该入口的占位(置灰 + 说明"阶段三支持")。
- **任务占位**:上传后创建一条 `jobs` 记录标记 UPLOADING(为 #09 任务中心预留),但本 slice 不实现后续解析阶段。

安全(遵守 PRD §18.1):限制扩展名、MIME、大小、ZIP 解压比,防压缩炸弹。

## Acceptance criteria

- [ ] 支持拖拽 + 文件选择上传,显示大小与上传进度,可取消(UP-02)
- [ ] 仅允许 .pptx;拒绝 .ppt / 加密文件,错误提示明确(UP-01)
- [ ] 计算 SHA-256;完全相同文件提示已存在,不生成重复 version 与重复对象(UP-03)
- [ ] 源 PPTX 不可变存入 MinIO,对象键遵循 PRD §13.1 布局(`presentations/{id}/versions/{vid}/source.pptx`)
- [ ] DB 建立 `presentations` 与 `presentation_versions` 记录,含 sha256、status
- [ ] 上传后立即创建 `jobs` 记录(UPLOADING 状态),可在 API 查到(为 #09 预留)
- [ ] 上传限流:扩展名/MIME/大小/解压比检查到位,防 ZIP 炸弹
- [ ] 上传需登录态(#02)

## Blocked by

- 02 — 单管理员认证(上传需鉴权)
