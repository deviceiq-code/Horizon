#!/usr/bin/env bash
# Start/stop the Horizon development servers (Django backend + Vite frontend).
#
# Usage: ./dev.sh {start|stop|restart|status|logs} [backend|frontend]
#   With no service name, the command applies to both.
#
# Each server runs in the background in its own process group, so "stop" also ends
# its children (Django's autoreloader, the Vite process started by npm).
# PIDs and logs live in .run/ (git-ignored).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"
SERVICES=(backend frontend)
START_TIMEOUT=60 # seconds to wait for a server to answer
STOP_TIMEOUT=10  # seconds to wait before forcing a stop

# --- Per-service settings -------------------------------------------------------------------

service_dir() {
  case "$1" in
    backend) echo "$ROOT/backend" ;;
    frontend) echo "$ROOT/frontend" ;;
  esac
}

service_url() {
  case "$1" in
    backend) echo "http://127.0.0.1:8000" ;;
    frontend) echo "http://localhost:5173" ;;
  esac
}

service_port() {
  case "$1" in
    backend) echo 8000 ;;
    frontend) echo 5173 ;;
  esac
}

service_command() {
  case "$1" in
    # --insecure: the admin's static files are served even with DEBUG=False (e.g. while the
    # dev servers are open to the internet for tests)
    backend) echo "uv run python manage.py runserver --insecure 127.0.0.1:8000" ;;
    frontend) echo "npm run dev -- --port 5173 --strictPort" ;;
  esac
}

# --- Helpers --------------------------------------------------------------------------------

if [[ -t 1 ]]; then
  GREEN=$'\e[32m' RED=$'\e[31m' YELLOW=$'\e[33m' BOLD=$'\e[1m' RESET=$'\e[0m'
else
  GREEN='' RED='' YELLOW='' BOLD='' RESET=''
fi

info() { echo "${BOLD}$*${RESET}"; }
ok() { echo "  ${GREEN}✔${RESET} $*"; }
warn() { echo "  ${YELLOW}!${RESET} $*"; }
fail() { echo "  ${RED}✘${RESET} $*" >&2; }

pid_file() { echo "$RUN_DIR/$1.pid"; }
log_file() { echo "$RUN_DIR/$1.log"; }

# Prints the PID if the service is running; cleans up a stale PID file otherwise.
running_pid() {
  local file pid
  file="$(pid_file "$1")"
  [[ -f "$file" ]] || return 1
  pid="$(<"$file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "$pid"
    return 0
  fi
  rm -f "$file"
  return 1
}

# True while the service's session (setsid) still has live processes. Zombies are ignored:
# they have already exited, but "kill -0" would still report them as alive.
group_alive() {
  ps -o stat= -s "$1" 2>/dev/null | grep -qv '^Z'
}

port_in_use() {
  ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN
}

responds() {
  curl -s -o /dev/null --max-time 1 "$1"
}

# --- Commands -------------------------------------------------------------------------------

preflight() {
  if [[ ! -f "$ROOT/.env" ]]; then
    fail "Missing .env at the repository root (copy .env.example and fill it in)."
    exit 1
  fi
  if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
    warn "frontend/node_modules not found — running npm install..."
    (cd "$ROOT/frontend" && npm install --no-fund --no-audit >/dev/null)
  fi
}

check_migrations() {
  if ! (cd "$ROOT/backend" && uv run python manage.py migrate --check >/dev/null 2>&1); then
    warn "There are unapplied migrations in Live (or the database is unreachable)."
    warn "Run: cd backend && uv run python manage.py migrate"
  fi
  # Development (Test), when configured: a database of its own, migrated on its own
  if grep -q '^DATABASE_URL_DEVELOPMENT=.' "$ROOT/.env" &&
    ! (cd "$ROOT/backend" && HORIZON_ENVIRONMENT=development uv run python manage.py migrate --check >/dev/null 2>&1); then
    warn "There are unapplied migrations in Development (or the database is unreachable)."
    warn "Run: cd backend && HORIZON_ENVIRONMENT=development uv run python manage.py migrate"
  fi
}

