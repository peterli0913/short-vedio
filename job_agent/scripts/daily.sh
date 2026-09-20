#!/usr/bin/env bash
# Grok Bot daily routine. Does not open JobsDB HTML and does not click Apply.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export JOB_AGENT_HOME="${JOB_AGENT_HOME:-$ROOT/workspace}"

python3 run.py setup
if [[ -n "${1:-}" ]]; then
  python3 run.py search --keywords "$1" --pages "${PAGES:-2}" --min-score "${MIN_SCORE:-25}"
else
  python3 run.py search --pages "${PAGES:-2}" --min-score "${MIN_SCORE:-25}"
fi
python3 run.py batch --min-score "${MIN_SCORE:-40}" --limit "${LIMIT:-8}"

MAIL="$JOB_AGENT_HOME/imports/emails.txt"
if [[ -f "$MAIL" ]]; then
  python3 run.py classify --file "$MAIL"
  python3 run.py drafts
fi
python3 run.py digest
