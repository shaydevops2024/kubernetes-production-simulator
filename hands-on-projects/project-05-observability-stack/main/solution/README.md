# Solution — Complete K8s Observability Stack

This is the reference solution. Use it to compare against your own work, not as a copy-paste exercise.

---

## What's Included

| File/Directory | What It Does |
|----------------|-------------|
| `namespace.yaml` | Creates the `observability` namespace |
| `deploy.sh` | One-shot deploy script (runs all steps in order) |
| `app/` | observe-app Deployment, Service, ServiceMonitor, Ingress, ConfigMap |
| `kube-prometheus-stack/values.yaml` | Prometheus + AlertManager + Grafana (via Helm) |
| `loki/values.yaml` | Loki log aggregation + Promtail collector (via Helm) |
| `tempo/values.yaml` | Tempo trace backend (via Helm) |
| `jaeger/values.yaml` | Jaeger UI wired to Tempo (via Helm) |
| `thanos/values.yaml` | Thanos long-term storage components (via Helm) |
| `thanos/object-store-secret.yaml` | Object store credentials template |
| `alertmanager/config.yaml` | AlertmanagerConfig CRD for routing |
| `alertmanager/pagerduty-secret.yaml` | PagerDuty integration key secret template |
| `prometheusrules/slo-rules.yaml` | SLO alerting + recording rules |
| `grafana/dashboards-configmap.yaml` | Dashboard auto-loaded by Grafana sidecar |

---

## Quick Deploy

```bash
# 1. Edit thanos/object-store-secret.yaml with real credentials (or skip Thanos)
# 2. Edit alertmanager/pagerduty-secret.yaml with real key (or skip PagerDuty)

cd main/solution
./deploy.sh
```

## Access (no /etc/hosts changes needed)

`*.localhost` subdomains resolve to `127.0.0.1` automatically on Linux/WSL2.

| Service    | URL                              | Credentials        |
|------------|----------------------------------|--------------------|
| App        | http://observe-app.localhost     |                    |
| Grafana    | http://grafana.localhost         | admin / admin-change-me |
| Prometheus | http://prometheus.localhost      |                    |
| Jaeger     | http://jaeger.localhost          |                    |
| Thanos     | http://thanos.localhost          |                    |

## Manual Step-by-Step

```bash
# Namespace
kubectl apply -f namespace.yaml

# Add Helm repos
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# kube-prometheus-stack (Prometheus + AlertManager + Grafana + Node Exporter + kube-state-metrics)
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace observability -f kube-prometheus-stack/values.yaml

# Loki + Promtail
helm upgrade --install loki grafana/loki-stack \
  --namespace observability -f loki/values.yaml

# Tempo
helm upgrade --install tempo grafana/tempo \
  --namespace observability -f tempo/values.yaml

# Jaeger UI
helm upgrade --install jaeger jaegertracing/jaeger \
  --namespace observability -f jaeger/values.yaml

# Thanos (requires object store secret)
kubectl apply -f thanos/object-store-secret.yaml
helm upgrade --install thanos bitnami/thanos \
  --namespace observability -f thanos/values.yaml

# Application
kubectl apply -f app/

# SLO rules
kubectl apply -f prometheusrules/

# Grafana dashboards
kubectl apply -f grafana/

# AlertManager routing
kubectl apply -f alertmanager/config.yaml
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     observability namespace                          │
│                                                                      │
│  observe-app (x2)                                                    │
│   ├── /metrics ──────────────────────────→ ServiceMonitor            │
│   ├── stdout JSON logs ──────────────────→ Promtail → Loki           │
│   └── OTLP traces → Tempo ←── Jaeger UI                             │
│                                                                      │
│  kube-prometheus-stack                                               │
│   ├── Prometheus ← ServiceMonitor (observe-app + cluster)           │
│   │    └── Thanos Sidecar → object store (S3/MinIO)                 │
│   ├── AlertManager → PagerDuty / Slack                              │
│   └── Grafana → Prometheus + Loki + Tempo/Jaeger                    │
│                                                                      │
│  Thanos                                                              │
│   ├── Store Gateway ← object store                                   │
│   ├── Query ← Prometheus sidecar + Store Gateway                     │
│   └── Compactor → compacts + downsamples blocks                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts Demonstrated

| Concept | Where |
|---------|-------|
| ServiceMonitor CRD | `app/servicemonitor.yaml` |
| PrometheusRule CRD (SLO alerting) | `prometheusrules/slo-rules.yaml` |
| Multi-window burn-rate alerting | `prometheusrules/slo-rules.yaml` |
| Recording rules | `prometheusrules/slo-rules.yaml` |
| Grafana dashboard as code | `grafana/dashboards-configmap.yaml` |
| AlertmanagerConfig CRD | `alertmanager/config.yaml` |
| Thanos sidecar pattern | `kube-prometheus-stack/values.yaml` |
| OTLP trace forwarding | `app/configmap.yaml` |
