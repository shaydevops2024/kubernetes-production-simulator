#!/bin/bash
# health-check.sh — Verify a blue-green environment is ready to receive traffic
#
# Usage:
#   ./health-check.sh [color] [namespace] [expected_replicas]
#   ./health-check.sh green blue-green 3
#
# Exit codes:
#   0 = healthy, ready for traffic switch
#   1 = not ready, do NOT switch traffic

set -euo pipefail

COLOR=${1:-green}
NAMESPACE=${2:-blue-green}
EXPECTED_REPLICAS=${3:-3}
MAX_WAIT=${4:-120}  # seconds to wait for pods to be ready

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_ok()   { echo -e "${GREEN}[OK]${NC}  $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

echo ""
log_info "Health check for: $COLOR environment (namespace: $NAMESPACE)"
log_info "Expected replicas: $EXPECTED_REPLICAS | Timeout: ${MAX_WAIT}s"
echo ""

# ── Check 1: Deployment exists ────────────────────────────────────────────────
log_info "Check 1/4: Deployment exists"
if ! kubectl get deployment deploytrack-$COLOR -n $NAMESPACE &>/dev/null; then
    log_fail "Deployment 'deploytrack-$COLOR' not found in namespace '$NAMESPACE'"
    exit 1
fi
log_ok "Deployment 'deploytrack-$COLOR' exists"

# ── Check 2: Wait for pods to be ready ───────────────────────────────────────
log_info "Check 2/4: Waiting for $EXPECTED_REPLICAS ready pods (max ${MAX_WAIT}s)"

ELAPSED=0
while true; do
    READY=$(kubectl get deployment deploytrack-$COLOR -n $NAMESPACE \
        -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    READY=${READY:-0}

    if [ "$READY" -ge "$EXPECTED_REPLICAS" ]; then
        break
    fi

    if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
        log_fail "Timeout: Only $READY/$EXPECTED_REPLICAS pods ready after ${MAX_WAIT}s"
        kubectl get pods -n $NAMESPACE -l "app=deploytrack,color=$COLOR" --no-headers
        exit 1
    fi

    echo "  Waiting... ($READY/$EXPECTED_REPLICAS ready, ${ELAPSED}s elapsed)"
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done
log_ok "$READY/$EXPECTED_REPLICAS pods ready"

# ── Check 3: Readiness probe passing on all pods ─────────────────────────────
log_info "Check 3/4: All pods passing readiness probes"

NOT_READY=$(kubectl get pods -n $NAMESPACE -l "app=deploytrack,color=$COLOR" \
    --no-headers | grep -v "Running" | grep -v "1/1" | wc -l || echo "0")

if [ "$NOT_READY" -gt "0" ]; then
    log_fail "$NOT_READY pods not in Running/Ready state"
    kubectl get pods -n $NAMESPACE -l "app=deploytrack,color=$COLOR"
    exit 1
fi
log_ok "All pods in Running state"

# ── Check 4: Health endpoint responding ──────────────────────────────────────
log_info "Check 4/4: /health endpoint responding"

POD=$(kubectl get pod -n $NAMESPACE -l "app=deploytrack,color=$COLOR" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -z "$POD" ]; then
    log_fail "No pod found for color=$COLOR"
    exit 1
fi

RESPONSE=$(kubectl exec -n $NAMESPACE $POD -- \
    python3 -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('http://localhost:5000/health', timeout=5)
    d = json.loads(r.read())
    print(d['status'], d['color'], d['version'])
except Exception as e:
    print('ERROR', str(e))
" 2>/dev/null || echo "ERROR exec failed")

if echo "$RESPONSE" | grep -q "^healthy"; then
    HEALTH_COLOR=$(echo "$RESPONSE" | awk '{print $2}')
    HEALTH_VER=$(echo "$RESPONSE" | awk '{print $3}')
    log_ok "Health check passed: status=healthy color=$HEALTH_COLOR version=$HEALTH_VER"
else
    log_fail "Health check failed: $RESPONSE"
    exit 1
fi

echo ""
log_ok "══════════════════════════════════════════════"
log_ok "  $COLOR environment is HEALTHY and ready."
log_ok "  Safe to run smoke tests and switch traffic."
log_ok "══════════════════════════════════════════════"
echo ""
exit 0
