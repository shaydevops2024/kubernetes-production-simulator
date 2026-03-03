#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# trigger-canary.sh — Upgrade deploy-insight to v2 using canary strategy
#
# Usage:
#   ./trigger-canary.sh              # promote v1 → v2
#   ./trigger-canary.sh --rollback   # revert to v1
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

NAMESPACE="zero-downtime"
ROLLOUT="deploy-insight-canary"

if [[ "${1:-}" == "--rollback" ]]; then
  echo "▶ Rolling back ${ROLLOUT} to previous version..."
  kubectl argo rollouts undo "${ROLLOUT}" -n "${NAMESPACE}"
  echo "✓ Rollback initiated. Watch progress:"
  echo "  kubectl argo rollouts get rollout ${ROLLOUT} -n ${NAMESPACE} -w"
  exit 0
fi

echo "══════════════════════════════════════════════"
echo "  Canary Rollout: v1 (blue) → v2 (green)      "
echo "══════════════════════════════════════════════"
echo ""
echo "Steps:"
echo "  5%  → AnalysisRun checks error rate for 1 min"
echo "  25% → AnalysisRun checks error rate for 2 min"
echo "  50% → AnalysisRun checks error rate for 2 min"
echo "  100%→ Promotion complete"
echo ""
echo "▶ Triggering canary rollout (image: deploy-insight:v2)..."
kubectl argo rollouts set image "${ROLLOUT}" \
  app=deploy-insight:v2 \
  -n "${NAMESPACE}"

echo ""
echo "✓ Canary started!"
echo ""
echo "Watch in real-time:"
echo "  kubectl argo rollouts get rollout ${ROLLOUT} -n ${NAMESPACE} -w"
echo ""
echo "Watch metrics in Grafana:  http://localhost:4446"
echo "Watch Prometheus targets:  http://localhost:4447/targets"
echo ""
echo "To simulate a bad deployment (triggers auto-rollback):"
echo "  kubectl exec -it deploy/${ROLLOUT} -n ${NAMESPACE} -- curl -X POST http://localhost:4545/break"
