# ADR-0008:本地 Embedding 服务 —— bge-m3 + 自建 OpenAI 兼容服务(原计划 Xinference)

- **状态**:已接受
- **日期**:2026-07-29
- **决策者**:工程讨论确认
- **取代**:无(补充 ADR-0006 / ADR-0007 的 embedding 部署落地细节)

## 背景

ADR-0006 定 embedding 配置驱动,ADR-0007 §6 定"重模型宿主机常驻 HTTP 服务、容器经 docker0 访问"的部署模式。本 ADR 记录本地 embedding 服务的具体落地决策,以及一个重要的方案变更:**放弃 Xinference,改用自建轻量服务**。

## 决策

### 1. 模型:bge-m3(1024 维)

BAAI/bge-m3,多语言 dense embedding,1024 维,~2.3GB。中英 RAG 事实标准,覆盖 PPT 素材库的中文检索需求。本次仅用 dense 路径(不启用 sparse/colbert)。

### 2. 服务实现:自建 FastAPI 包装 sentence-transformers(**放弃 Xinference**)

**原计划**:用 Xinference 宿主机 venv 部署 + `xinference launch --model-name bge-m3`(ADR-0007 §6 模式)。

**实际遇到的问题**:Xinference 3.0 在本机(arm64 / NVIDIA GB10 / CUDA 13.0)上无法启动 bge-m3。`xinference launch` 报告成功,但模型实际未注册到运行列表。根因:xoscar 创建 model actor 时走 fork,与 torch 多线程库冲突,worker 子进程在握手阶段(`ServerClosed: 0 bytes read on a total of 11 expected`)原生层崩溃(2 秒内死亡,无 Python traceback)。已排查并排除的因素:

- GPU:GB10 的 NVML 显存查询返回 "Not Supported"(仅日志噪音);设 `CUDA_VISIBLE_DEVICES=` 走纯 CPU 仍崩溃 → 非 GPU 问题。
- 模型文件:bge-m3 已完整下载到本地 modelscope 缓存(2.27GB + tokenizer 全套) → 非下载/损坏问题。
- 依赖版本:解决了 transformers 5.x 删除 `HybridCache`、4.57 缺 `PeftAdapterMixin`、accelerate 1.14 循环导入、安装损坏等一连串版本冲突,最终对齐到 `torch==2.13.0+cu130` + `transformers==4.46.3` + `sentence-transformers==3.4.1` + `accelerate==1.0.1`(主进程导入链全通),但 actor fork 崩溃依旧。
- 离线模式:设 `HF_HUB_OFFLINE=1` 排除了联网 etag 校验的 SSL 失败干扰。

**结论**:xoscar fork + torch 在 arm64 的原生崩溃是深层平台问题,继续投入回报不确定。

**最终方案**:用 sentence-transformers 单进程直跑 bge-m3,包一层 ~80 行 FastAPI,暴露 OpenAI 兼容 `POST /v1/embeddings`(见 `~/codebase/xinference/embedding_server.py`)。单进程无 fork 问题,GPU 直跑安全。与 `ModelProvider.embed()` 协议 100% 兼容,**应用层零改动**。

### 3. 部署形态:宿主机常驻 HTTP 服务(照搬 ADR-0007 §6)

- 服务进程:`~/codebase/xinference/embedding_server.py`(`run.sh` 启动),绑定 `0.0.0.0:9997`。
- 模型源:`XINFERENCE_MODEL_SRC=modelscope` 已下载完整;服务直接从本地路径 `~/.xinference/modelscope/models/Xorbits--bge-m3/snapshots/master` 离线加载(设 `HF_HUB_OFFLINE=1` 避免联网 etag 校验 SSL 失败)。
- 设备:单进程直跑 **cuda**(GB10 GPU 可用);如需 CPU 改 `EMBEDDING_DEVICE=cpu`。
- 进程管理:systemd unit `infra/systemd/embedding.service`(`Restart=always`,与 MinerU 同为宿主机常驻服务,不在 compose 内)。
- 容器访问:api/worker 经 docker0 网桥 `172.17.0.1:9997` 访问(已验证容器内可达)。

### 4. 应用接入(配置驱动,业务代码零改动)

- **config**:新增 `EMBEDDING_SERVICE_URL`(默认 `http://172.17.0.1:9997`)、`DEFAULT_EMBEDDING_MODEL`(默认 `bge-m3`),注入 `.env` / `.env.example` / `docker-compose.yml` 的 `&app_env` 锚点。
- **bootstrap**:新增 `bootstrap_default_embedding()`(`backend/app/api/bootstrap.py`),首次启动若无 `is_default` 的 embedding config 则种一条(幂等,不覆盖用户后续手动改动)。在 `main.py` startup 与 `bootstrap_admin()` 同 try/except 调用。
- **迁移** `0003_emb_dim_1024`:`slide_embeddings.embedding` 列从 `vector(1536)` 改为 `vector(1024)` + 重建 ivfflat 索引(`vector_cosine_ops`, `lists=100`)。迁移时表为空(0 行),安全。
- **接入层**:`ModelProvider.embed()` / `hybrid_search._vector_recall()` / `tasks/ai.build_embedding_task()` **均不改动** —— 已 dimension-agnostic 且自动 pick default config。

## 理由

- **放弃 Xinference 而非死磕**:核心需求是"本地 embedding + 接入应用",Xinference 只是手段。~80 行 FastAPI 完全达成目标,且与现有 OpenAI 兼容协议无缝衔接。
- **单进程直跑**:绕开 xoscar actor fork 的原生崩溃;GPU 单进程安全;bge-m3 推理延迟 ~45ms/请求(测试值),满足内网单管理员场景。
- **保留可替换性**:服务暴露标准 `/v1/embeddings`,将来若 Xinference 在 arm64 的 fork 问题解决,只需改 `model_config.base_url` 即可切换,应用层零改动(ADR-0006 配置驱动的价值)。

## 后果

- **正面**:本地 embedding 闭环跑通 —— 25 个 slide 已 re-embed 成 1024 维,混合检索向量路(`hit_reasons=['语义相似']`)端到端验证通过;部署简单(单进程 + systemd);换模型只需改配置 + 新迁移 + re-embed。
- **负面 / 诚实边界**:
  - 与 Xinference 相比,自建服务**只支持 `/v1/embeddings`**,不支持 Xinference 的 LLM/rerank/vision 等能力。当前项目 embedding 是唯一刚需,无影响;若将来需要本地 LLM 推理,需另选方案(可能仍需直面 Xinference 的 fork 问题,或换 vLLM/Ollama)。
  - `embedding_server.py` 留在 `~/codebase/xinference/` 目录(目录名沿用历史,实际已是自建服务);venv 里残留 xinference 包(未卸载,无害)。
  - 自建服务无内置多副本/负载均衡,单进程;内网单管理员规模够用,高并发场景需另行扩展。
- **运维**:`embedding.service` 需作为宿主机常驻服务管理(systemd),不在 compose 内,与 MinerU 同。

## 关联

- 上游:ADR-0001(OpenAI 兼容 API)、ADR-0006(embedding 配置驱动 / 换模型工作流)、ADR-0007 §6(宿主机常驻 HTTP 服务模式)。
- 下游:向量召回已接入 RRF 混合检索(ADR-0003);将来换 embedding 模型若维度不同,需新迁移重建 `embedding` 列 + 后台 re-embed。
