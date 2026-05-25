#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
RUNTIME_DIR="${RUNTIME_DIR:-$ROOT_DIR/runtime}"
PID_FILE="$RUNTIME_DIR/skills-manager.pid"
LOG_FILE="$RUNTIME_DIR/skills-manager.log"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-7890}"
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-}"

print_usage() {
  cat <<'EOF'
用法:
  ./scripts/deploy.sh init      初始化虚拟环境并安装依赖
  ./scripts/deploy.sh start     后台启动服务
  ./scripts/deploy.sh stop      停止服务
  ./scripts/deploy.sh restart   重启服务
  ./scripts/deploy.sh status    查看运行状态
  ./scripts/deploy.sh logs      查看实时日志

可选环境变量:
  PYTHON_BIN   默认 python3
  APP_HOST     默认 0.0.0.0
  APP_PORT     默认 7890
  SKILLS_PATH  skills 目录路径
  ENV_FILE     默认项目根目录 .env
  VENV_DIR     默认项目根目录 .venv
  PIP_INDEX_URL 自定义 pip 源
  PIP_TRUSTED_HOST 对应可信 host
EOF
}

log() {
  printf '[deploy] %s\n' "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令: $1" >&2
    exit 1
  fi
}

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    log "加载环境文件 $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi

  APP_HOST="${APP_HOST:-0.0.0.0}"
  APP_PORT="${APP_PORT:-7890}"
}

ensure_runtime_dir() {
  mkdir -p "$RUNTIME_DIR"
}

ensure_venv() {
  require_command "$PYTHON_BIN"
  if [[ ! -d "$VENV_DIR" ]]; then
    log "创建虚拟环境 $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
}

install_deps() {
  ensure_venv
  log "安装依赖"
  local pip_args=()
  if [[ -n "$PIP_INDEX_URL" ]]; then
    pip_args+=(--index-url "$PIP_INDEX_URL")
  fi
  if [[ -n "$PIP_TRUSTED_HOST" ]]; then
    pip_args+=(--trusted-host "$PIP_TRUSTED_HOST")
  fi

  if [[ ${#pip_args[@]} -gt 0 ]]; then
    "$VENV_DIR/bin/pip" install "${pip_args[@]}" --upgrade pip
    "$VENV_DIR/bin/pip" install "${pip_args[@]}" -r "$ROOT_DIR/requirements.txt"
  else
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$ROOT_DIR/requirements.txt"
  fi
}

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  if [[ -z "$pid" ]]; then
    return 1
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi

  rm -f "$PID_FILE"
  return 1
}

start_app() {
  load_env
  ensure_runtime_dir
  install_deps

  if is_running; then
    log "服务已运行，PID=$(cat "$PID_FILE")"
    exit 0
  fi

  local cmd=("$VENV_DIR/bin/python" "$ROOT_DIR/app.py" "$APP_PORT")
  log "启动服务 http://$APP_HOST:$APP_PORT"
  nohup env \
    APP_HOST="$APP_HOST" \
    APP_PORT="$APP_PORT" \
    SKILLS_PATH="${SKILLS_PATH:-}" \
    ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    "${cmd[@]}" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 1

  if is_running; then
    log "启动成功，PID=$(cat "$PID_FILE")"
    log "日志文件: $LOG_FILE"
    return 0
  fi

  log "启动失败，请检查日志: $LOG_FILE"
  exit 1
}

stop_app() {
  if ! is_running; then
    log "服务未运行"
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  log "停止服务，PID=$pid"
  kill "$pid"

  for _ in {1..10}; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      rm -f "$PID_FILE"
      log "已停止"
      return 0
    fi
    sleep 1
  done

  log "进程未在预期时间内退出，可手动检查 PID=$pid"
  exit 1
}

status_app() {
  load_env
  if is_running; then
    log "运行中"
    echo "PID: $(cat "$PID_FILE")"
    echo "URL: http://$APP_HOST:$APP_PORT"
    echo "LOG: $LOG_FILE"
    return 0
  fi

  log "未运行"
}

logs_app() {
  ensure_runtime_dir
  touch "$LOG_FILE"
  tail -f "$LOG_FILE"
}

main() {
  local action="${1:-start}"

  case "$action" in
    init)
      load_env
      ensure_runtime_dir
      install_deps
      log "初始化完成"
      ;;
    start)
      start_app
      ;;
    stop)
      stop_app
      ;;
    restart)
      stop_app || true
      start_app
      ;;
    status)
      status_app
      ;;
    logs)
      logs_app
      ;;
    help|-h|--help)
      print_usage
      ;;
    *)
      echo "未知命令: $action" >&2
      print_usage
      exit 1
      ;;
  esac
}

main "$@"
