#!/usr/bin/env bash
# Ask4Mo CAPSTONE LIVE-DEMONSTRATION environment (controlled academic demo, NOT production). Separate data, database and ledger from the review environment.
#
#   scripts/demo/live_env.sh start [offline|live]   copy curated stores, migrate a fresh DB, start API 8020, worker, frontend 3015, spend indicator 8030, register accounts
#   scripts/demo/live_env.sh promote [--yes]        run scripts/bootstrap_admin.py for the demo admin (dry-run unless --yes; --yes only after the owner's explicit confirmation)
#   scripts/demo/live_env.sh seed                   register the SYNTHETIC governed sources through the real Admin lifecycle (needs the admin)
#   scripts/demo/live_env.sh status | stop
#
# Provider mode is explicit: offline (default) never contacts a provider even if a key exists. live injects the OpenRouter key from the owner's main-checkout .env into the
# child processes only (never printed, never written) and routes EVERY request through the EUR ledger in $D/ledger (see src/demo_live). Processes run from a CLEAN git worktree.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
D="${DEMO_DIR:-/tmp/ask4mo_live_demo}"; WT="${DEMO_WORKTREE:-/tmp/ask4mo_live_wt}"; PY="$REPO/.venv/bin/python"; LOGIN="$D/logins.txt"; ADMIN=admin.live@example.invalid; CAND=candidate.live@example.invalid
pidof_port() { lsof -ti tcp:"$1" -sTCP:LISTEN | head -1 || true; }
env_common() {
  export COPILOT_DATA_DIR="$D/data" DATABASE_URL="sqlite:///$D/app.db" PYTHONPATH="$WT" API_ENV=development AGENT_COACH_ENABLED=true EMAIL_PROVIDER=memory FILE_SCAN_PROVIDER=fake \
         FRONTEND_ORIGINS=http://localhost:3015,http://127.0.0.1:3015 PYTHON_DOTENV_DISABLED=1 COPILOT_EMBEDDING_PROVIDER=local \
         ASK4MO_PROVIDER_MODE="${MODE:-offline}" ASK4MO_DEMO_LEDGER_DIR="$D/ledger" ASK4MO_DEMO_CATEGORY=troubleshooting
  unset OPENROUTER_API_KEY RAGAS_EVAL_API_KEY || true
  if [ "${MODE:-offline}" = live ]; then
    local k; k="$(grep '^OPENROUTER_API_KEY=' "$REPO/.env" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
    [ -n "$k" ] || { echo "no OPENROUTER_API_KEY in the main checkout .env; staying refused"; exit 1; }
    export OPENROUTER_API_KEY="$k" OPENROUTER_MODEL_FAST=openai/gpt-5.4-mini OPENROUTER_MODEL_BALANCED=openai/gpt-5.4 OPENROUTER_MODEL_ADVANCED=openai/gpt-5.5
  fi
}
case "${1:-}" in
  start)
    MODE="${2:-offline}"; [[ "$MODE" == offline || "$MODE" == live ]] || { echo "mode must be offline or live"; exit 2; }
    [ -z "$(pidof_port 8020)" ] && [ -z "$(pidof_port 3015)" ] || { echo "ports 8020/3015 busy; stop the other stack first"; exit 1; }
    [ -d "$WT" ] || git -C "$REPO" worktree add -q --detach "$WT" HEAD
    mkdir -p "$D/data" "$D/ledger"
    [ -d "$D/data/chroma" ] || { cp -Rp "$REPO/data/knowledge" "$D/data/knowledge"; cp -Rp "$REPO/data/chroma" "$D/data/chroma"; }
    if [ ! -f "$LOGIN" ]; then
      printf "admin: %s\nadmin_password: Adm1n-%s\ncandidate: %s\ncandidate_password: Cand-%s\n(synthetic demo accounts; file is mode 600, outside the repository)\n" "$ADMIN" "$("$PY" -c 'import secrets;print(secrets.token_urlsafe(10))')" "$CAND" "$("$PY" -c 'import secrets;print(secrets.token_urlsafe(10))')" > "$LOGIN"; chmod 600 "$LOGIN"
    fi
    env_common
    (cd "$WT" && "$PY" -m alembic upgrade head >/dev/null 2>&1)
    (cd "$WT" && nohup "$REPO/.venv/bin/uvicorn" src.api.main:app --host 127.0.0.1 --port 8020 > "$D/api.log" 2>&1 < /dev/null &)
    (cd "$WT" && ASK4MO_DEMO_CATEGORY=troubleshooting nohup "$PY" -m src.jobs.worker > "$D/worker.log" 2>&1 < /dev/null &)
    (cd "$REPO/frontend" && NEXT_PUBLIC_API_BASE_URL=http://localhost:8020/api/v1 nohup npm run dev -- --port 3015 > "$D/web.log" 2>&1 < /dev/null &)
    (cd "$REPO" && env -u OPENROUTER_API_KEY ASK4MO_DEMO_LEDGER_DIR="$D/ledger" nohup "$PY" scripts/demo/live_budget.py serve --port 8030 > "$D/indicator.log" 2>&1 < /dev/null &)
    for i in $(seq 1 40); do curl -sf http://127.0.0.1:8020/api/v1/health >/dev/null && break; sleep 1; done
    AP="$(sed -n 2p "$LOGIN" | cut -d' ' -f2)"; CP="$(sed -n 4p "$LOGIN" | cut -d' ' -f2)"
    curl -s -X POST http://127.0.0.1:8020/api/v1/auth/register -H 'content-type: application/json' -d "{\"email\":\"$ADMIN\",\"password\":\"$AP\",\"display_name\":\"Platform Admin (live demo)\"}" -o /dev/null || true
    curl -s -X POST http://127.0.0.1:8020/api/v1/auth/register -H 'content-type: application/json' -d "{\"email\":\"$CAND\",\"password\":\"$CP\",\"display_name\":\"Synthetic Candidate (live demo)\"}" -o /dev/null || true
    echo "started in $MODE mode: app http://localhost:3015  api http://127.0.0.1:8020  spend indicator http://127.0.0.1:8030  logins: $LOGIN"
    ;;
  promote)
    MODE=offline; env_common
    if [ "${2:-}" = "--yes" ]; then (cd "$WT" && "$PY" scripts/bootstrap_admin.py --email "$ADMIN" --yes); else (cd "$WT" && "$PY" scripts/bootstrap_admin.py --email "$ADMIN"); fi ;;
  seed) MODE=offline; env_common; "$PY" "$REPO/scripts/review/seed_governed_demo_sources.py" --base http://127.0.0.1:8020 --email "$ADMIN" --password-file "$LOGIN" ;;
  status) for p in 8020 3015 8030; do echo "port $p: pid=$(pidof_port $p)"; done; ASK4MO_DEMO_LEDGER_DIR="$D/ledger" "$PY" "$REPO/scripts/demo/live_budget.py" status | head -20 ;;
  stop)
    for port in 8020 3015 8030; do pid="$(pidof_port $port)"; [ -n "$pid" ] && kill "$pid" && echo "stopped $port ($pid)"; done
    wpid="$(pgrep -f "$WT.*src.jobs.worker|src.jobs.worker" | head -1 || true)"; [ -n "$wpid" ] && kill "$wpid" && echo "stopped worker ($wpid)"; true ;;
  *) sed -n 2,12p "$0"; exit 2 ;;
esac
