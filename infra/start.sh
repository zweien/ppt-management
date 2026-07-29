#!/usr/bin/env bash
# PPT 素材库 —— 统一启动/停止脚本。
#
# 本项目有两类服务:
#   1) 宿主机常驻服务(ADR-0007 §6 / ADR-0008:重模型留宿主机 venv,容器经
#      docker0 网桥 172.17.0.1 访问,不进 compose):
#        - MinerU API    (PDF/PPTX 增强解析)      :8765
#        - Embedding 服务(bge-m3 /v1/embeddings)  :9997
#   2) Docker compose 栈(api/web/workers/postgres/redis/minio)。
#
# 用法:
#   infra/start.sh start    # 启动全部(宿主机服务 + compose 栈)
#   infra/start.sh stop     # 停止全部
#   infra/start.sh restart  # 重启全部
#   infra/start.sh status   # 查看各服务状态
#   infra/start.sh logs <服务名>  # 跟踪日志(host-mineru / host-embedding / compose)
#
# 宿主机服务用 PID 文件管理(轻量,不依赖 systemd/sudo)。若已装 systemd unit
# (infra/systemd/*.service),优先用 systemctl 管理更稳;本脚本为不装 unit 的场景兜底。
set -euo pipefail

# ============================================================================
# 配置区(按实际环境修改)
# ============================================================================
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${PID_DIR:-$REPO_ROOT/.run}"
LOG_DIR="${LOG_DIR:-$REPO_ROOT/.run/logs}"
mkdir -p "$PID_DIR" "$LOG_DIR"

# --- 宿主机 MinerU API (ADR-0007 §6) ---
MINERU_VENV="${MINERU_VENV:-$HOME/codebase/MinerU/.venv}"
MINERU_BIN="$MINERU_VENV/bin/mineru-api"
MINERU_HOST="${MINERU_HOST:-0.0.0.0}"
MINERU_PORT="${MINERU_PORT:-8765}"
MINERU_EXTRA_ARGS="${MINERU_EXTRA_ARGS:---allow-public-http-client}"

# --- 宿主机 Embedding 服务 (ADR-0008) ---
EMBEDDING_DIR="${EMBEDDING_DIR:-$HOME/codebase/xinference}"
EMBEDDING_RUN="$EMBEDDING_DIR/run.sh"
EMBEDDING_PORT="${EMBEDDING_PORT:-9997}"

# ============================================================================
# 辅助函数
# ============================================================================
_log() { printf '\033[36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
_ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }
_fail(){ printf '  \033[31m✗\033[0m %s\n' "$*"; }
_info(){ printf '  \033[33m·\033[0m %s\n' "$*"; }

# 判断 PID 是否存活
_is_running() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

# 等待 HTTP 端口就绪(轮询),参数:端口 期望状态码(可选,默认任意 2xx/4xx)
_wait_http() {
  local port="$1" want="${2:-}" n=0
  while [ "$n" -lt 60 ]; do
    code=$(curl -sS -m 3 -o /dev/null -w '%{http_code}' "http://localhost:$port/" 2>/dev/null || true)
    if [ -n "$code" ] && [ "$code" != "000" ]; then
      if [ -z "$want" ] || [ "$code" = "$want" ]; then return 0; fi
    fi
    n=$((n+1)); sleep 2
  done
  return 1
}

# ----------------------------------------------------------------------------
# 宿主机服务:start/stop/status 各一个,用 PID 文件
# ----------------------------------------------------------------------------
_host_pidfile() { echo "$PID_DIR/$1.pid"; }

_host_start() {
  local name="$1" port="$2" pidfile; pidfile="$(_host_pidfile "$name")"
  local pid; pid=$(cat "$pidfile" 2>/dev/null || true)
  if _is_running "$pid"; then _info "$name 已在运行 (pid $pid)"; return 0; fi
  # 端口已被占用(可能由本脚本之外的 systemd/手拉启动)
  local code; code=$(curl -sS -m 3 -o /dev/null -w '%{http_code}' "http://localhost:$port/" 2>/dev/null || true)
  if [ -n "$code" ] && [ "$code" != "000" ]; then
    _info "$name 端口 :$port 已有服务响应(HTTP $code,非本脚本启动),跳过"; return 0
  fi

  case "$name" in
    host-mineru)
      [ -x "$MINERU_BIN" ] || { _fail "$name: 找不到 $MINERU_BIN(MINERU_VENV 设对了吗?)"; return 1; }
      _log "启动 MinerU API ($MINERU_HOST:$MINERU_PORT) ..."
      nohup "$MINERU_VENV/bin/python3" "$MINERU_BIN" \
        --host "$MINERU_HOST" --port "$MINERU_PORT" $MINERU_EXTRA_ARGS \
        > "$LOG_DIR/mineru.log" 2>&1 &
      echo $! > "$pidfile"
      _wait_http "$MINERU_PORT" && _ok "MinerU API 就绪 (pid $(cat "$pidfile"))" || _fail "MinerU API 未在预期时间内就绪,查 $LOG_DIR/mineru.log"
      ;;
    host-embedding)
      local emb_py="$EMBEDDING_DIR/embedding_server.py"
      local emb_venv="$EMBEDDING_DIR/.venv/bin/python"
      [ -f "$emb_py" ] || { _fail "$name: 找不到 $emb_py(EMBEDDING_DIR 设对了吗?)"; return 1; }
      [ -x "$emb_venv" ] || { _fail "$name: 找不到 $emb_venv"; return 1; }
      _log "启动 Embedding 服务 (bge-m3, :$EMBEDDING_PORT;首次加载模型需 30-60s) ..."
      # 直接用 venv python 启动(不经 run.sh 多层 exec,确保 PID 准确);
      # run.sh 里的环境变量在这里显式 export
      ( cd "$EMBEDDING_DIR" && \
        HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}" \
        HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}" \
        TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}" \
        EMBEDDING_MODEL_PATH="${EMBEDDING_MODEL_PATH:-$HOME/.xinference/modelscope/models/Xorbits--bge-m3/snapshots/master}" \
        EMBEDDING_MODEL_NAME="${EMBEDDING_MODEL_NAME:-bge-m3}" \
        EMBEDDING_DEVICE="${EMBEDDING_DEVICE:-cuda}" \
        EMBEDDING_HOST=0.0.0.0 EMBEDDING_PORT="$EMBEDDING_PORT" \
        nohup "$emb_venv" "$emb_py" > "$LOG_DIR/embedding.log" 2>&1 & echo $! > "$pidfile" )
      _wait_http "$EMBEDDING_PORT" && _ok "Embedding 服务就绪 (pid $(cat "$pidfile"))" || _fail "Embedding 服务未在预期时间内就绪,查 $LOG_DIR/embedding.log"
      ;;
  esac
}