start_service() {
  local name="$1" pid port url
  port="$(service_port "$name")"
  url="$(service_url "$name")"

  if pid="$(running_pid "$name")"; then
    ok "$name already running (PID $pid) — $url"
    return 0
  fi
  if port_in_use "$port"; then
    fail "$name: port $port is already in use by another process."
    return 1
  fi

  mkdir -p "$RUN_DIR"
  : >"$(log_file "$name")"
  (
    cd "$(service_dir "$name")"
    # setsid: new session/process group, so stop can signal the whole tree
    exec setsid bash -c "exec $(service_command "$name")" \
      >>"$(log_file "$name")" 2>&1 </dev/null
  ) &
  echo $! >"$(pid_file "$name")"

  local waited=0
  until responds "$url"; do
    if ! running_pid "$name" >/dev/null; then
      fail "$name exited during startup. Last log lines:"
      tail -n 20 "$(log_file "$name")" >&2
      return 1
    fi
    if ((waited >= START_TIMEOUT)); then
      fail "$name did not answer at $url after ${START_TIMEOUT}s. See: ./dev.sh logs $name"
      return 1
    fi
    sleep 1
    ((waited += 1))
  done
  ok "$name running (PID $(<"$(pid_file "$name")")) — $url"
}

stop_service() {
  local name="$1" pid
  if ! pid="$(running_pid "$name")"; then
    ok "$name is not running"
    return 0
  fi

  # The PID is the process group leader (setsid); signal the whole group
  kill -TERM -- "-$pid" 2>/dev/null || true
  local waited=0
  while group_alive "$pid"; do
    if ((waited >= STOP_TIMEOUT)); then
      warn "$name did not stop after ${STOP_TIMEOUT}s — forcing (SIGKILL)"
      kill -KILL -- "-$pid" 2>/dev/null || true
      break
    fi
    sleep 1
    ((waited += 1))
  done
  rm -f "$(pid_file "$name")"
  ok "$name stopped"
}

status_service() {
  local name="$1" pid
  if pid="$(running_pid "$name")"; then
    if responds "$(service_url "$name")"; then
      ok "$name running (PID $pid) — $(service_url "$name")"
    else
      warn "$name process is up (PID $pid) but not answering at $(service_url "$name")"
    fi
  else
    echo "  - $name stopped"
  fi
}

usage() {
  cat <<EOF
Usage: ./dev.sh {start|stop|restart|status|logs} [backend|frontend]

  start     Start the servers in the background
  stop      Stop the servers
  restart   Stop and start again
  status    Show whether each server is running
  logs      Follow the server logs (Ctrl+C to leave; servers keep running)

Without a service name, the command applies to both backend and frontend.
EOF
}

main() {
  local command="${1:-}" target="${2:-}"
  local services=("${SERVICES[@]}")
  if [[ -n "$target" ]]; then
    if [[ " ${SERVICES[*]} " != *" $target "* ]]; then
      usage
      exit 1
    fi
    services=("$target")
  fi

  local status=0
  case "$command" in
    start)
      info "Starting Horizon..."
      preflight
      [[ " ${services[*]} " == *" backend "* ]] && check_migrations
      for s in "${services[@]}"; do start_service "$s" || status=1; done
      if ((status == 0)) && [[ " ${services[*]} " == *" frontend "* ]]; then
        info "Open $(service_url frontend)"
      fi
      ;;
    stop)
      info "Stopping Horizon..."
      for s in "${services[@]}"; do stop_service "$s" || status=1; done
      ;;
    restart)
      "$0" stop "$target" && "$0" start "$target"
      return
      ;;
    status)
      info "Horizon status"
      for s in "${services[@]}"; do status_service "$s"; done
      ;;
    logs)
      local files=()
      for s in "${services[@]}"; do
        [[ -f "$(log_file "$s")" ]] && files+=("$(log_file "$s")")
      done
      if ((${#files[@]} == 0)); then
        echo "No logs yet. Start the servers with: ./dev.sh start"
        exit 1
      fi
      exec tail -n 50 -F "${files[@]}"
      ;;
    -h | --help | help)
      usage
      ;;
    *)
      usage
      exit 1
      ;;
  esac
  exit "$status"
}

main "$@"
