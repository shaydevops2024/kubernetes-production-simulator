#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Kind cluster + MetalLB + ingress-nginx + ArgoCD setup
# Run from: main/solution/phase-1-cluster/
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CLUSTER_NAME="paas"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Creating Kind cluster: ${CLUSTER_NAME}"
kind create cluster --name "${CLUSTER_NAME}" --config "${SCRIPT_DIR}/kind-config.yaml"

echo "==> Verifying nodes..."
kubectl wait --for=condition=Ready nodes --all --timeout=120s
kubectl get nodes

echo "==> Installing MetalLB..."
helm repo add metallb https://metallb.github.io/metallb --force-update
helm install metallb metallb/metallb \
  --namespace metallb-system \
  --create-namespace \
  --wait --timeout 3m

echo "==> Waiting for MetalLB webhooks to be ready..."
kubectl wait --for=condition=available --timeout=90s \
  deployment/metallb-controller -n metallb-system

echo "==> Applying MetalLB IP pool (edit metallb-config.yaml if needed)..."
kubectl apply -f "${SCRIPT_DIR}/metallb-config.yaml"

echo "==> Installing ingress-nginx..."
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx --force-update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer \
  --wait --timeout 3m

echo "==> Verifying ingress-nginx EXTERNAL-IP..."
kubectl get svc -n ingress-nginx ingress-nginx-controller

echo "==> Installing ArgoCD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available --timeout=120s deployment/argocd-server -n argocd

ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d)

echo ""
echo "════════════════════════════════════════════════════════════"
echo "Phase 1 complete!"
echo ""
echo "  Nodes:        $(kubectl get nodes --no-headers | wc -l) ready"
echo "  Ingress IP:   $(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
echo ""
echo "  ArgoCD UI:    kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "  ArgoCD login: admin / ${ARGOCD_PASSWORD}"
echo ""
echo "Next: Phase 2 — Harbor + Gitea + Woodpecker CI"
echo "════════════════════════════════════════════════════════════"
