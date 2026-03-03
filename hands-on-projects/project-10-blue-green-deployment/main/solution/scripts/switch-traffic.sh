#!/bin/bash
# switch-traffic.sh — Switch the live service selector to blue or green
#
# This is the core blue-green traffic switch.
# It patches the `deploytrack-live` service selector to point to the new color.
# The switch is atomic and instant (no dropped connections).
#
# Usage:
#   ./switch-traffic.sh [target_color] [namespace]
#   ./switch-traffic.sh green blue-green    ← switch to green
#   ./switch-traffic.sh blue  blue-green    ← rollback to blue
#
# Exit codes:
#   0 = switch successful
#   1 = switch failed

set -euo pipefail

TARGET=${1:-green}
NAMESPACE=${2:-blue-green}

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$TARGET" != "blue" ] && [ "$TARGET" != "green" ]; then
    echo -e "${RED}ERROR:${NC} TARGET must be 'blue' or 'green', got: $TARGET"
    exit 1
fi

echo ""
echo -e "${YELLOW}==> Switching live traffic to: ${NC}${TARGET^^}"
echo ""

# ── Get current active color ──────────────────────────────────────────────────
CURRENT=$(kubectl get service deploytrack-live -n $NAMESPACE \
    -o jsonpath='{.spec.selector.color}' 2>/dev/null || echo "unknown")

echo "  Current active: $CURRENT"
echo "  Switching to:   $TARGET"

if [ "$CURRENT" = "$TARGET" ]; then
    echo -e "${YELLOW}  Already routing to $TARGET — no change needed.${NC}"
    exit 0
fi

# ── Patch the service selector ────────────────────────────────────────────────
echo ""
echo -e "  Patching deploytrack-live selector..."

kubectl patch service deploytrack-live -n $NAMESPACE \
    --type='json' \
    -p="[{\"op\":\"replace\",\"path\":\"/spec/selector/color\",\"value\":\"$TARGET\"}]"

# Also update the annotation for documentation
kubectl annotate service deploytrack-live -n $NAMESPACE \
    "blue-green/active=$TARGET" --overwrite &>/dev/null || true

# ── Verify the switch ─────────────────────────────────────────────────────────
ACTUAL=$(kubectl get service deploytrack-live -n $NAMESPACE \
    -o jsonpath='{.spec.selector.color}')

if [ "$ACTUAL" = "$TARGET" ]; then
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Traffic successfully switched to: $TARGET${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo ""
    echo "  Verify with:"
    echo "    kubectl get endpoints deploytrack-live -n $NAMESPACE"
    echo "    curl http://deploytrack.local/version"
    echo ""
    exit 0
else
    echo ""
    echo -e "${RED}ERROR: Switch failed. Selector is still: $ACTUAL${NC}"
    exit 1
fi
