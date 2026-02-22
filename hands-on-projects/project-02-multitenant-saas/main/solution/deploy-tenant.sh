#!/usr/bin/env bash
# ============================================================
# deploy-tenant.sh
# Deploys one tenant namespace from the tenant-template
#
# Usage:
#   TENANT=alice-corp   PLAN=enterprise bash main/solution/deploy-tenant.sh
#   TENANT=bob-industries PLAN=pro      bash main/solution/deploy-tenant.sh
#   TENANT=charlie-ltd  PLAN=starter   bash main/solution/deploy-tenant.sh
# ============================================================
set -euo pipefail

TENANT="${TENANT:?Set TENANT=<slug> e.g. TENANT=alice-corp}"
PLAN="${PLAN:?Set PLAN=starter|pro|enterprise e.g. PLAN=pro}"
TEMPLATE_DIR="$(cd "$(dirname "$0")/tenant-template" && pwd)"

# ── Plan quota values ──────────────────────────────────────────────────────────
case "$PLAN" in
  starter)
    REQ_CPU=500m;   REQ_MEM=512Mi; LIM_CPU=1;  LIM_MEM=1Gi;  PODS=5;  SVCS=5
    ;;
  pro)
    REQ_CPU=2;      REQ_MEM=2Gi;   LIM_CPU=4;  LIM_MEM=4Gi;  PODS=20; SVCS=10
    ;;
  enterprise)
    REQ_CPU=8;      REQ_MEM=8Gi;   LIM_CPU=16; LIM_MEM=16Gi; PODS=100; SVCS=20
    ;;
  *)
    echo "ERROR: PLAN must be starter, pro, or enterprise"
    exit 1
    ;;
esac

# Generate a simple password (deterministic for demo purposes)
DB_PASSWORD="tenant-$(echo "$TENANT" | tr -d '-')-pass"

echo "==> Deploying tenant: $TENANT (plan: $PLAN)"
echo ""

# Apply all template files, substituting placeholders
for f in "$TEMPLATE_DIR"/*.yaml; do
  fname="$(basename "$f")"
  echo "--- Applying $fname for tenant-$TENANT"
  sed \
    -e "s/TENANT_SLUG/$TENANT/g" \
    -e "s/PLAN_VALUE/$PLAN/g" \
    -e "s/REQ_CPU_VALUE/$REQ_CPU/g" \
    -e "s/REQ_MEM_VALUE/$REQ_MEM/g" \
    -e "s/LIM_CPU_VALUE/$LIM_CPU/g" \
    -e "s/LIM_MEM_VALUE/$LIM_MEM/g" \
    -e "s/PODS_VALUE/$PODS/g" \
    -e "s/SVCS_VALUE/$SVCS/g" \
    -e "s/DB_PASSWORD_VALUE/$DB_PASSWORD/g" \
    "$f" | kubectl apply -f -
done

echo ""
echo "==> Tenant tenant-$TENANT deployed (plan: $PLAN)"
echo ""
echo "Wait for pods:"
echo "  kubectl get pods -n tenant-$TENANT -w"
echo ""
echo "Describe quota:"
echo "  kubectl describe quota -n tenant-$TENANT"
echo ""
echo "Test access:"
echo "  kubectl port-forward -n tenant-$TENANT svc/app-service 9001:8011"
echo "  curl -H 'X-Tenant-ID: $TENANT' http://localhost:9001/tasks"
