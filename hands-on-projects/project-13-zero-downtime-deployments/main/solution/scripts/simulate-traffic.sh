#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# simulate-traffic.sh — Generate realistic traffic so Grafana graphs look good
#
# Usage:
#   ./simulate-traffic.sh                   # localhost:4545
#   ./simulate-traffic.sh http://my-host    # custom URL
#   ./simulate-traffic.sh --break           # also hit /break on v2 to cause errors
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BASE_URL="${1:-http://localhost:4545}"
BREAK_MODE="${2:-}"

echo "Generating traffic to ${BASE_URL} — press Ctrl+C to stop"
echo ""

# Inject errors into v2 if --break is passed
if [[ "${BREAK_MODE}" == "--break" ]]; then
  echo "⚠ Injecting errors into v2 (direct port 4552)..."
  curl -s -X POST http://localhost:4552/break > /dev/null 2>&1 || true
  echo "  Done — watch error rate climb in Grafana"
fi

TASK_ID=0

while true; do
  # Normal GET requests (simulate browser traffic)
  curl -s "${BASE_URL}/" > /dev/null
  curl -s "${BASE_URL}/health" > /dev/null
  curl -s "${BASE_URL}/version" > /dev/null

  # Task CRUD (simulate app usage)
  TASK_ID=$((TASK_ID + 1))
  curl -s -X POST "${BASE_URL}/tasks" \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"Task ${TASK_ID}\", \"priority\": \"medium\"}" > /dev/null

  curl -s "${BASE_URL}/tasks" > /dev/null

  # Occasionally complete or delete a task
  if (( TASK_ID % 5 == 0 )); then
    curl -s -X PATCH "${BASE_URL}/tasks/$((TASK_ID - 1))/done" > /dev/null || true
  fi
  if (( TASK_ID % 8 == 0 )); then
    curl -s -X DELETE "${BASE_URL}/tasks/$((TASK_ID - 2))" > /dev/null || true
  fi

  sleep 0.5

  # Print a heartbeat every 20 iterations
  if (( TASK_ID % 20 == 0 )); then
    echo "  [$(date '+%H:%M:%S')] ${TASK_ID} tasks created — traffic flowing"
  fi
done
