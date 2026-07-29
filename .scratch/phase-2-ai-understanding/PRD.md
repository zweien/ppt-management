# PRD — 阶段二:AI 理解与语义检索

> Parent for issues under `.scratch/phase-2-ai-understanding/issues/`.
> 需求源自 PRD V1.0 §21.2,落地决策见 ADR-0007。

## 阶段二目标

在阶段一基础素材库上,接入模型配置中心、MinerU 增强解析、视觉结构化分析与 pgvector 语义检索,实现 RRF 混合检索 + 命中解释 + 高级筛选。

## 已完成(P2-1 ~ P2-8)

| # | Issue | 状态 | 验证 |
|---|---|---|---|
| P2-1 | 模型配置中心(CRUD + Fernet 加密 + 连接测试 + 前端页) | done | API Key 密文存储、脱敏显示、测试端点 |
| P2-2 | ModelProvider 统一适配层(OpenAI 兼容 text/vision/embedding) | done | chat/embed/chat_with_image 三接口 |
| P2-3 | MinerU 接入(宿主机 mineru-api HTTP + worker-mineru) | done | 实测产出 Markdown(137 字符) |
| P2-4 | 视觉模型分析(整页 PNG→结构化 JSON + AI 标签) | done | JSON Schema 强约束 + 缩放 + 重试(需 default vision 配置触发) |
| P2-5 | pgvector 向量召回 + embedding 生成(配置驱动 default) | done | vector(1536) + ivfflat 索引 |
| P2-6 | RRF 混合检索融合 + 结构化加分 | done | 实测 score=3.5164 含标题/文件名匹配 |
| P2-7 | 搜索增强(标签筛选 + 文件聚合视图 + 命中原因 + 排序) | done | 聚合视图 2 组、命中原因徽标、排序下拉 |
| P2-8 | 详情页(AI 摘要/标签 tab + MinerU 文本 + AI 标签开关) | done | 5 tab + AI 标签显隐开关 |

## 关键设计决策(ADR-0007)

- MinerU:宿主机 mineru-api(pipeline 后端,GB10 hybrid-engine 有 device_map 问题),worker HTTP 调用,经 docker0 IP `172.17.0.1:8765` 访问
- 视觉:发送前缩放 ≤1568px,JSON Schema 强约束 + 重试 1 次
- 向量:vector(1536) 固定维度,ivfflat 索引,配置驱动 default
- 融合:RRF(k=60,每路 top-100)+ 加性 bonus(标题/文件名/人工标签/AI标签/收藏)
- AI 标签:origin=ai/is_confirmed=false,详情页「显示 AI 建议」开关

## 待办(需用户提供真实模型 API Key)

P2-4/P2-5 的视觉分析与 embedding 生成**需要配置 default vision/embedding 模型并填入真实 API Key**才能端到端跑通。当前代码逻辑已验证(配置缺失时优雅跳过),实测触发待用户提供可用模型端点。

## 完成定义

模型配置中心可配置并测试三类 OpenAI 兼容接口;MinerU 失败不阻断基础检索;视觉模型生成符合 Schema 的摘要与标签;pgvector 向量召回 + RRF 融合;命中可解释;标签可筛选。
