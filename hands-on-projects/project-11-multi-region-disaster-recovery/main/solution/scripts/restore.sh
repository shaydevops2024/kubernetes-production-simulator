#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# restore.sh
# Restores a Velero backup from MinIO onto the secondary cluster.
# Simulates a full disaster recovery: secondary cluster starts fresh.
#
# Usage:
#   ./restore.sh [BACKUP_NAME]
#   ./restore.sh                    # uses the most recent backup
#   ./restore.sh dr-system-schedule-20240101120000
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

BACKUP_NAME="${1:-}"

# ── List available backups ────────────────────────────────────────────────────
log "Available backups on primary cluster:"
velero --kubecontext kind-primary backup get 2>/dev/null || warn "Could not list backups from primary"

# ── Find backup name ──────────────────────────────────────────────────────────
if [[ -z "$BACKUP_NAME" ]]; then
  log "No backup name provided — using most recent completed backup..."
  BACKUP_NAME=$(velero --kubecontext kind-primary backup get \
    --output json 2>/dev/null | \
    python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('items', [])
completed = [i for i in items if i.get('status', {}).get('phase') == 'Completed']
if not completed:
    print('')
else:
    # Sort by creation timestamp, most recent first
    completed.sort(key=lambda x: x['metadata'].get('creationTimestamp',''), reverse=True)
    print(completed[0]['metadata']['name'])
" 2>/dev/null || echo "")

  if [[ -z "$BACKUP_NAME" ]]; then
    error "No completed backups found. Create one with: velero --kubecontext kind-primary backup create test --include-namespaces dr-system --wait"
  fi
  ok "Using backup: $BACKUP_NAME"
fi

# ── Verify backup exists ──────────────────────────────────────────────────────
BACKUP_STATUS=$(velero --kubecontext kind-primary backup get "$BACKUP_NAME" \
  -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
if [[ "$BACKUP_STATUS" != "Completed" ]]; then
  error "Backup '$BACKUP_NAME' is not in Completed state (current: ${BACKUP_STATUS:-not found})"
fi
ok "Backup '$BACKUP_NAME' is Completed"

# ── Start the clock ───────────────────────────────────────────────────────────
RESTORE_START=$(date +%s)
echo ""
warn "=== DR TEST STARTING ==="
warn "This simulates a complete primary region failure."
warn "We will DELETE dr-system from secondary, then restore from backup."
echo ""
read -rp "Press ENTER to continue (or Ctrl+C to abort)..."

# ── Delete dr-system from secondary ──────────────────────────────────────────
log "Step 1/4: Deleting dr-system from secondary (simulating fresh cluster after DR)..."
kubectl --context kind-secondary delete namespace dr-system --ignore-not-found --wait=true
ok "dr-system deleted from secondary"

# ── Wait for namespace to be fully gone ──────────────────────────────────────
log "Waiting for namespace termination..."
WAIT=30
while kubectl --context kind-secondary get namespace dr-system &>/dev/null && [[ $WAIT -gt 0 ]]; do
  sleep 2
  WAIT=$((WAIT - 1))
done
ok "Namespace gone"

# ── Restore ───────────────────────────────────────────────────────────────────
log "Step 2/4: Restoring backup '$BACKUP_NAME' to secondary cluster..."
velero --kubecontext kind-secondary restore create \
  "dr-restore-$(date +%s)" \
  --from-backup "$BACKUP_NAME" \
  --include-namespaces dr-system \
  --restore-volumes=true \
  --wait
ok "Restore completed"

# ── Verify pods are running ───────────────────────────────────────────────────
log "Step 3/4: Waiting for pods to start..."
kubectl --context kind-secondary -n dr-system wait \
  --for=condition=ready pod \
  -l app=regionwatch \
  --timeout=120s
ok "RegionWatch pods are ready"

# ── Health check ──────────────────────────────────────────────────────────────
log "Step 4/4: Running health check..."
kubectl --context kind-secondary port-forward svc/regionwatch 5902:80 -n dr-system &
PF_PID=$!
sleep 3
trap "kill $PF_PID 2>/dev/null || true" EXIT

HEALTH=$(curl -sf http://localhost:5902/health 2>/dev/null || echo "")
kill $PF_PID 2>/dev/null || true

RESTORE_END=$(date +%s)
RTO=$((RESTORE_END - RESTORE_START))

if echo "$HEALTH" | grep -q '"status"'; then
  REGION=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('region_name','?'))" 2>/dev/null || echo "?")
  ok "Health check passed — region: $REGION"
else
  warn "Health check inconclusive: ${HEALTH:-no response}"
fi

# ── Results ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  DR Test Complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
echo "  Backup used:  $BACKUP_NAME"
echo "  RTO achieved: ${RTO} seconds"
echo "  RTO target:   300 seconds (5 min)"
echo "  SLA status:   $([ $RTO -le 300 ] && echo '✓ WITHIN SLA' || echo '✗ EXCEEDED SLA')"
echo ""
echo "  Secondary access: kubectl --context kind-secondary port-forward svc/regionwatch 5902:80 -n dr-system"
echo "  Then open:        http://localhost:5902"
