#!/usr/bin/env bash
# Ask4Mo REVIEW-DAY environment: an isolated, keyless, reproducible stack. Nothing here touches the developer stores under data/ (they are COPIED).
#
#   scripts/review/review_env.sh start     copy the curated stores, migrate a fresh review database, start API (8020), job worker and frontend (3015), seed accounts
#   scripts/review/review_env.sh seed      register the SYNTHETIC governed demonstration sources through the real Admin lifecycle (idempotent)
#   scripts/review/review_env.sh check     knowledge readiness, one retrieval check, and the offline journey
#   scripts/review/review_env.sh stop      stop the three processes by exact PID (never pkill)
#
# Keyless by construction: the backend and worker run from a CLEAN git worktree (no .env, no .streamlit/secrets.toml), so no provider key can be discovered and no
# paid call can happen. FILE_SCAN_PROVIDER=fake is a DEVELOPMENT-ONLY scanner for this synthetic demonstration; never use it in staging or production.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
R="${REVIEW_DIR:-/tmp/ask4mo_review}"; WT="${REVIEW_WORKTREE:-/tmp/ask4mo_review_wt}"; PY="$REPO/.venv/bin/python"
LOGIN_FILE="${REVIEW_LOGIN_FILE:-/tmp/ask4mo_admin_login.txt}"
env_common() {
  export COPILOT_DATA_DIR="$R/data" DATABASE_URL="sqlite:///$R/app.db" PYTHONPATH="$WT" API_ENV=development AGENT_COACH_ENABLED=true EMAIL_PROVIDER=memory \
         FILE_SCAN_PROVIDER=fake FRONTEND_ORIGINS=http://localhost:3015,http://127.0.0.1:3015 PYTHON_DOTENV_DISABLED=1
}
pidof_port() { lsof -ti tcp:"$1" -sTCP:LISTEN | head -1 || true; }
case "${1:-}" in
  start)
    [ -z "$(pidof_port 8020)" ] && [ -z "$(pidof_port 3015)" ] || { echo "ports 8020 or 3015 are busy; run stop first"; exit 1; }
    [ -d "$WT" ] || git -C "$REPO" worktree add -q "$WT" HEAD
    mkdir -p "$R/data"
    [ -d "$R/data/chroma" ] || { cp -Rp "$REPO/data/knowledge" "$R/data/knowledge"; cp -Rp "$REPO/data/chroma" "$R/data/chroma"; }
    if [ ! -f "$LOGIN_FILE" ]; then
      printf "email: admin.demo@example.invalid\npassword: Adm1n-%s\n(throwaway review database; synthetic account)\n" "$("$PY" -c 'import secrets;print(secrets.token_urlsafe(9))')" > "$LOGIN_FILE"; chmod 600 "$LOGIN_FILE"
    fi
    env_common
    (cd "$WT" && "$PY" -m alembic upgrade head >/dev/null 2>&1)
    (cd "$WT" && nohup "$REPO/.venv/bin/uvicorn" src.api.main:app --host 127.0.0.1 --port 8020 > "$R/api.log" 2>&1 < /dev/null &)
    (cd "$WT" && nohup "$PY" -m src.jobs.worker > "$R/worker.log" 2>&1 < /dev/null &)
    (cd "$REPO/frontend" && NEXT_PUBLIC_API_BASE_URL=http://localhost:8020/api/v1 nohup npm run dev -- --port 3015 > "$R/web.log" 2>&1 < /dev/null &)
    for i in $(seq 1 30); do curl -sf http://127.0.0.1:8020/api/v1/health >/dev/null && break; sleep 1; done
    PW="$(sed -n 2p "$LOGIN_FILE" | cut -d' ' -f2)"
    curl -s -X POST http://127.0.0.1:8020/api/v1/auth/register -H 'content-type: application/json' -d "{\"email\":\"admin.demo@example.invalid\",\"password\":\"$PW\",\"display_name\":\"Platform Admin (demo)\"}" -o /dev/null || true
    curl -s -X POST http://127.0.0.1:8020/api/v1/auth/register -H 'content-type: application/json' -d '{"email":"candidate.demo@example.invalid","password":"demo-passphrase-synthetic-1","display_name":"Synthetic Candidate A"}' -o /dev/null || true
    (cd "$WT" && "$PY" - <<'PYEOF'
import os
from sqlalchemy import create_engine, text
with create_engine(os.environ["DATABASE_URL"]).begin() as c:
    c.execute(text("update users set platform_role='platform_admin' where email='admin.demo@example.invalid'"))
PYEOF
    )
    echo "started: frontend http://localhost:3015  api http://127.0.0.1:8020  admin login: $LOGIN_FILE (candidate.demo@example.invalid / the documented synthetic passphrase)"
    ;;
  seed) env_common; "$PY" "$REPO/scripts/review/seed_governed_demo_sources.py" --base http://127.0.0.1:8020 --email admin.demo@example.invalid --password-file "$LOGIN_FILE" ;;
  check)
    env_common
    (cd "$WT" && "$PY" scripts/check_demo_knowledge.py | tail -12)
    (cd "$REPO" && "$PY" scripts/demo_offline_journey.py | tail -4)
    ;;
  stop)
    for port in 8020 3015; do pid="$(pidof_port $port)"; [ -n "$pid" ] && kill "$pid" && echo "stopped $port ($pid)"; done
    wpid="$(pgrep -f 'src.jobs.worker' | head -1 || true)"; [ -n "$wpid" ] && kill "$wpid" && echo "stopped worker ($wpid)"
    ;;
  *) sed -n 2,12p "$0"; exit 2 ;;
esac
