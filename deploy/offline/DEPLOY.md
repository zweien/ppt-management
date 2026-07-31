# 内网离线部署指南

把 PPT 素材库部署到**无互联网的内网 x86_64 主机**，复用内网已有的 Authentik / MinerU / Embedding / Redis / MinIO。

## 架构

```
内网目标机器 (x86_64, <DEPLOY_HOST>)
├─ Docker
│   └─ compose 栈(本方案):
│       ├─ api / web / worker-basic / mineru / ai / render
│       └─ postgres (pgvector,自带 —— 因 pgvector 是硬依赖)
│
└─ 复用内网现有服务:
    ├─ Authentik   :<AUTHENTIK>   SSO 登录
    ├─ MinerU      :<MINERU>      PPT/PDF 解析
    ├─ Embedding   :<EMBEDDING>   bge-m3 向量检索
    ├─ Redis       :<REDIS>       Celery broker
    └─ MinIO       :<MINIO>       对象存储
```

## ⚠️ 架构关键约束（必须先读）

**Docker 镜像与 CPU 架构强绑定。** 内网是 **x86_64 (amd64)** 主机，镜像必须是 amd64。在不同架构机器上构建/拉取的镜像（如 arm64）**无法在内网运行**。

因此镜像必须在 **amd64 机器**上准备。下面「阶段一」给出三条路径，按你手头资源选择。

> Postgres 为何不复用内网？本系统 migration 强制 `CREATE EXTENSION vector`(pgvector) + `pg_trgm`。内网原生 PG 若未装这两个扩展会迁移失败。自带 `pgvector/pgvector:pg16` 最稳妥。若内网 PG **已装 pgvector**，可复用：改 `POSTGRES_HOST` 指向内网 PG，并删 compose 里的 postgres 服务。

---

## 阶段一：准备镜像（在 amd64 机器上）

需要的镜像清单（全部 amd64）：

| 镜像 | 用途 | 来源 |
|---|---|---|
| `ppt-management-api:latest` | 后端 | 本仓库 build |
| `ppt-management-web:latest` | 前端 | 本仓库 build |
| `ppt-management-worker-basic:latest` | Celery(basic/mineru/ai 共用) | 本仓库 build |
| `ppt-management-worker-render:latest` | Celery(render,含 LibreOffice) | 本仓库 build |
| `pgvector/pgvector:pg16` | Postgres | docker hub pull |
| `python:3.12-slim` | base(可选,留作内网重 build) | docker hub pull |
| `node:20-alpine` | base(可选) | docker hub pull |

### 路径 A — 有一台能联网的 x86 机器（推荐）

在那台机器上克隆仓库并执行（原生 amd64 build，质量最高）：

```bash
# 确认是 x86
uname -m   # 应输出 x86_64

cd /path/to/ppt-management
bash deploy/offline/make-offline-package.sh
# → 自动 build 4 个自建镜像 + pull 3 个 base + save 全部为 tar + 打包配置
# → 产物:ppt-offline-<时间戳>.tar.gz(约 7-8 GB)
```

### 路径 B — 没有任何 x86 联网机器，先只拿配置包

在本仓库所在机器（任何架构）执行，只打包代码+配置（**不含镜像**）：

```bash
NO_BUILD=1 bash deploy/offline/make-offline-package.sh
# → 产物:ppt-offline-<时间戳>.tar.gz(很小,不含镜像)
```

然后镜像需另行解决（见路径 C 子选项）。推荐做法：找一台 x86 机器，把配置包里的 `backend/` + `deploy/offline/*.Dockerfile`（在仓库 `infra/docker/`）拿过去，按路径 A build。

### 路径 C — 镜像已通过其他途径准备好

若你已有全部 7 个 amd64 镜像（如内网有 x86 镜像源/registry，或别的 x86 机器 build 好）：

```bash
# 在已有这些镜像的 x86 机器上
IMAGES_READY=1 bash deploy/offline/make-offline-package.sh
# → 校验镜像架构为 amd64 后 save + 打包
```

### 验证镜像架构（任何时候都该做）

```bash
docker image inspect ppt-management-api:latest --format '{{.Architecture}}'
# 必须输出 amd64,否则内网无法运行
```

`load-images.sh` 在内网 load 后会自动做这个校验，架构不符会报错。

---

## 阶段二：传输到内网

把 `ppt-offline-<时间戳>.tar.gz` 拷到内网目标机器（U 盘 / 内网文件服务器 / scp 等）。

---

## 阶段三：内网部署

### 步骤 1 — 解压

```bash
tar xzf ppt-offline-<时间戳>.tar.gz
cd ppt-offline
```

### 步骤 2 — 加载镜像（含架构校验）

```bash
bash load-images.sh
# 自动 docker load 全部 tar,并校验架构 = amd64。不符会报错中止。
```

### 步骤 3 — 填写环境变量

```bash
cp .env.offline .env
vi .env       # 替换所有 〈...〉 占位符
```

**必填项**（详见 `.env.offline` 注释）：
- `REDIS_HOST/PORT` —— 内网 Redis
- `MINIO_ENDPOINT` —— 容器访问 MinIO 的地址
- `MINIO_EXTERNAL_ENDPOINT` —— **浏览器访问 MinIO 的地址**（取缩略图/预览，通常 `<DEPLOY_HOST>:<MinIO对外端口>`）
- `MINIO_ACCESS_KEY/SECRET_KEY`
- `OIDC_ISSUER/INTERNAL_ISSUER/CLIENT_SECRET/REDIRECT_URI` —— Authentik
- `MINERU_API_URL` —— 内网 MinerU
- `EMBEDDING_SERVICE_URL` —— 内网 Embedding
- `SECRET_KEY` / `APP_ENCRYPTION_KEY` / 各密码 —— **生产必改**

