#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# failover.sh
# Performs a manual failover from the primary to the secondary cluster.
#
# Steps:
#   1. Check secondary cluster health (pre-flight)
#   2. Scale up secondary replicas (primary has 3, secondary has 2 → promote to 3)
#   3. Verify secondary is serving traffic (health check)
#   4. "Switch DNS" (here: update nginx.conf on the local simulation)
#   5. Log RTO
#
# Usage:
#   ./failover.sh [--dry-run]
#
# Options:
#   --dry-run   Print what would happen without making changes
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
dry()   { echo -e "${YELLOW}[DRY]${NC}   would run: $*"; }

FAILOVER_START=$(date +%s)
NGINX_CONF="$(dirname "$0")/../../local/nginx/nginx.conf"

log "Starting failover: PRIMARY → SECONDARY"
$DRY_RUN && warn "DRY-RUN mode — no changes will be made"

# ── Step 1: Pre-flight check on secondary ────────────────────────────────────
log "Step 1/5: Pre-flight check on secondary cluster..."

if ! kubectl --context kind-secondary -n dr-system get pods &>/dev/null; then
  error "Cannot reach secondary cluster (kind-secondary). Is it running?"
fi

SECONDARY_PODS=$(kubectl --context kind-secondary -n dr-system get pods \
  -l app=regionwatch --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')

if [[ "$SECONDARY_PODS" -eq 0 ]]; then
  error "No running regionwatch pods on secondary. Deploy the app first."
fi
ok "Secondary has $SECONDARY_PODS running pod(s)"

# ── Step 2: Scale up secondary ───────────────────────────────────────────────
log "Step 2/5: Scaling secondary to 3 replicas (promoting to active)..."
if $DRY_RUN; then
  dry "kubectl --context kind-secondary scale deployment regionwatch --replicas=3 -n dr-system"
else
  kubectl --context kind-secondary scale deployment regionwatch --replicas=3 -n dr-system
  kubectl --context kind-secondary -n dr-system rollout status deployment/regionwatch --timeout=60s
fi
ok "Secondary scaled to 3 replicas"

# ── Step 3: Health check on secondary ────────────────────────────────────────
log "Step 3/5: Health check on secondary (port-forward)..."
if $DRY_RUN; then
  dry "kubectl --context kind-secondary port-forward svc/regionwatch 5902:80 -n dr-system"
  dry "curl http://localhost:5902/health"
else
  # Start port-forward in background
  kubectl --context kind-secondary port-forward svc/regionwatch 5902:80 -n dr-system &
  PF_PID=$!
  sleep 3
  trap "kill $PF_PID 2>/dev/null || true" EXIT

  HEALTH_RESPONSE=$(curl -sf http://localhost:5902/health 2>/dev/null || echo "")
  kill $PF_PID 2>/dev/null || true

  if echo "$HEALTH_RESPONSE" | grep -q '"status": "healthy"'; then
    REGION=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('region_name','?'))")
    ok "Secondary health check passed — region: $REGION"
  else
    error "Secondary health check FAILED. Aborting failover. Response: ${HEALTH_RESPONSE:-no response}"
  fi
fi

# ── Step 4: Switch traffic ────────────────────────────────────────────────────
log "Step 4/5: Switching nginx to secondary region..."
if $DRY_RUN; then
  dry "sed -i 's|proxy_pass.*primary_region|proxy_pass http://secondary_region|' $NGINX_CONF"
  dry "docker compose exec nginx nginx -s reload"
else
  if [[ -f "$NGINX_CONF" ]]; then
    # Backup nginx.conf
    cp "$NGINX_CONF" "${NGINX_CONF}.bak"
    # Switch upstream
    sed -i 's|proxy_pass\s*http://primary_region|proxy_pass http://secondary_region|g' "$NGINX_CONF"

    # Reload nginx if running
    if docker ps --format '{{.Names}}' | grep -q "nginx"; then
      cd "$(dirname "$NGINX_CONF")/.." && docker compose exec nginx nginx -s reload && cd - > /dev/null
      ok "nginx reloaded — traffic now routes to secondary"
    else
      warn "nginx container not running — nginx.conf updated but not reloaded"
      warn "Start it with: cd local && docker compose up -d nginx"
    fi
  else
    warn "nginx.conf not found at $NGINX_CONF — skipping nginx switch"
    warn "In Kubernetes, run: kubectl --context kind-primary patch svc regionwatch-live ..."
  fi
fi

# ── Step 5: Log RTO ───────────────────────────────────────────────────────────
FAILOVER_END=$(date +%s)
RTO=$((FAILOVER_END - FAILOVER_START))
ok "Step 5/5: Failover complete"

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Failover completed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
echo "  From:    PRIMARY (eu-west-1)"
echo "  To:      SECONDARY (us-east-1)"
echo "  RTO:     ${RTO} seconds"
echo "  Status:  $([ $RTO -le 300 ] && echo 'WITHIN SLA (≤5 min)' || echo 'EXCEEDED SLA')"
echo ""
echo "  Live URL:      http://localhost:5858  → now secondary"
echo "  Secondary URL: http://localhost:5861  → direct"
echo "  Primary URL:   http://localhost:5860  → still running (rollback available)"
echo ""
echo "  To rollback: ./rollback.sh"
