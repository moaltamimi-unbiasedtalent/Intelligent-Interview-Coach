#!/usr/bin/env bash
# Bounded RAGAS run for the capstone live demonstration, always through the EUR ledger (category ragas, EUR 3.00 allocation).
#   scripts/demo/run_ragas.sh deterministic     free, no provider
#   scripts/demo/run_ragas.sh estimate          judge cost estimate, no model call
#   scripts/demo/run_ragas.sh live [LIMIT]      reviewer subset limited to LIMIT cases (default 2, max 6 without editing this script); needs the live ledger and the owner's key
# The evaluator key is the SAME OpenRouter key the owner placed in the main-checkout .env (no separate evaluator key exists); it is injected into this one process only and never printed.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; D="${DEMO_DIR:-/tmp/ask4mo_live_demo}"; WT="${DEMO_WORKTREE:-/tmp/ask4mo_live_wt}"; PY="$REPO/.venv/bin/python"
OUT="$D/ragas_runs"; mkdir -p "$OUT"
base() { export COPILOT_DATA_DIR="$D/data" PYTHONPATH="$WT" PYTHON_DOTENV_DISABLED=1 COPILOT_EMBEDDING_PROVIDER=local DATABASE_URL="sqlite:///$D/ragas_scratch.db"; unset OPENROUTER_API_KEY RAGAS_EVAL_API_KEY || true; }
case "${1:-}" in
  deterministic) base; export ASK4MO_PROVIDER_MODE=offline; cd "$WT" && "$PY" scripts/eval_ragas.py --output-dir "$OUT/deterministic_$(date +%Y%m%dT%H%M%S)" ;;
  estimate) base; export ASK4MO_PROVIDER_MODE=offline; cd "$WT" && "$PY" scripts/eval_ragas.py --mode judge --subset reviewer --estimate-only ;;
  live)
    N="${2:-2}"; [ "$N" -le 6 ] || { echo "limit above 6 needs a deliberate edit"; exit 2; }
    base; k="$(grep '^OPENROUTER_API_KEY=' "$REPO/.env" | head -1 | cut -d= -f2- | tr -d "\"'")"; [ -n "$k" ] || { echo "no key; refused"; exit 1; }
    export OPENROUTER_API_KEY="$k" RAGAS_EVAL_API_KEY="$k" RAGAS_EVAL_BASE_URL=https://openrouter.ai/api/v1 RAGAS_EVAL_MODEL=openai/gpt-4o-mini RAGAS_EVAL_EMBEDDING_MODEL=openai/text-embedding-3-small \
           OPENROUTER_MODEL_BALANCED=openai/gpt-5.4 OPENROUTER_MODEL_FAST=openai/gpt-5.4-mini OPENROUTER_MODEL_ADVANCED=openai/gpt-5.5 \
           ASK4MO_PROVIDER_MODE=live ASK4MO_DEMO_LEDGER_DIR="$D/ledger" ASK4MO_DEMO_CATEGORY=ragas
    cd "$WT" && "$PY" scripts/eval_ragas.py --live --subset reviewer --limit "$N" --require-live --output-dir "$OUT/live_$(date +%Y%m%dT%H%M%S)" ;;
  *) sed -n 2,6p "$0"; exit 2 ;;
esac
