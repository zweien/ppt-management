# 阶段一 E2E 测试报告(playwright-cli)

> 测试日期:2026-07-29
> 测试工具:`playwright-cli --browser=chromium`
> 测试地址:`http://localhost:13000`(web) / `http://localhost:18000`(api)

## 测试环境

- 全栈通过 `docker compose up` 启动,7 个容器全部 healthy
- 数据库:PostgreSQL 16 + pgvector + pg_trgm
- 对象存储:MinIO(bucket `ppt-library`)
- 渲染:LibreOffice Headless + poppler + imagemagick
- 队列:Celery + Redis(basic / render 两个 worker)

## 测试用例与结果

| # | 用例 | 验证方式 | 结果 |
|---|---|---|---|
| 1 | 首页落地页渲染 | goto `/` + snapshot + 视觉分析 | ✅ 标题"PPT 素材库"+清华紫配色 |
| 2 | 登录(正确密码) | 填表单 + 提交 | ✅ 跳转 `/files`,token 存 localStorage |
| 3 | 登录(无 token 访问受保护页) | 删 token 后访问 `/files` | ✅ 重定向 `/login`(401) |
| 4 | 修改密码 | API:PUT /api/auth/password | ✅ 旧密码校验 + 新密码生效 |
| 5 | 上传 PPTX(UI) | setInputFiles 触发 | ✅ `test_report` 入库 BASIC_READY |
| 6 | SHA-256 去重(UI) | 重复上传同文件 | ✅ "已存在(SHA-256 重复)",数量不增 |
| 7 | 错误扩展名拒绝 | 上传 .txt / 伪 .pptx | ✅ API 返回 400 "仅支持 .pptx" |
| 8 | Open XML 解析 | 上传后查 slides 表 | ✅ 3 页:title/native_text/notes/fingerprint |
| 9 | LibreOffice 渲染 | slides 有 preview/thumb | ✅ PNG(2000x1125)+ WebP 缩略图 |
| 10 | 文件列表 | snapshot 文件管理页 | ✅ 表格:文件名/页数/状态/大小/操作 |
| 11 | 页面卡片网格 | 进入文件详情 + snapshot | ✅ 3 张卡片,缩略图 naturalWidth=480 |
| 12 | 详情抽屉 | 点击卡片 | ✅ 高清预览(2000x1125)+ 3 个 tab + 复用按钮 |
| 13 | 导出单页占位 | 详情抽屉 | ✅ "导出单页 PPTX" 置灰 disabled |
| 14 | 下载源 PPTX | API + UI 按钮 | ✅ 返回整份源文件 |
| 15 | 关键词全文搜索(无人系统) | 搜索框输入 | ✅ 返回 P1 "无人系统总体架构" |
| 16 | 中文分词(智能体协同) | 搜索框输入 | ✅ 返回 P2 含"多智能体协同"(jieba 切词生效) |
| 17 | 标题匹配(项目研究目标) | 搜索框输入 | ✅ 返回 P3 |
| 18 | 页面浏览(全库瀑布流) | goto `/pages` | ✅ 渲染,显示 slides |
| 19 | 任务中心 | goto `/jobs` | ✅ 3 个任务 validate/parse/render 均 success |
| 20 | 标签创建(UI) | 标签管理页填表 | ✅ "紫智能体/主题"入库并显示 |
| 21 | 软删除(UI) | 文件列表点删除 | ✅ 移入回收站,active 数量-1 |
| 22 | 回收站恢复(UI) | 回收站点恢复 | ✅ active 数量+1 |
| 23 | 登出 | 点退出登录 | ✅ 清 token,跳转 `/login` |
| 24 | presigned URL(外部 host) | 浏览器加载图片 | ✅ localhost:19000,HTTP 200,签名有效 |
| 25 | 健康检查 | GET /health | ✅ postgres/redis/minio 全 ok |

## 已验证的关键设计决策(ADR 落地)

- **ADR-0004 应用层 jieba**:搜索"智能体协同"命中"多智能体协同",领域词典生效
- **ADR-0005 多容器单并发**:worker-render `--concurrency=1`,渲染稳定无锁冲突
- **ADR-0006 主密钥/MinerU 推迟**:Fernet 加密配置就绪,MinerU 阶段一跳过,文件停在 BASIC_READY 可检索
- **CONTEXT.md 数据优先级**:详情抽屉人工摘要 tab 显示"待填写",AI 摘要标"阶段二"
- **§13.1 对象键布局**:source.pptx / slides/0001.png / 0001-thumb.webp 全部遵循
- **§14.3 签名 URL**:presigned URL 走外部 host,不暴露 MinIO 内部地址

## 数据快照

- presentations: 2(test_无人系统, test_report)
- slides: 5(全部含 text/preview/thumb/index)
- jobs: 6(全部 success)
- tags: 1

## 结论

阶段一 MVP **全部 10 个 vertical slice 实现完成,25 个 E2E 用例全部通过**。系统可从零 `docker compose up` 启动,完整支持上传 → 解析 → 渲染 → 浏览 → 搜索 → 复用 → 任务追踪 → 标签/回收站的闭环。