生成密钥：
```bash
openssl rand -hex 32                                                    # SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # APP_ENCRYPTION_KEY
```

> **`<DEPLOY_HOST>`** = 部署本系统的内网机器 IP（用户浏览器访问的地址），如 `10.0.0.10`。

### 步骤 4 — 内网 MinIO 预创建 bucket

在复用的内网 MinIO 上创建 bucket `ppt-library`（或让系统首次启动自动创建 —— 需 AK/SK 有 `create_bucket` 权限）。

### 步骤 5 — 配置 Authentik OIDC Provider

在内网 Authentik 创建 OIDC provider，把 `ppt-library` 系统接入 SSO。

```bash
export AUTHENTIK_URL=http://<AUTHENTIK_IP>:<AUTHENTIK_PORT>
export AUTHENTIK_TOKEN=<akadmin 的 API token>
export OIDC_REDIRECT_URI=http://<DEPLOY_HOST>:13000/api/auth/callback
python3 infra/authentik/setup-ppt-provider.py
```

脚本输出 `client_secret`，填入 `.env` 的 `OIDC_CLIENT_SECRET`。

> **关键：** provider 的 `redirect_uris` 必须含 `http://<DEPLOY_HOST>:13000/api/auth/callback`（脚本已按 `OIDC_REDIRECT_URI` 自动配置）。

获取 Authentik admin API token（在 Authentik server 容器内）：
```bash
docker exec authentik-server-1 ak shell -c "
from authentik.core.models import User, Token
u = User.objects.filter(username='akadmin').first()
t, _ = Token.objects.get_or_create(user=u, identifier='api-ppt',
                                   defaults={'expiring': False, 'intent': 'api'})
print(t.key)
"
```

### 步骤 6 — 启动

```bash
docker compose -f docker-compose.offline.yml --env-file .env up -d
```

`api` 启动时自动执行 `alembic upgrade head`（建表 + 扩展）。

### 步骤 7 — 验证

```bash
curl http://<DEPLOY_HOST>:18000/   # 应返回 {"version":"0.7.0",...}
docker compose -f docker-compose.offline.yml ps
docker compose -f docker-compose.offline.yml logs api
```

浏览器访问 `http://<DEPLOY_HOST>:13000` → 「使用 Authentik 登录」→ SSO → 进入系统。

---

## 阶段四（可选）：启用视觉 AI

> 给每页 PPT 生成 AI 摘要 + 标签。内网若无 OpenAI 兼容视觉模型，跳过（系统照常运行，仅缺 AI 摘要/标签）。

1. 登录系统 → 「设置 → 模型配置」
2. 新建：能力 `vision`、base_url = 内网视觉模型 OpenAI 兼容地址、model = 模型名（如 `qwen-vl-max`）、勾「允许发送原图」
3. 保存 → 测试连接 → 设为默认 vision

---

## 常见问题

### Q0 镜像架构不符 / exec format error？
镜像架构与内网 x86 不一致。必须在 **amd64 机器**上重新 build/pull 镜像。`load-images.sh` 会提前校验拦截。

### Q1 登录后跳转 localhost，别的主机登不上？
`.env` 里 `OIDC_ISSUER` / `OIDC_REDIRECT_URI` / `WEB_BASE_URL` 必须用 `<DEPLOY_HOST>`。Authentik provider 的 redirect_uris 也必须含该回调。改后重启 api/web。

### Q2 图片/缩略图显示不出来？
`MINIO_EXTERNAL_ENDPOINT` 必须是**浏览器能访问**的 MinIO 地址，不能用容器内地址或 localhost。

### Q3 上传文件失败（HTTP 局域网访问）？
纯 HTTP 局域网下浏览器 `crypto.subtle` 不可用，前端已自动降级（跳过客户端 SHA-256 预检直接上传，后端仍精确查重）。v0.7.0 内置。要恢复完整预检需配 HTTPS。

### Q4 migration 报错 `CREATE EXTENSION vector` 失败？
说明 Postgres 没有 pgvector。用 compose 自带 `pgvector/pgvector:pg16`（默认）。若复用内网 PG，需先以超管安装 pgvector + pg_trgm。

### Q5 想复用内网 Postgres？
前提：内网 PG 已装 pgvector + pg_trgm。满足后：`.env` 设 `POSTGRES_HOST=<内网PG_IP>`；compose 删 postgres 服务块 + 各服务 depends_on；`docker compose up -d`。

---

## 文件清单（离线包内）

```
ppt-offline/
├─ images/                           # 7 个 amd64 镜像 tar(模式 B 不含此目录)
│   ├─ ppt-management-api-latest.tar
│   ├─ ppt-management-web-latest.tar
│   ├─ ppt-management-worker-basic-latest.tar
│   ├─ ppt-management-worker-render-latest.tar
│   ├─ pgvector-pgvector-pg16.tar
│   ├─ python-3.12-slim.tar
│   └─ node-20-alpine.tar
├─ backend/                          # 后端代码(含 alembic migrations)
├─ infra/authentik/
│   └─ setup-ppt-provider.py
├─ docker-compose.offline.yml
├─ .env.offline
├─ load-images.sh
└─ DEPLOY.md                         # 本文档
```
