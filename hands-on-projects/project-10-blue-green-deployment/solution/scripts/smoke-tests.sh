#!/bin/bash
# smoke-tests.sh — Validate that the newly deployed environment works correctly
#
# Run AFTER health checks pass. Can test the inactive environment (before switch)
# or the live environment (after switch) by changing the target URL.
#
# Usage:
#   # Test green BEFORE switching (via service, not ingress)
#   ./smoke-tests.sh green blue-green
#
#   # Test live AFTER switching (via ingress)
#   ./smoke-tests.sh live blue-green deploytrack.local
#
# Exit codes:
#   0 = all tests passed
#   1 = one or more tests failed (do NOT switch traffic / rollback if already switched)

set -euo pipefail

TARGET=${1:-green}        # "green", "blue", or "live"
NAMESPACE=${2:-blue-green}
INGRESS_HOST=${3:-""}     # only needed when TARGET=live

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0

ok()    { echo -e "${GREEN}  [PASS]${NC} $1"; PASS=$((PASS+1)); }
fail()  { echo -e "${RED}  [FAIL]${NC} $1"; FAIL=$((FAIL+1)); }
info()  { echo -e "${YELLOW}  [INFO]${NC} $1"; }
header(){ echo -e "\n${BOLD}$1${NC}"; }

# ── Determine base URL ────────────────────────────────────────────────────────
if [ "$TARGET" = "live" ]; then
    if [ -z "$INGRESS_HOST" ]; then
        echo "ERROR: Must provide INGRESS_HOST when TARGET=live"
        echo "Usage: $0 live blue-green deploytrack.local"
        exit 1
    fi
    BASE_URL="http://$INGRESS_HOST"
    EXPECTED_ENV="live (via ingress)"
else
    # Port-forward or use service DNS (inside cluster)
    # For local testing: port-forward first
    #   kubectl port-forward svc/deploytrack-$TARGET 8888:80 -n blue-green &
    BASE_URL="http://localhost:8888"
    EXPECTED_ENV="$TARGET (via service)"
    info "Using kubectl port-forward: kubectl port-forward svc/deploytrack-$TARGET 8888:80 -n $NAMESPACE"
fi

echo ""
echo -e "${BOLD}=== Smoke Tests: $TARGET environment ($EXPECTED_ENV) ===${NC}"
echo ""

# ── Test 1: Health endpoint ───────────────────────────────────────────────────
header "Test 1 — /health"
RESP=$(curl -sf --max-time 10 "$BASE_URL/health" 2>/dev/null || echo "CURL_ERROR")
if [ "$RESP" = "CURL_ERROR" ]; then
    fail "/health returned no response"
else
    STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "parse_error")
    COLOR=$(echo  "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('color','?'))"  2>/dev/null || echo "parse_error")
    VERSION=$(echo "$RESP"| python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "parse_error")
    if [ "$STATUS" = "healthy" ]; then
        ok "status=healthy color=$COLOR version=$VERSION"
    else
        fail "status=$STATUS (expected: healthy)"
    fi
fi

# ── Test 2: Version endpoint ──────────────────────────────────────────────────
header "Test 2 — /version"
RESP=$(curl -sf --max-time 10 "$BASE_URL/version" 2>/dev/null || echo "CURL_ERROR")
if [ "$RESP" = "CURL_ERROR" ]; then
    fail "/version returned no response"
else
    BUILD=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('build','?'))" 2>/dev/null || echo "parse_error")
    ok "build=$BUILD"
fi

# ── Test 3: API list releases ─────────────────────────────────────────────────
header "Test 3 — GET /api/releases"
RESP=$(curl -sf --max-time 10 "$BASE_URL/api/releases" 2>/dev/null || echo "CURL_ERROR")
if [ "$RESP" = "CURL_ERROR" ]; then
    fail "/api/releases returned no response"
else
    COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "-1")
    if [ "$COUNT" -ge "0" ] 2>/dev/null; then
        ok "returned $COUNT release(s)"
    else
        fail "failed to parse response: $RESP"
    fi
fi

# ── Test 4: POST a release (write test) ───────────────────────────────────────
header "Test 4 — POST /api/releases (write test)"
RESP=$(curl -sf --max-time 10 -X POST "$BASE_URL/api/releases" \
    -H "Content-Type: application/json" \
    -d "{\"version\":\"smoke-test-$$\",\"color\":\"$TARGET\",\"environment\":\"ci\",\"notes\":\"Automated smoke test\"}" \
    2>/dev/null || echo "CURL_ERROR")
if [ "$RESP" = "CURL_ERROR" ]; then
    fail "POST /api/releases failed"
else
    RELEASE_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','?'))" 2>/dev/null || echo "?")
    ok "created release id=$RELEASE_ID"
fi

# ── Test 5: Homepage loads (200) ──────────────────────────────────────────────
header "Test 5 — GET / (HTML dashboard)"
HTTP_CODE=$(curl -so /dev/null --max-time 10 -w "%{http_code}" "$BASE_URL/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    ok "dashboard returns HTTP 200"
else
    fail "dashboard returns HTTP $HTTP_CODE (expected 200)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo -e " Results: ${GREEN}$PASS passed${NC} | ${RED}$FAIL failed${NC}"
echo "═══════════════════════════════════════════"
echo ""

if [ "$FAIL" -gt "0" ]; then
    echo -e "${RED}SMOKE TESTS FAILED — Do NOT switch traffic.${NC}"
    exit 1
else
    echo -e "${GREEN}All smoke tests passed. Ready to proceed.${NC}"
    exit 0
fi
