#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# verify-dr.sh
# Runs a full DR verification checklist against both clusters.
# Outputs a pass/fail report.
#
# Usage: ./verify-dr.sh
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
PASS=0; FAIL=0; WARN_COUNT=0

check_pass() { echo -e "  ${GREEN}✓${NC} $*"; PASS=$((PASS+1)); }
check_fail() { echo -e "  ${RED}✗${NC} $*"; FAIL=$((FAIL+1)); }
check_warn() { echo -e "  ${YELLOW}!${NC} $*"; WARN_COUNT=$((WARN_COUNT+1)); }
section()    { echo -e "\n${BLUE}━━━ $* ━━━${NC}"; }

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║       RegionWatch — DR Verification Report         ║"
echo "╚════════════════════════════════════════════════════╝"

# ── 1. Cluster connectivity ───────────────────────────────────────────────────
section "1. Cluster Connectivity"
for ctx in kind-primary kind-secondary; do
  if kubectl --context "$ctx" cluster-info &>/dev/null 2>&1; then
    check_pass "$ctx: reachable"
  else
    check_fail "$ctx: NOT reachable"
  fi
done

# ── 2. App pods ───────────────────────────────────────────────────────────────
section "2. Application Pods"
for ctx in kind-primary kind-secondary; do
  label="${ctx/kind-/}"
  PODS=$(kubectl --context "$ctx" -n dr-system get pods -l app=regionwatch \
    --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$PODS" -ge 1 ]]; then
    check_pass "$label: $PODS regionwatch pod(s) running"
  else
    check_fail "$label: no regionwatch pods running"
  fi
done

# ── 3. Database ───────────────────────────────────────────────────────────────
section "3. Database (PostgreSQL)"
for ctx in kind-primary kind-secondary; do
  label="${ctx/kind-/}"
  DB_PODS=$(kubectl --context "$ctx" -n dr-system get pods -l app=postgres \
    --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$DB_PODS" -ge 1 ]]; then
    check_pass "$label: postgres pod running"
  else
    check_fail "$label: postgres not running"
  fi
done

# ── 4. Velero ─────────────────────────────────────────────────────────────────
section "4. Velero Backup System"
for ctx in kind-primary kind-secondary; do
  label="${ctx/kind-/}"

  # Velero pod
  VELERO_PODS=$(kubectl --context "$ctx" -n velero get pods -l app.kubernetes.io/name=velero \
    --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$VELERO_PODS" -ge 1 ]]; then
    check_pass "$label: velero pod running"
  else
    check_fail "$label: velero pod not running"
  fi

  # Backup location
  BL_PHASE=$(kubectl --context "$ctx" -n velero get backupstoragelocation default \
    -o jsonpath='{.status.phase}' 2>/dev/null || echo "unknown")
  if [[ "$BL_PHASE" == "Available" ]]; then
    check_pass "$label: backup storage location Available"
  else
    check_fail "$label: backup storage location phase=$BL_PHASE"
  fi
done

# ── 5. Recent backups ─────────────────────────────────────────────────────────
section "5. Recent Backups"
BACKUP_COUNT=$(velero --kubecontext kind-primary backup get \
  --output json 2>/dev/null | \
  python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    completed = [i for i in data.get('items', []) if i.get('status', {}).get('phase') == 'Completed']
    print(len(completed))
except:
    print(0)
" 2>/dev/null || echo "0")

if [[ "$BACKUP_COUNT" -ge 1 ]]; then
  check_pass "primary: $BACKUP_COUNT completed backup(s) found"
else
  check_fail "primary: no completed backups — run: velero --kubecontext kind-primary backup create test --include-namespaces dr-system --wait"
fi

# ── 6. App health API ─────────────────────────────────────────────────────────
section "6. Application Health API (port-forward)"
for ctx in kind-primary kind-secondary; do
  label="${ctx/kind-/}"
  port=$([[ "$ctx" == "kind-primary" ]] && echo 5900 || echo 5901)

  kubectl --context "$ctx" port-forward svc/regionwatch "${port}:80" -n dr-system &>/dev/null &
  PF_PID=$!
  sleep 2

  HEALTH=$(curl -sf "http://localhost:${port}/health" 2>/dev/null || echo "")
  kill $PF_PID 2>/dev/null || true

  if echo "$HEALTH" | grep -q '"status"'; then
    ROLE=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('region_role','?'))" 2>/dev/null || echo "?")
    check_pass "$label: health OK (role=$ROLE)"
  else
    check_fail "$label: health endpoint did not respond"
  fi
done

# ── 7. Ingress ────────────────────────────────────────────────────────────────
section "7. Ingress"
for ctx in kind-primary kind-secondary; do
  label="${ctx/kind-/}"
  ING=$(kubectl --context "$ctx" -n dr-system get ingress regionwatch --no-headers 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$ING" -ge 1 ]]; then
    check_pass "$label: ingress resource exists"
  else
    check_warn "$label: ingress not found"
  fi
done

# ── 8. Schedule ───────────────────────────────────────────────────────────────
section "8. Backup Schedule"
SCHEDULE=$(kubectl --context kind-primary -n velero get schedule dr-system-schedule \
  --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [[ "$SCHEDULE" -ge 1 ]]; then
  check_pass "primary: dr-system-schedule exists"
else
  check_warn "primary: scheduled backup not configured"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════════════════╗"
printf "║  %-48s  ║\n" "RESULTS:"
printf "║  %-48s  ║\n" "  Passed:   $PASS"
printf "║  %-48s  ║\n" "  Failed:   $FAIL"
printf "║  %-48s  ║\n" "  Warnings: $WARN_COUNT"
echo "╚════════════════════════════════════════════════════╝"

if [[ $FAIL -eq 0 ]]; then
  echo -e "\n${GREEN}DR verification PASSED — system is ready for failover.${NC}"
  exit 0
else
  echo -e "\n${RED}DR verification FAILED — fix the issues above before a real failover.${NC}"
  exit 1
fi
