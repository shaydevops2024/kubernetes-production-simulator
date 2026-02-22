#!/usr/bin/env bash
# =============================================================================
# ChatFlow — Kubernetes Deployment Script
# Deploys the full ChatFlow platform to a Kubernetes cluster (Kind or otherwise)
# =============================================================================
set -euo pipefail

NAMESPACE="chatflow"
SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SOLUTION_DIR")")"
IMAGE_TAG="${IMAGE_TAG:-v1}"
REGISTRY="${REGISTRY:-chatflow}"
KIND_CLUSTER="${KIND_CLUSTER:-kind}"

# Colors
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# =============================================================================
# Step 0 — Build & load images (Kind)
# =============================================================================
build_and_load() {
  info "Building Docker images..."

  services=("chat-service" "presence-service" "notification-service" "file-service")
  for svc in "${services[@]}"; do
    info "  Building $svc..."
    docker build -t "${REGISTRY}/${svc}:${IMAGE_TAG}" "${PROJECT_ROOT}/app/${svc}/"
  done

  info "  Building frontend..."
  docker build -t "${REGISTRY}/chat-frontend:${IMAGE_TAG}" "${PROJECT_ROOT}/app/frontend/"

  info "Loading images into Kind cluster '${KIND_CLUSTER}'..."
  for svc in "${services[@]}"; do
    kind load docker-image "${REGISTRY}/${svc}:${IMAGE_TAG}" --name "${KIND_CLUSTER}"
  done
  kind load docker-image "${REGISTRY}/chat-frontend:${IMAGE_TAG}" --name "${KIND_CLUSTER}"

  info "Images loaded successfully."
}

# =============================================================================
# Step 1 — Namespace
# =============================================================================
apply_namespace() {
  info "Creating namespace..."
  kubectl apply -f "${SOLUTION_DIR}/namespace.yaml"
}

# =============================================================================
# Step 2 — Secrets & ConfigMaps
# =============================================================================
apply_config() {
  info "Applying secrets and configmaps..."
  kubectl apply -f "${SOLUTION_DIR}/secrets/"
  kubectl apply -f "${SOLUTION_DIR}/configmaps/"
}

# =============================================================================
# Step 3 — Infrastructure (Redis, PostgreSQL, MinIO)
# =============================================================================
apply_infrastructure() {
  info "Deploying infrastructure (Redis, PostgreSQL x3, MinIO)..."
  kubectl apply -f "${SOLUTION_DIR}/infrastructure/"

  info "Waiting for infrastructure to be ready..."
  kubectl rollout status statefulset/redis              -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status statefulset/postgres-chat      -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status statefulset/postgres-notifications -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status statefulset/postgres-files     -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status statefulset/minio              -n "${NAMESPACE}" --timeout=120s
  info "Infrastructure ready."
}

# =============================================================================
# Step 4 — Application Deployments + Services
# =============================================================================
apply_applications() {
  info "Deploying application services..."
  kubectl apply -f "${SOLUTION_DIR}/deployments/"
  kubectl apply -f "${SOLUTION_DIR}/services/"

  info "Waiting for deployments to roll out..."
  kubectl rollout status deployment/chat-service         -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status deployment/presence-service     -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status deployment/notification-service -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status deployment/file-service         -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status deployment/frontend             -n "${NAMESPACE}" --timeout=120s
  info "Applications ready."
}

# =============================================================================
# Step 5 — HPA + Ingress
# =============================================================================
apply_routing() {
  info "Applying HPA and Ingress..."
  kubectl apply -f "${SOLUTION_DIR}/hpa/"
  kubectl apply -f "${SOLUTION_DIR}/ingress/"
}

# =============================================================================
# Status check
# =============================================================================
check_status() {
  info "=== Deployment Status ==="
  kubectl get all -n "${NAMESPACE}"
  echo ""
  info "=== Ingress ==="
  kubectl get ingress -n "${NAMESPACE}"
  echo ""
  info "=== PVCs ==="
  kubectl get pvc -n "${NAMESPACE}"
}

# =============================================================================
# Main
# =============================================================================
usage() {
  cat <<EOF
Usage: $0 [COMMAND]

Commands:
  all         Full deploy (build images + apply everything)  [default]
  build       Build & load images into Kind cluster only
  infra       Apply namespace, secrets, configmaps, infrastructure
  apps        Apply application deployments, services, HPA, ingress
  status      Show current deployment status
  teardown    Delete the chatflow namespace (removes everything)

Environment variables:
  REGISTRY        Image registry/prefix  (default: chatflow)
  IMAGE_TAG       Image tag              (default: v1)
  KIND_CLUSTER    Kind cluster name      (default: kind)

Examples:
  ./deploy.sh                        # Full deploy
  ./deploy.sh build                  # Build images only
  REGISTRY=myrepo ./deploy.sh all    # Deploy with custom registry
EOF
}

case "${1:-all}" in
  all)
    build_and_load
    apply_namespace
    apply_config
    apply_infrastructure
    apply_applications
    apply_routing
    check_status
    info "ChatFlow deployed successfully! Access via Ingress."
    ;;
  build)
    build_and_load
    ;;
  infra)
    apply_namespace
    apply_config
    apply_infrastructure
    ;;
  apps)
    apply_applications
    apply_routing
    ;;
  status)
    check_status
    ;;
  teardown)
    warn "Deleting namespace '${NAMESPACE}' and all resources..."
    kubectl delete namespace "${NAMESPACE}" --ignore-not-found
    info "Teardown complete."
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    error "Unknown command: $1. Run '$0 help' for usage."
    ;;
esac
