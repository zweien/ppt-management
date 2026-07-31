#!/usr/bin/env bash
# =============================================================================
# 制作内网离线部署包
# =============================================================================
# ⚠️ 架构警告:镜像与 CPU 架构强绑定。内网是 x86_64(amd64) 主机,
#    镜像必须在【同架构的 amd64 机器】上构建/拉取,否则内网无法运行。
#
# 本脚本提供两种模式,按你手头的资源选择:
#
#   模式 A(推荐):在【能联网的 x86 机器】上运行
#     bash make-offline-package.sh
#     → build 自建镜像(amd64 原生)+ pull base 镜像 + save 全部为 tar + 打包
#
#   模式 B:本地无 build,只打包配置(镜像由你另行在 x86 机器准备)
#     NO_BUILD=1 bash make-offline-package.sh
#     → 只打包代码 + compose + env 模板 + load 脚本(不含镜像 tar)
#
#   模式 C:镜像已就绪(任意途径准备好 amd64 镜像),只 save + 打包
#     IMAGES_READY=1 bash make-offline-package.sh
#     → 假设本机已有全部 amd64 镜像,直接 save + 打包(不 build)
#
# 关键:运行本脚本前,先确认本机架构与目标一致:
#   uname -m   → 必须是 x86_64(模式 A/C 才有意义)
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

TS="$(date +%Y%m%d-%H%M%S)"
PKG_DIR="$(mktemp -d)/ppt-offline"
IMG_DIR="$PKG_DIR/images"
mkdir -p "$IMG_DIR"

_log()  { printf '\033[36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
_ok()    { printf '  \033[32m✓\033[0m %s\n' "$*"; }
_fail()  { printf '  \033[31m✗\033[0m %s\n' "$*"; exit 1; }

NO_BUILD="${NO_BUILD:-0}"
IMAGES_READY="${IMAGES_READY:-0}"

# 自建镜像(base 镜像也一并 save,内网不联网也能 load)
# worker-mineru/ai 与 worker-basic 同一 Dockerfile,compose 里复用 basic 镜像,不需单独 save。
declare -a IMAGES=(
  "ppt-management-api:latest"
  "ppt-management-web:latest"
  "ppt-management-worker-basic:latest"
  "ppt-management-worker-render:latest"
  "pgvector/pgvector:pg16"
  "python:3.12-slim"
  "node:20-alpine"
)

# ---- 架构检查 ----
ARCH="$(uname -m)"
_log "本机架构:$ARCH"

if [ "$NO_BUILD" = "1" ]; then
  _log "模式 B:仅打包配置(NO_BUILD=1),不处理镜像"
  SKIP_IMAGES=1
elif [ "$IMAGES_READY" = "1" ]; then
  _log "模式 C:镜像已就绪,只 save + 打包(IMAGES_READY=1)"
  [ "$ARCH" = "x86_64" ] || _fail "本机是 $ARCH,但内网需 amd64。请在 x86 机器上准备镜像,或用 NO_BUILD=1"
  SKIP_IMAGES=0
else
  _log "模式 A:在 x86 联网机器上 build + save(默认)"
  [ "$ARCH" = "x86_64" ] || _fail "本机是 $ARCH,不能为内网 x86 构建。请:(1)换到 x86 联网机器跑此脚本;或(2)用 NO_BUILD=1 只打包配置"
  SKIP_IMAGES=0
fi

# ---- 1. build 自建镜像(仅模式 A)----
if [ "$SKIP_IMAGES" = "0" ] && [ "$IMAGES_READY" = "0" ]; then
  _log "== 1/4 build 自建镜像(amd64 原生) =="
  docker compose build api web worker-basic worker-render
  _ok "自建镜像 build 完成"
else
  _log "== 1/4 跳过 build =="
fi

# ---- 2. save 镜像为 tar(模式 A/C)----
if [ "$SKIP_IMAGES" = "0" ]; then
  _log "== 2/4 save 镜像为 tar =="
  for img in "${IMAGES[@]}"; do
    # 确认镜像存在 + 架构正确
    if ! docker image inspect "$img" >/dev/null 2>&1; then
      _fail "镜像 $img 不存在。模式 A 需先 build;模式 C 需确保镜像已 pull/build"
    fi
    IMG_ARCH="$(docker image inspect "$img" --format '{{.Architecture}}' 2>/dev/null || echo unknown)"
    [ "$IMG_ARCH" = "amd64" ] || _fail "镜像 $img 架构是 $IMG_ARCH,内网需 amd64。请在 x86 机器准备"
    fname="${img//\//-}"
    fname="${fname//:/-}.tar"
    _log "  saving $img ($IMG_ARCH) → $fname"
    docker save -o "$IMG_DIR/$fname" "$img"
    _ok "$fname ($(du -h "$IMG_DIR/$fname" | cut -f1))"
  done
else
  _log "== 2/4 跳过 save 镜像(模式 B 不含镜像) =="
fi

# ---- 3. 打包代码 + 配置 ----
_log "== 3/4 拷贝代码与配置 =="
mkdir -p "$PKG_DIR/backend"
cp -r backend/app backend/alembic backend/requirements.txt "$PKG_DIR/backend/"

cp deploy/offline/docker-compose.offline.yml "$PKG_DIR/"
cp deploy/offline/.env.offline "$PKG_DIR/"
cp deploy/offline/load-images.sh "$PKG_DIR/"
cp deploy/offline/DEPLOY.md "$PKG_DIR/"
chmod +x "$PKG_DIR/load-images.sh"

mkdir -p "$PKG_DIR/infra/authentik"
cp infra/authentik/setup-ppt-provider.py "$PKG_DIR/infra/authentik/"

_ok "代码与配置已拷贝"

# ---- 4. 压缩 ----
_log "== 4/4 压缩离线包 =="
OUT="$REPO_ROOT/ppt-offline-$TS.tar.gz"
tar -czf "$OUT" -C "$(dirname "$PKG_DIR")" ppt-offline
_ok "离线包已生成"
echo
_log "✅ 完成!产物:$OUT"
echo "    大小:$(du -h "$OUT" | cut -f1)"
echo
if [ "$SKIP_IMAGES" = "1" ]; then
  echo "注意:此包【不含镜像】。请在 x86 机器上另外准备 7 个 amd64 镜像"
  echo "     (见 DEPLOY.md「镜像准备」章节),拷到内网后 docker load。"
fi
echo "下一步:把 $OUT 拷到内网目标机器,解压后按 DEPLOY.md 部署。"
