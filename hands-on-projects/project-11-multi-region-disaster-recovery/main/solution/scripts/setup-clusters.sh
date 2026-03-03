#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup-clusters.sh
# Creates two Kind clusters (primary + secondary) and installs nginx Ingress.
#
# Usage:  ./setup-clusters.sh
# Prereq: kind, kubectl, docker installed
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# ── Check prereqs ─────────────────────────────────────────────────────────────
for cmd in kind kubectl docker; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd not found. Please install it first." >&2
    exit 1
  fi
done
ok "Prerequisites: kind, kubectl, docker found"

# ── Create primary cluster ────────────────────────────────────────────────────
if kind get clusters 2>/dev/null | grep -q "^primary$"; then
  warn "Cluster 'primary' already exists — skipping creation"
else
  log "Creating Kind cluster: primary (2 workers)"
  cat <<EOF | kind create cluster --name primary --config -
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
  - role: worker
  - role: worker
EOF
  ok "Primary cluster created"
fi

# ── Create secondary cluster ──────────────────────────────────────────────────
if kind get clusters 2>/dev/null | grep -q "^secondary$"; then
  warn "Cluster 'secondary' already exists — skipping creation"
else
  log "Creating Kind cluster: secondary (1 worker)"
  cat <<EOF | kind create cluster --name secondary --config -
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 8090    # different host port to avoid conflict with primary
        protocol: TCP
  - role: worker
EOF
  ok "Secondary cluster created"
fi

# ── Install nginx Ingress ─────────────────────────────────────────────────────
INGRESS_MANIFEST="https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml"

log "Installing nginx Ingress on primary..."
kubectl --context kind-primary apply -f "$INGRESS_MANIFEST"
kubectl --context kind-primary -n ingress-nginx wait \
  --for=condition=ready pod \
  -l app.kubernetes.io/component=controller \
  --timeout=120s
ok "nginx Ingress ready on primary"

log "Installing nginx Ingress on secondary..."
kubectl --context kind-secondary apply -f "$INGRESS_MANIFEST"
kubectl --context kind-secondary -n ingress-nginx wait \
  --for=condition=ready pod \
  -l app.kubernetes.io/component=controller \
  --timeout=120s
ok "nginx Ingress ready on secondary"

# ── Start MinIO (backup storage) ──────────────────────────────────────────────
if docker ps --format '{{.Names}}' | grep -q "^minio$"; then
  warn "MinIO container already running"
else
  log "Starting MinIO container..."
  docker run -d \
    --name minio \
    --restart unless-stopped \
    -p 9000:9000 \
    -p 9001:9001 \
    -e MINIO_ROOT_USER=minioadmin \
    -e MINIO_ROOT_PASSWORD=minioadmin \
    quay.io/minio/minio server /data --console-address ":9001"
  sleep 3
  docker exec minio mc alias set local http://localhost:9000 minioadmin minioadmin
  docker exec minio mc mb --ignore-existing local/velero
  docker exec minio mc mb --ignore-existing local/dr-backups
  ok "MinIO running at http://localhost:9000 (console: http://localhost:9001)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Multi-region clusters ready!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo "  Clusters:"
kubectl config get-contexts | grep -E "kind-primary|kind-secondary" || true
echo ""
echo "  MinIO Console: http://localhost:9001 (minioadmin / minioadmin)"
echo ""
echo "  Next step: run ./install-velero.sh"
