#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — One-shot cluster bootstrap for Project 13
#
# Run this ONCE after creating your Kind cluster.
# It installs all required tools into the cluster.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SOLUTION_DIR="${ROOT_DIR}/solution"

echo "══════════════════════════════════════════════════════"
echo "  Zero-Downtime Deployment Platform — Cluster Setup   "
echo "══════════════════════════════════════════════════════"

# ── 1. MetalLB ────────────────────────────────────────────────────────────────
echo ""
echo "▶ Installing MetalLB..."
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.5/config/manifests/metallb-native.yaml
kubectl wait --namespace metallb-system \
  --for=condition=ready pod \
  --selector=app=metallb \
  --timeout=120s

kubectl apply -f "${SOLUTION_DIR}/k8s/metallb/"
echo "  ✓ MetalLB ready"

# ── 2. nginx Ingress ──────────────────────────────────────────────────────────
echo ""
echo "▶ Installing nginx Ingress Controller..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
echo "  ✓ nginx Ingress ready"

# ── 3. Argo Rollouts ──────────────────────────────────────────────────────────
echo ""
echo "▶ Installing Argo Rollouts..."
kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -
helm repo add argo https://argoproj.github.io/argo-helm --force-update
helm repo update argo
helm upgrade --install argo-rollouts argo/argo-rollouts \
  --namespace argo-rollouts \
  --values "${SOLUTION_DIR}/helm/argo-rollouts-values.yaml" \
  --wait --timeout 3m
echo "  ✓ Argo Rollouts ready"

# ── 4. Prometheus Stack ───────────────────────────────────────────────────────
echo ""
echo "▶ Installing kube-prometheus-stack..."
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo update prometheus-community
helm upgrade --install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values "${SOLUTION_DIR}/helm/prometheus-values.yaml" \
  --wait --timeout 5m
echo "  ✓ Prometheus + Grafana ready"

# ── 5. App namespace + monitoring resources ───────────────────────────────────
echo ""
echo "▶ Creating app namespace and monitoring resources..."
kubectl apply -f "${SOLUTION_DIR}/k8s/namespace.yaml"
kubectl apply -f "${SOLUTION_DIR}/k8s/monitoring/"
echo "  ✓ Namespace and ServiceMonitor created"

# ── 6. Build and load app image ───────────────────────────────────────────────
echo ""
echo "▶ Building app image..."
docker build -t deploy-insight:v1 "${ROOT_DIR}/app"
docker build -t deploy-insight:v2 \
  --build-arg APP_VERSION=v2 \
  "${ROOT_DIR}/app"

echo "▶ Loading images into Kind..."
kind load docker-image deploy-insight:v1
kind load docker-image deploy-insight:v2
echo "  ✓ Images loaded"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Access points:"
echo "    App UI:      http://localhost:4545"
echo "    Grafana:     http://localhost:4446  (admin / admin)"
echo "    Prometheus:  http://localhost:4447"
echo ""
echo "  Next steps:"
echo "    kubectl apply -f solution/k8s/app/"
echo "    kubectl apply -f solution/k8s/argo-rollouts/"
echo "    kubectl argo rollouts get rollout deploy-insight -n zero-downtime -w"
echo "══════════════════════════════════════════════════════"
