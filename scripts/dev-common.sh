#!/usr/bin/env bash
# Shared helpers for backend.sh / frontend.sh

set -euo pipefail

_DEV_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
DEV_ROOT_DIR="$(cd "$_DEV_SCRIPT_DIR/.." && pwd)"
DEV_STATE_DIR="$DEV_ROOT_DIR/.dev"
DEV_BACKEND_DIR="$DEV_ROOT_DIR/backend"
DEV_FRONTEND_DIR="$DEV_ROOT_DIR/frontend"

mkdir -p "$DEV_STATE_DIR"

dev_is_windows() {
  case "$(uname -s)" in
    MINGW* | MSYS* | CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

dev_port_pids() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti ":$port" 2>/dev/null || true
  elif dev_is_windows; then
    netstat -ano 2>/dev/null \
      | grep -E ":${port}[[:space:]]" \
      | grep LISTENING \
      | awk '{print $NF}' \
      | sort -u || true
  elif command -v ss >/dev/null 2>&1; then
    ss -lptn 2>/dev/null \
      | grep ":${port}" \
      | sed -n 's/.*pid=\([0-9]*\).*/\1/p' || true
  else
    true
  fi
}

dev_kill_pid() {
  local pid=$1
  if dev_is_windows; then
    taskkill //PID "$pid" //F >/dev/null 2>&1 || true
  else
    kill "$pid" 2>/dev/null || true
  fi
}

dev_stop_port() {
  local port=$1
  local pids
  pids="$(dev_port_pids "$port")"
  if [ -z "$pids" ]; then
    return 1
  fi
  while IFS= read -r pid; do
    [ -n "$pid" ] && dev_kill_pid "$pid"
  done <<<"$pids"
  return 0
}

dev_http_code() {
  local url=$1
  local curl_cmd="curl"
  if dev_is_windows && command -v curl.exe >/dev/null 2>&1; then
    curl_cmd="curl.exe"
  fi
  if command -v "$curl_cmd" >/dev/null 2>&1; then
    "$curl_cmd" -s -o /dev/null -w "%{http_code}" \
      --connect-timeout 2 --max-time 3 "$url" 2>/dev/null || echo "000"
  else
    echo "000"
  fi
}

dev_port_listening() {
  [ -n "$(dev_port_pids "$1" | head -1)" ]
}

# Read KEY=value from an env file (first match; ignores comments/blank lines).
dev_env_file_value() {
  local env_file=$1
  local key=$2
  [ -f "$env_file" ] || return 0
  grep -E "^[[:space:]]*${key}=" "$env_file" 2>/dev/null \
    | head -1 \
    | sed -E "s/^[[:space:]]*${key}=//" \
    | sed -E 's/^["'\'']//; s/["'\'']$//' \
    | tr -d '\r' || true
}
