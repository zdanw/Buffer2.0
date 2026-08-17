#!/usr/bin/env bash
# Control local frontend (Vite on :5174)
#
# Usage:
#   ./scripts/frontend.sh start|stop|status|restart

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Git Bash on Windows: use PowerShell (cmd.exe start breaks the terminal).
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    if command -v powershell.exe >/dev/null 2>&1; then
      exec powershell.exe -NoProfile -File "$SCRIPT_DIR/frontend.ps1" "${1:-}"
    fi
    ;;
esac

# shellcheck disable=SC1091
source "$SCRIPT_DIR/dev-common.sh"

PORT=5174
LOG_FILE="$DEV_STATE_DIR/frontend.log"
PID_FILE="$DEV_STATE_DIR/frontend.pid"

usage() {
  cat <<EOF
Usage: $(basename "$0") <start|stop|status|restart>

Examples:
  $(basename "$0") start
  $(basename "$0") stop
  $(basename "$0") status
EOF
}

status() {
  local pids code
  pids="$(dev_port_pids "$PORT" | tr '\n' ' ')"
  code="$(dev_http_code "http://localhost:${PORT}/")"
  if [ "$code" = "200" ]; then
    echo "running (port $PORT${pids:+, pid(s) $pids})"
    return 0
  fi
  if [ -n "$pids" ]; then
    echo "starting (port $PORT, pid(s) $pids)"
    return 1
  fi
  echo "stopped"
  return 1
}

start() {
  if status >/dev/null 2>&1; then
    echo "frontend: $(status)"
    echo "Already running. Use: $(basename "$0") restart"
    return 0
  fi

  if [ ! -d "$DEV_FRONTEND_DIR/node_modules" ]; then
    echo "error: dependencies missing. Run: cd frontend && npm ci"
    exit 1
  fi

  echo "frontend: starting..."
  (
    cd "$DEV_FRONTEND_DIR"
    nohup npm run dev >>"$LOG_FILE" 2>&1 &
  )

  for i in $(seq 1 30); do
    if dev_port_listening "$PORT"; then
      if [ "$(dev_http_code "http://localhost:${PORT}/")" = "200" ]; then
        echo "frontend: started -> http://localhost:${PORT} (log: .dev/frontend.log)"
        return 0
      fi
    fi
    sleep 1
  done

  echo "frontend: launched but not responding yet. See .dev/frontend.log"
  tail -n 20 "$LOG_FILE" || true
  exit 1
}

stop() {
  if dev_stop_port "$PORT"; then
    rm -f "$PID_FILE"
    echo "frontend: stopped"
  else
    rm -f "$PID_FILE"
    echo "frontend: not running"
  fi
}

ACTION="${1:-}"
case "$ACTION" in
  start) start ;;
  stop) stop ;;
  status) echo "frontend: $(status)" ;;
  restart) stop; start ;;
  *) usage; exit 1 ;;
esac
