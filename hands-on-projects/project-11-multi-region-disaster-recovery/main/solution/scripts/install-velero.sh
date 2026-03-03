#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# install-velero.sh
# Installs Velero on both Kind clusters pointing to the local MinIO instance.
#
# Usage:  ./install-velero.sh
# Prereq: velero CLI installed, kind clusters running, MinIO running
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Detect host IP (MinIO runs on host) ───────────────────────────────────────
detect_host_ip() {
  # For Docker Desktop on Mac/Windows: host.docker.internal works
  # For Linux: use the docker bridge IP
  if [[ "$(uname)" == "Darwin" ]] || grep -qi microsoft /proc/version 2>/dev/null; then
    echo "host.docker.internal"
  else
    docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' 2>/dev/null || echo "172.17.0.1"
  fi
}

HOST_IP=$(detect_host_ip)
MINIO_URL="http://${HOST_IP}:9000"
log "MinIO URL: $MINIO_URL"

# ── Check Velero CLI ──────────────────────────────────────────────────────────
if ! command -v velero &>/dev/null; then
  error "velero CLI not found. Install from: https://velero.io/docs/latest/basic-install/"
fi
ok "velero CLI found: $(velero version --client-only 2>/dev/null | head -1)"

# ── Write MinIO credentials ───────────────────────────────────────────────────
CREDS_FILE=$(mktemp)
cat > "$CREDS_FILE" <<EOF
[default]
aws_access_key_id = minioadmin
aws_secret_access_key = minioadmin
EOF
log "Credentials file created at $CREDS_FILE"

install_velero_on_cluster() {
  local context="$1"
  local cluster_name="${context/kind-/}"

  log "Installing Velero on cluster: $cluster_name ($context)..."

  # Check if already installed
  if kubectl --context "$context" -n velero get deployment velero &>/dev/null 2>&1; then
    warn "Velero already installed on $context — skipping"
    return
  fi

  velero install \
    --kubecontext "$context" \
    --provider aws \
    --plugins velero/velero-plugin-for-aws:v1.9.0 \
    --bucket velero \
    --secret-file "$CREDS_FILE" \
    --use-volume-snapshots=false \
    --default-volumes-to-fs-backup \
    --backup-location-config \
      "region=minio,s3ForcePathStyle=true,s3Url=${MINIO_URL}" \
    --wait

  ok "Velero installed on $cluster_name"

  # Verify backup location
  log "Checking backup location on $cluster_name..."
  local retries=10
  while [[ $retries -gt 0 ]]; do
    local phase
    phase=$(kubectl --context "$context" -n velero get backupstoragelocation default \
      -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    if [[ "$phase" == "Available" ]]; then
      ok "Backup location is Available on $cluster_name"
      break
    fi
    warn "Waiting for backup location... (phase: ${phase:-pending}) retries left: $retries"
    sleep 5
    retries=$((retries - 1))
  done

  if [[ $retries -eq 0 ]]; then
    warn "Backup location not Available yet on $cluster_name — check: velero --kubecontext $context backup-location get"
  fi
}

# ── Install on both clusters ──────────────────────────────────────────────────
install_velero_on_cluster "kind-primary"
install_velero_on_cluster "kind-secondary"

# ── Clean up credentials ──────────────────────────────────────────────────────
rm -f "$CREDS_FILE"

# ── Create a test backup ──────────────────────────────────────────────────────
log "Triggering a test backup on primary..."
velero --kubecontext kind-primary backup create dr-install-test \
  --include-namespaces dr-system \
  --wait 2>/dev/null || warn "dr-system namespace may not exist yet — backup skipped"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Velero installed on both clusters!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo "  Useful commands:"
echo "    velero --kubecontext kind-primary  backup get"
echo "    velero --kubecontext kind-secondary backup get"
echo "    velero --kubecontext kind-primary  backup-location get"
echo "    velero --kubecontext kind-secondary backup-location get"
echo ""
echo "  MinIO Console: http://localhost:9001 → check velero/ bucket"
echo ""
echo "  Next step: apply the app manifests, then run ./failover.sh"
