Status: done

# 05 — LibreOffice 渲染:PDF / PNG / 缩略图

## Parent

阶段一 MVP(`.scratch/phase-1-foundation/`)。

## What to build

一条渲染 vertical slice:源 PPTX 触发 LibreOffice Headless 渲染,先转 PDF,再按页生成高清 PNG(1920 像素宽)与 WebP 缩略图(480 像素宽),存入 MinIO,并在 slides 记录上回填 preview/thumbnail 对象键。渲染完成后页面有了视觉预览。

这是 worker-render 的任务(`render_preview`,PRD §15.1)。**与 #04 并行**:二者都只依赖 #03(源文件已落盘),互不阻塞。

端到端穿过:任务队列、渲染容器、对象存储、schema(slides 预览字段)、test。

约束(遵守 PRD §9.3、ADR-0005、CONTEXT.md「视觉呈现层」):

- **并发模型**:每 `worker-render` 容器单 profile 单并发,靠 `replicas` 扩并发(起步 2 副本);常驻保活 `soffice` 进程复用;容器 `restart: unless-stopped` 自愈,崩溃后任务靠幂等键回队列重试(ADR-0005)。
- **预览仅用于浏览与 AI 识别**:**不**参与源 PPTX 保存、也**不**用于单页导出(CONTEXT.md「视觉呈现层」)。
- **隔离**:渲染在非特权容器中运行,限制 CPU/内存/文件系统/网络(PRD §18.1)。
- **只读挂载**:源 PPTX 以只读方式挂载到渲染容器。
- **对象键**:遵循 PRD §13.1(`.../preview.pdf`、`.../slides/0001.png`、`.../slides/0001-thumb.webp`)。
- **幂等**:幂等键防重复生成。

注意:本 slice **不**做 Open XML 解析(那是 #04)。本 slice 的输入是源 PPTX,输出是预览图,与文本解析完全解耦。

## Acceptance criteria

- [ ] 上传完成后自动触发 `render_preview` 任务(与 #04 解析并行)
- [ ] LibreOffice 转 PDF 成功,按页生成 1920 宽 PNG 与 480 宽 WebP 缩略图
- [ ] 预览图与缩略图存入 MinIO,对象键遵循 §13.1
- [ ] slides 记录回填 `preview_object_key`、`thumbnail_object_key`
- [ ] 并发模型符合 ADR-0005:单容器单并发 + replicas 扩容 + 常驻保活 + 容器自愈
- [ ] 渲染失败记录 stderr、退出码、LibreOffice 版本,允许单独重试(PRD §9.3)
- [ ] 渲染失败不影响已成功页面与其他文件(PRD §18.2)
- [ ] 幂等:重复触发不重复生成对象

## Blocked by

- 03 — PPTX 上传 + 校验 + 去重(需要已落盘的源 PPTX 与 Version 记录)
