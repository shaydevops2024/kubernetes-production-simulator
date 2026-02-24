#!/usr/bin/env bash
# ============================================================
#  Install Kong Ingress Controller via Helm
#  Project 06: API Gateway with Advanced Traffic Management
# ============================================================
set -euo pipefail

NAMESPACE="api-gateway"
RELEASE_NAME="kong"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Installing Kong Ingress Controller"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Add Kong Helm repo
echo "→ Adding Kong Helm repository..."
helm repo add kong https://charts.konghq.com
helm repo update

# Create namespace if not exists
kubectl get namespace "${NAMESPACE}" &>/dev/null || \
  kubectl create namespace "${NAMESPACE}"

# Install Kong
echo "→ Installing Kong Ingress Controller..."
helm upgrade --install "${RELEASE_NAME}" kong/ingress \
  --namespace "${NAMESPACE}" \
  --values kong-values.yaml \
  --wait \
  --timeout 5m

echo ""
echo "✓ Kong installed successfully!"
echo ""
echo "Checking Kong status:"
kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=kong
echo ""
echo "Kong Proxy Service:"
kubectl get svc -n "${NAMESPACE}" "${RELEASE_NAME}-kong-proxy"
echo ""
echo "Kong Admin API:"
echo "  kubectl port-forward -n ${NAMESPACE} svc/${RELEASE_NAME}-kong-admin 8001:8001"
