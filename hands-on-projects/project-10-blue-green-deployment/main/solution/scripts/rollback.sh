#!/bin/bash
# rollback.sh — Emergency rollback to the previous environment
#
# Switches traffic back to the previous color (blue if green is live, vice versa).
# Does NOT require redeployment — the old environment stays running.
#
# Usage:
#   ./rollback.sh [namespace]
#   ./rollback.sh blue-green
#
# This script:
#   1. Finds the currently live color
#   2. Switches to the opposite color
#   3. Scales the failed environment to 0 replicas
#   4. Reports the result

set -euo pipefail

NAMESPACE=${1:-blue-green}

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}=== ROLLBACK INITIATED ===${NC}"
echo ""

# ── Find current live color ────────────────────────────────────────────────────
CURRENT=$(kubectl get service deploytrack-live -n $NAMESPACE \
    -o jsonpath='{.spec.selector.color}' 2>/dev/null || echo "")

if [ -z "$CURRENT" ]; then
    echo -e "${RED}ERROR: Could not determine current live color from service selector.${NC}"
    echo "  kubectl get service deploytrack-live -n $NAMESPACE"
    exit 1
fi

echo "  Current live: $CURRENT"

# ── Determine rollback target ──────────────────────────────────────────────────
if [ "$CURRENT" = "green" ]; then
    ROLLBACK_TO="blue"
elif [ "$CURRENT" = "blue" ]; then
    ROLLBACK_TO="green"
else
    echo -e "${RED}ERROR: Unknown current color: $CURRENT${NC}"
    exit 1
fi

echo "  Rolling back to: $ROLLBACK_TO"
echo ""

# ── Switch traffic ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}Step 1/3: Switching service-live selector → $ROLLBACK_TO${NC}"

kubectl patch service deploytrack-live -n $NAMESPACE \
    --type='json' \
    -p="[{\"op\":\"replace\",\"path\":\"/spec/selector/color\",\"value\":\"$ROLLBACK_TO\"}]"

ACTUAL=$(kubectl get service deploytrack-live -n $NAMESPACE \
    -o jsonpath='{.spec.selector.color}')

if [ "$ACTUAL" != "$ROLLBACK_TO" ]; then
    echo -e "${RED}CRITICAL: Failed to switch service selector! Manual intervention required.${NC}"
    echo "  kubectl patch service deploytrack-live -n $NAMESPACE --type=json -p='[{\"op\":\"replace\",\"path\":\"/spec/selector/color\",\"value\":\"$ROLLBACK_TO\"}]'"
    exit 1
fi
echo -e "  ${GREEN}Done.${NC} Traffic now routes to: $ROLLBACK_TO"

# ── Scale the failed environment to 0 ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}Step 2/3: Scaling $CURRENT (failed env) to 0 replicas${NC}"

kubectl scale deployment deploytrack-$CURRENT --replicas=0 -n $NAMESPACE
echo -e "  ${GREEN}Done.${NC} deploytrack-$CURRENT scaled to 0"

# ── Verify rollback target is healthy ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}Step 3/3: Verifying $ROLLBACK_TO is responding${NC}"

sleep 3  # brief pause for any inflight requests to drain

READY=$(kubectl get deployment deploytrack-$ROLLBACK_TO -n $NAMESPACE \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
READY=${READY:-0}

if [ "$READY" -ge "1" ]; then
    echo -e "  ${GREEN}Done.${NC} $READY pods ready for $ROLLBACK_TO"
else
    echo -e "  ${RED}WARNING: $ROLLBACK_TO has 0 ready pods. Check logs:${NC}"
    echo "    kubectl logs -l app=deploytrack,color=$ROLLBACK_TO -n $NAMESPACE --tail=50"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ROLLBACK COMPLETE                           ║${NC}"
echo -e "${GREEN}║  Live traffic → $ROLLBACK_TO                    ║${NC}"
echo -e "${GREEN}║  Failed env ($CURRENT) → scaled to 0         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Verify:"
echo "    kubectl get endpoints deploytrack-live -n $NAMESPACE"
echo "    kubectl get pods -n $NAMESPACE -l app=deploytrack"
echo ""
