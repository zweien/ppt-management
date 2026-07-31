#!/usr/bin/env bash
# =============================================================================
# 内网目标机器:一键 load 全部离线镜像
# =============================================================================
# 在离线包解压后的 ppt-offline/ 目录内运行:
#   bash load-images.sh
#
# 作用:load images/*.tar,并把 worker-basic 镜像 tag 成 worker-mineru/ai
#       (三者共用同一 Dockerfile,compose 用服务名 + 命令覆盖区分队列)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMG_DIR="$SCRIPT_DIR/images"

_log() { printf '\033[36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
_ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
_fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; exit 1; }

[ -d "$IMG_DIR" ] || _fail "找不到 images/ 目录($IMG_DIR),请在 ppt-offline/ 根目录运行"

_log "== load 离线镜像 =="
for tar in "$IMG_DIR"/*.tar; do
  [ -f "$tar" ] || continue
  _log "  loading $(basename "$tar") ..."
  docker load -i "$tar" >/dev/null && _ok "$(basename "$tar")" || _fail "load 失败:$tar"
done

# ---- 架构校验:确认加载的镜像与本机架构匹配 ----
_log "== 校验镜像架构 =="
HOST_ARCH="$(uname -m)"   # x86_64 / aarch64
BAD=0
for img in ppt-management-api:latest ppt-management-web:latest \
           ppt-management-worker-basic:latest ppt-management-worker-render:latest \
           pgvector/pgvector:pg16; do
  IA="$(docker image inspect "$img" --format '{{.Architecture}}' 2>/dev/null || echo missing)"
  if [ "$IA" = "missing" ]; then _fail "镜像缺失:$img"; fi
  # x86_64 主机应配 amd64 镜像;aarch64 应配 arm64
  case "$HOST_ARCH" in
    x86_64)  want="amd64" ;;
    aarch64) want="arm64" ;;
    *)       want="$IA"   ;;
  esac
  if [ "$IA" != "$want" ]; then
    printf '  \033[31m✗\033[0m %s 架构是 %s,本机(%s)需 %s\n' "$img" "$IA" "$HOST_ARCH" "$want"
    BAD=1
  fi
done
[ "$BAD" = "0" ] || _fail "存在架构不匹配的镜像,内网无法运行。请在【同架构】机器上重新准备镜像"
_ok "所有镜像架构匹配($want)"

# worker-mineru / worker-ai 与 worker-basic 共用同一镜像(compose 服务名区分)。
# compose.offline.yml 里已直接引用 ppt-management-worker-basic:latest,无需 tag,
# 此处仅做兼容性确认。
if ! docker image inspect ppt-management-worker-basic:latest >/dev/null 2>&1; then
  _fail "ppt-management-worker-basic:latest 未加载成功"
fi

echo
_log "== 已加载镜像 =="
docker images --format '  {{.Repository}}:{{.Tag}}  ({{.Size}})' | grep -E "ppt-management|pgvector/pgvector" || true
echo
_ok "✅ 镜像加载完成。下一步:cp .env.offline .env 并填写,然后 docker compose up -d"
