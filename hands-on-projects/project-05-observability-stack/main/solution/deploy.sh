#!/usr/bin/env bash
# deploy.sh — Deploy the complete observability stack to Kubernetes
#
# Prerequisites:
#   - kubectl configured against a cluster
#   - Helm v3 installed
#   - NGINX Ingress Controller installed
#   - observe-app Docker image built and available
#
# Usage:
#   cd main/solution
#   chmod +x deploy.sh
#   ./deploy.sh

set -euo pipefail

NAMESPACE="observability"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info()    { echo -e "\n\033[0;34m▶  $*\033[0m"; }
success() { echo -e "\033[0;32m✓  $*\033[0m"; }
warn()    { echo -e "\033[0;33m⚠  $*\033[0m"; }

# ── 1. Namespace ───────────────────────────────────────────────────────────────
info "Creating namespace: $NAMESPACE"
kubectl apply -f "$SCRIPT_DIR/namespace.yaml"
success "Namespace ready"

# ── 2. Add Helm repos ──────────────────────────────────────────────────────────
info "Adding Helm repositories"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo add grafana             https://grafana.github.io/helm-charts             2>/dev/null || true
helm repo add jaegertracing       https://jaegertracing.github.io/helm-charts       2>/dev/null || true
helm repo add bitnami             https://charts.bitnami.com/bitnami               2>/dev/null || true
helm repo update
success "Helm repos ready"

# ── 3. kube-prometheus-stack (Prometheus + AlertManager + Grafana) ─────────────
info "Installing kube-prometheus-stack"
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace "$NAMESPACE" \
  --version "55.5.0" \
  -f "$SCRIPT_DIR/kube-prometheus-stack/values.yaml" \
  --wait --timeout 10m
success "kube-prometheus-stack ready"

# ── 4. Loki + Promtail ─────────────────────────────────────────────────────────
info "Installing Loki Stack"
helm upgrade --install loki grafana/loki-stack \
  --namespace "$NAMESPACE" \
  --version "2.10.2" \
  -f "$SCRIPT_DIR/loki/values.yaml" \
  --wait --timeout 5m
success "Loki Stack ready"

# ── 5. Tempo ───────────────────────────────────────────────────────────────────
info "Installing Tempo"
helm upgrade --install tempo grafana/tempo \
  --namespace "$NAMESPACE" \
  --version "1.7.1" \
  -f "$SCRIPT_DIR/tempo/values.yaml" \
  --wait --timeout 5m
success "Tempo ready"

# ── 6. Jaeger ──────────────────────────────────────────────────────────────────
info "Installing Jaeger"
helm upgrade --install jaeger jaegertracing/jaeger \
  --namespace "$NAMESPACE" \
  --version "0.71.11" \
  -f "$SCRIPT_DIR/jaeger/values.yaml" \
  --wait --timeout 5m
success "Jaeger ready"

# ── 7. Thanos (optional — comment out if no object store) ─────────────────────
info "Installing Thanos"
if kubectl get secret thanos-object-store -n "$NAMESPACE" &>/dev/null; then
  helm upgrade --install thanos bitnami/thanos \
    --namespace "$NAMESPACE" \
    --version "12.13.3" \
    -f "$SCRIPT_DIR/thanos/values.yaml" \
    --wait --timeout 10m
  success "Thanos ready"
else
  warn "Secret 'thanos-object-store' not found — skipping Thanos install"
  warn "To enable: kubectl apply -f thanos/object-store-secret.yaml && re-run this script"
fi

# ── 8. Deploy observe-app ──────────────────────────────────────────────────────
info "Deploying observe-app"
kubectl apply -f "$SCRIPT_DIR/app/"
success "observe-app deployed"

# ── 9. Apply PrometheusRules ───────────────────────────────────────────────────
info "Applying SLO alerting rules"
kubectl apply -f "$SCRIPT_DIR/prometheusrules/"
success "PrometheusRules applied"

# ── 10. Apply Grafana dashboards ───────────────────────────────────────────────
info "Applying Grafana dashboard ConfigMaps"
kubectl apply -f "$SCRIPT_DIR/grafana/"
success "Dashboards applied"

# ── 11. AlertManager config ────────────────────────────────────────────────────
info "Applying AlertManager routing config"
kubectl apply -f "$SCRIPT_DIR/alertmanager/config.yaml"
success "AlertManager config applied"

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo -e "\033[0;32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
echo -e "\033[0;32m  Deployment complete!\033[0m"
echo -e "\033[0;32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
echo ""
echo "Access (*.localhost resolves automatically — no /etc/hosts needed):"
echo "  App:        http://observe-app.localhost"
echo "  Grafana:    http://grafana.localhost    (admin / admin-change-me)"
echo "  Prometheus: http://prometheus.localhost"
echo "  Jaeger:     http://jaeger.localhost"
echo "  Thanos:     http://thanos.localhost"
echo ""
echo "Check pod status:"
echo "  kubectl get pods -n $NAMESPACE"
