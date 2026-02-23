# Main — Production Kubernetes Deployment

Deploy the complete observability stack to a Kubernetes cluster. This is where you take everything from the Docker Compose local setup and make it production-ready.

---

## What You'll Build

By the end of this phase you'll have:

```
Cluster: observability namespace
│
├── observe-app          (Deployment + Service + Ingress + ServiceMonitor)
│
├── kube-prometheus-stack  (Helm: Prometheus + AlertManager + Grafana)
│   ├── Prometheus         scrapes metrics from ServiceMonitors
│   ├── AlertManager       routes alerts to PagerDuty / Slack
│   └── Grafana            dashboards with provisioned datasources
│
├── Loki Stack (Helm)    log aggregation + querier
│
├── Tempo (Helm)         trace backend (replaces Jaeger in K8s)
│
├── Jaeger (Helm)        Jaeger UI wired to Tempo backend
│
├── Thanos (Helm)        long-term metrics storage via S3/MinIO
│   ├── Sidecar          runs alongside Prometheus
│   ├── Store Gateway    queries historical data from object store
│   └── Query            unified query layer over Prometheus + Store
│
└── PrometheusRules      SLO alerting rules applied by the Prometheus Operator
```

---

## Phases

### Phase 3A — Deploy the Application

Write the Kubernetes manifests to deploy ObserveApp:

```
main/
├── namespace.yaml           ← Create the observability namespace
├── app/
│   ├── deployment.yaml      ← App pod spec with OTLP env vars
│   ├── service.yaml         ← ClusterIP service
│   ├── ingress.yaml         ← Ingress for external access
│   └── servicemonitor.yaml  ← Tells Prometheus to scrape the app
```

Key decisions to make:
- What resource limits should the app have?
- What environment variables does it need? (`OTLP_ENDPOINT`, `ENVIRONMENT`)
- Which Ingress class and hostname to use?

### Phase 3B — Install the Monitoring Stack with Helm

Install `kube-prometheus-stack` — this gives you Prometheus, AlertManager, Grafana, and the Prometheus Operator in one chart:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace observability \
  -f main/solution/kube-prometheus-stack/values.yaml
```

Then install Loki, Tempo, and Jaeger:

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm upgrade --install loki grafana/loki-stack --namespace observability -f main/solution/loki/values.yaml
helm upgrade --install tempo grafana/tempo --namespace observability -f main/solution/tempo/values.yaml

helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm upgrade --install jaeger jaegertracing/jaeger --namespace observability -f main/solution/jaeger/values.yaml
```

### Phase 3C — Configure Alerting

Apply PrometheusRules for SLO-based alerting:

```bash
kubectl apply -f main/solution/prometheusrules/slo-rules.yaml
```

Configure AlertManager to send to PagerDuty:

```bash
kubectl create secret generic pagerduty-key \
  --from-literal=routingKey=YOUR_PAGERDUTY_KEY \
  -n observability

kubectl apply -f main/solution/alertmanager/config.yaml
```

### Phase 3D — Add Thanos for Long-Term Storage

Configure Prometheus to use the Thanos sidecar for shipping metrics to object storage:

```bash
# Create the object store secret first (S3 / MinIO credentials)
kubectl apply -f main/solution/thanos/object-store-secret.yaml

# Upgrade kube-prometheus-stack to enable the Thanos sidecar
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace observability \
  -f main/solution/kube-prometheus-stack/values.yaml

# Install Thanos components
helm repo add bitnami https://charts.bitnami.com/bitnami
helm upgrade --install thanos bitnami/thanos \
  --namespace observability \
  -f main/solution/thanos/values.yaml
```

---

## Solution Reference

A complete working solution is in `main/solution/`. Use it as a reference, not a copy-paste exercise.

```
main/solution/
├── README.md
├── deploy.sh                       ← One-shot deploy script
├── namespace.yaml
├── app/
│   ├── configmap.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── servicemonitor.yaml
│   └── ingress.yaml
├── kube-prometheus-stack/values.yaml
├── loki/values.yaml
├── tempo/values.yaml
├── jaeger/values.yaml
├── thanos/
│   ├── values.yaml
│   └── object-store-secret.yaml
├── alertmanager/
│   ├── config.yaml
│   └── pagerduty-secret.yaml
├── grafana/
│   └── dashboards-configmap.yaml
└── prometheusrules/
    └── slo-rules.yaml
```

---

## Prerequisites

- `kubectl` configured against a Kubernetes cluster (Kind, k3s, or cloud)
- Helm v3 installed
- The cluster must have an Ingress controller (NGINX recommended)
- At least 4 CPU / 8GB RAM available in the cluster

---

## Checklist

- [ ] Namespace created: `kubectl get ns observability`
- [ ] App running: `kubectl get pods -n observability -l app=observe-app`
- [ ] App reachable via Ingress
- [ ] Prometheus scraping the app: Prometheus UI → Targets → `observe-app` is UP
- [ ] Grafana accessible and showing the pre-built dashboard
- [ ] Logs visible in Grafana → Explore → Loki
- [ ] Traces visible in Jaeger UI
- [ ] Alerts visible in Prometheus → Alerts when error mode is enabled
- [ ] AlertManager routing working
- [ ] Thanos sidecar running alongside Prometheus (if Phase 3D complete)
