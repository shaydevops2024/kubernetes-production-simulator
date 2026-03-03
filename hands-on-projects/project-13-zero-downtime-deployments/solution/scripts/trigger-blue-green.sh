#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# trigger-blue-green.sh — Blue-Green rollout workflow
#
# Usage:
#   ./trigger-blue-green.sh           # deploy v2 to preview, pause for promotion
#   ./trigger-blue-green.sh --promote  # switch traffic to v2 (promote)
#   ./trigger-blue-green.sh --abort    # abort and rollback to v1
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

NAMESPACE="zero-downtime"
ROLLOUT="deploy-insight"

case "${1:-}" in
  --promote)
    echo "▶ Promoting deploy-insight to v2 (green)..."
    echo "  Traffic will instantly switch from v1 (blue) to v2 (green)."
    kubectl argo rollouts promote "${ROLLOUT}" -n "${NAMESPACE}"
    echo "✓ Promoted! v2 is now live."
    echo "  v1 pods stay running for 5 minutes (rollback window)."
    exit 0
    ;;
  --abort)
    echo "▶ Aborting rollout — reverting to v1 (blue)..."
    kubectl argo rollouts abort "${ROLLOUT}" -n "${NAMESPACE}"
    kubectl argo rollouts undo "${ROLLOUT}" -n "${NAMESPACE}"
    echo "✓ Rolled back to v1."
    exit 0
    ;;
esac

echo "══════════════════════════════════════════════"
echo "  Blue-Green Rollout: v1 (blue) → v2 (green)  "
echo "══════════════════════════════════════════════"
echo ""
echo "Step 1: Deploy v2 to the preview environment (0 user traffic)"
echo "Step 2: Run pre-promotion AnalysisRun on preview service"
echo "Step 3: You decide to promote (or Argo auto-promotes if configured)"
echo ""
echo "▶ Updating image to deploy-insight:v2..."
kubectl argo rollouts set image "${ROLLOUT}" \
  app=deploy-insight:v2 \
  -n "${NAMESPACE}"

echo ""
echo "✓ v2 is being deployed to the preview environment."
echo "  0 % of user traffic hits v2 yet."
echo ""
echo "Watch rollout status:"
echo "  kubectl argo rollouts get rollout ${ROLLOUT} -n ${NAMESPACE} -w"
echo ""
echo "Test v2 preview directly:"
echo "  kubectl port-forward svc/deploy-insight-canary 4552:80 -n ${NAMESPACE}"
echo "  Then open: http://localhost:4552"
echo ""
echo "When ready to switch traffic, run:"
echo "  ./trigger-blue-green.sh --promote"
echo ""
echo "If something looks wrong, abort:"
echo "  ./trigger-blue-green.sh --abort"