_host_stop() {
  local name="$1" pidfile; pidfile="$(_host_pidfile "$name")"
  local pid; pid=$(cat "$pidfile" 2>/dev/null || true)
  if ! _is_running "$pid"; then
    rm -f "$pidfile"; _info "$name 未在运行"; return 0
  fi
  _log "停止 $name (pid $pid) ..."
  # 先杀 PID 自身 + 其子进程树(uvicorn/fastapi 可能有 worker 子进程)
  pkill -TERM -P "$pid" 2>/dev/null || true
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do _is_running "$pid" || break; sleep 1; done
  if _is_running "$pid"; then
    _info "优雅退出超时,强杀 ..."
    pkill -KILL -P "$pid" 2>/dev/null || true
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"; _ok "$name 已停止"
}

_host_status() {
  local name="$1" port="$2"
  local pid; pid=$(cat "$(_host_pidfile "$name")" 2>/dev/null || true)
  local code; code=$(curl -sS -m 3 -o /dev/null -w '%{http_code}' "http://localhost:$port/" 2>/dev/null || echo "000")
  if _is_running "$pid"; then
    if [ "$code" != "000" ]; then _ok "$name: 运行中 (pid $pid, :$port HTTP $code)"
    else _info "$name: 进程在 (pid $pid) 但 :$port 未响应"; fi
  elif [ "$code" != "000" ]; then
    _info "$name: :$port 有响应 (HTTP $code,非本脚本启动)"
  else
    _fail "$name: 未运行"
  fi
}

# ----------------------------------------------------------------------------
# compose 栈
# ----------------------------------------------------------------------------
_compose() { ( cd "$REPO_ROOT" && docker compose "$@" ); }

compose_up() {
  _log "启动 compose 栈 ..."
  _compose up -d
  _ok "compose 栈已启动"
}

compose_down() {
  _log "停止 compose 栈 ..."
  _compose stop
  _ok "compose 栈已停止"
}

compose_status() {
  _log "compose 栈:"
  _compose ps --format 'table {{.Service}}\t{{.Status}}' 2>/dev/null || _compose ps
}

# ============================================================================
# 子命令
# ============================================================================
cmd_start() {
  _log "== 启动宿主机服务 =="
  _host_start host-mineru "$MINERU_PORT" || true
  _host_start host-embedding "$EMBEDDING_PORT" || true
  echo
  _log "== 启动 compose 栈 =="
  compose_up
  echo
  cmd_status
}

cmd_stop() {
  _log "== 停止 compose 栈 =="
  compose_down
  echo
  _log "== 停止宿主机服务 =="
  _host_stop host-embedding || true
  _host_stop host-mineru || true
  echo
  cmd_status
}

cmd_restart() {
  cmd_stop
  echo
  sleep 2
  cmd_start
}

cmd_status() {
  _log "== 宿主机服务 =="
  _host_status host-mineru "$MINERU_PORT"
  _host_status host-embedding "$EMBEDDING_PORT"
  echo
  compose_status
}

cmd_logs() {
  local svc="${1:-}"
  case "$svc" in
    host-mineru)    tail -f "$LOG_DIR/mineru.log" ;;
    host-embedding) tail -f "$LOG_DIR/embedding.log" ;;
    compose|"")     _compose logs -f --tail=50 ;;
    *)              _compose logs -f --tail=50 "$svc" ;;
  esac
}

usage() {
  cat <<EOF
PPT 素材库服务管理脚本

用法: infra/start.sh <命令> [参数]

命令:
  start           启动全部(宿主机 MinerU + Embedding + compose 栈)
  stop            停止全部
  restart         重启全部
  status          查看各服务状态
  logs [服务]     跟踪日志:
                    host-mineru / host-embedding / compose 服务名 / 空(compose 全部)

环境变量(可覆盖默认):
  MINERU_VENV, MINERU_PORT, EMBEDDING_DIR, EMBEDDING_PORT,
  PID_DIR(默认 \$REPO/.run), LOG_DIR(默认 \$REPO/.run/logs)
EOF
}

# ============================================================================
case "${1:-}" in
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_restart ;;
  status)  cmd_status ;;
  logs)    shift; cmd_logs "${1:-}" ;;
  *)       usage; exit 1 ;;
esac
