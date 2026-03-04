# Project 05 — Observability Stack: Explained

---

## 1. The App

You are deploying a **complete production observability platform** around a pre-built SaaS analytics application called **ObserveApp**. The app is already instrumented — it emits Prometheus metrics, structured JSON logs, and OpenTelemetry traces. Your job is to deploy the entire observability backend that collects, stores, and visualizes all of it.

```
ObserveApp (FastAPI SaaS analytics app)
  │ generates:
  ├── /metrics → Prometheus metrics (requests, errors, latency, business metrics)
  ├── stdout   → JSON structured logs → Promtail → Loki
  └── OTLP/gRPC → OpenTelemetry traces → Jaeger (local) / Tempo (K8s)
                                              │
                                         Grafana ◄── unified dashboard
                                              │
                                        AlertManager → Slack / PagerDuty
```

| Component | What it does |
|-----------|-------------|
| **ObserveApp** | Pre-instrumented FastAPI app simulating a SaaS product with real user traffic patterns |
| **Prometheus** | Scrapes `/metrics` every 15s, stores time-series data, evaluates alerting rules |
| **Loki** | Log aggregation — stores and indexes structured logs; queried via LogQL |
| **Promtail** | Log collector — tails Docker container logs, ships to Loki |
| **Jaeger** | Distributed tracing backend — receives OTLP traces, shows request flows |
| **Tempo** | Production-grade trace storage (replaces Jaeger in K8s phase) |
| **Thanos** | Long-term Prometheus metrics storage (K8s phase) — stores months of metrics |
| **Grafana** | Unified UI — dashboards for metrics (Prometheus/Thanos), logs (Loki), traces (Jaeger/Tempo) |
| **AlertManager** | Routes alerts from Prometheus rules to Slack, email, or PagerDuty |

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-05-observability-stack/local/

docker compose up --build
```

Once running:

| UI | URL | Credentials |
|----|-----|-------------|
| ObserveApp Dashboard | http://localhost:8080 | none |
| Prometheus | http://localhost:9090 | none |
| Grafana | http://localhost:3000 | admin / admin |
| Loki | http://localhost:3100 | none |
| Jaeger | http://localhost:16686 | none |
| AlertManager | http://localhost:9093 | none |

**Generate load on ObserveApp:**
```bash
# Simulate user activity (triggers metrics, logs, and traces)
for i in {1..50}; do
  curl -s http://localhost:8080/api/dashboard &
  curl -s http://localhost:8080/api/users &
  curl -s http://localhost:8080/api/events &
done
wait
```

**Explore Grafana:**
1. Open http://localhost:3000 → Log in as admin/admin
2. Go to Dashboards → a pre-built ObserveApp dashboard is already provisioned
3. You can see request rates, error rates, latency percentiles, active users

**Query Prometheus directly:**
```
# In Prometheus UI → Graph tab
# All requests per second
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# 99th percentile latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

**Query Loki logs:**
In Grafana → Explore → Select Loki datasource:
```
{service="observeapp"} | json | level="error"
{service="observeapp"} | json | user_id="user123"
```

### Phase 2 — Deploy to Kubernetes (Helm)

```bash
cd hands-on-projects/project-05-observability-stack/main/

# Install kube-prometheus-stack (Prometheus + Grafana + AlertManager)
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f solution/kube-prometheus-stack/values.yaml

# Install Loki
helm install loki grafana/loki-stack \
  -n monitoring \
  -f solution/loki/values.yaml

# Install Tempo (distributed tracing)
helm install tempo grafana/tempo \
  -n monitoring \
  -f solution/tempo/values.yaml

# Deploy ObserveApp with ServiceMonitor
kubectl apply -f solution/app/
```

---

## 3. How to Test It

### Verify Prometheus is Scraping ObserveApp

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="observeapp")'

# Or in Prometheus UI: Status → Targets
# ObserveApp should show as UP
```

### Test Metrics Are Flowing

```bash
# Query metric directly
curl http://localhost:8080/metrics | grep http_requests_total

# Query from Prometheus API
curl 'http://localhost:9090/api/v1/query?query=http_requests_total'
```

### Test Log Aggregation (Loki)

```bash
# Check Promtail is shipping logs
curl http://localhost:3100/ready  # Should return "ready"

# Check log labels
curl http://localhost:3100/loki/api/v1/labels

# Query logs via API
curl -G http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={service="observeapp"}' \
  --data-urlencode 'limit=10'
```

### Test Distributed Tracing (Jaeger)

```bash
# Make a request that generates a trace
curl http://localhost:8080/api/dashboard

# Open Jaeger UI: http://localhost:16686
# Select service "observeapp" → Find Traces
# Click on a trace to see the full call path with timing
```

### Trigger an Alert

```bash
# Stop ObserveApp to trigger "InstanceDown" alert
docker compose stop observeapp

# Wait ~1 minute, then check AlertManager
curl http://localhost:9093/api/v1/alerts

# Or in AlertManager UI: http://localhost:9093
# Alert should fire: "ObserveApp is down"
```

### Kubernetes: Verify ServiceMonitor

```bash
# Check ServiceMonitor is created
kubectl get servicemonitor -n monitoring

# Verify Prometheus picked it up (Prometheus UI → Status → Targets)
kubectl port-forward svc/kube-prometheus-stack-prometheus -n monitoring 9090:9090
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Prometheus** | Metrics collection + alerting | Scrapes `/metrics`, stores TSDB, evaluates alert rules defined in YAML |
| **Loki** | Log aggregation | Receives logs from Promtail, stores with labels, queryable via LogQL |
| **Promtail** | Log collection | Reads Docker container logs, attaches labels, ships to Loki |
| **Jaeger** | Trace backend (local) | Receives OTLP traces via gRPC :4317, stores and visualizes them |
| **Tempo** | Trace backend (K8s) | Production Jaeger replacement; integrates with Grafana natively |
| **Thanos** | Long-term metrics (K8s) | Stores Prometheus data to object storage (MinIO); enables multi-cluster queries |
| **Grafana** | Visualization | Unified dashboards; datasources: Prometheus, Loki, Tempo, Jaeger |
| **AlertManager** | Alert routing | Groups alerts, silences, routes to Slack/PagerDuty via webhook |
| **Helm** | K8s package manager | Installs kube-prometheus-stack, Loki, Tempo, Thanos |
| **ServiceMonitor** | Prometheus discovery (K8s) | CRD that tells Prometheus which services to scrape |

### Key Observability Concepts Practiced

- **The three pillars**: Metrics (Prometheus), Logs (Loki), Traces (Jaeger/Tempo)
- **PromQL**: Query language for metrics — rates, histograms, aggregations
- **LogQL**: Loki's query language — filter, parse JSON, extract fields
- **Distributed traces**: Track a request across multiple services with timing
- **Alerting pipeline**: Rule fires → Prometheus → AlertManager → notification channel
- **Grafana datasource chaining**: Link from a metric spike → filter logs for that time window → find the trace

---

## 5. Troubleshooting

### Prometheus not scraping ObserveApp

```bash
# Check if /metrics endpoint is accessible
curl http://localhost:8080/metrics

# Check Prometheus target health
# Prometheus UI → Status → Targets → look for "DOWN"
# Common causes: wrong port, wrong label selector, firewall

# Check prometheus.yml scrape config
docker compose exec prometheus cat /etc/prometheus/prometheus.yml
```

### No logs in Loki / Grafana

```bash
# Check Promtail is running
docker compose ps promtail

# Check Promtail config and targets
curl http://localhost:9080/targets  # Promtail's own status page

# Check Loki received data
curl http://localhost:3100/loki/api/v1/labels

# Check Promtail logs for errors
docker compose logs promtail
```

### No traces in Jaeger

```bash
# Verify ObserveApp is configured to send traces
docker compose exec observeapp env | grep OTEL

# Should have: OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317

# Check Jaeger received data
curl http://localhost:16686/api/services

# Check Jaeger logs
docker compose logs jaeger
```

### AlertManager not firing alerts

```bash
# Check alert rules are loaded correctly
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[]'

# Check if alert is in pending state (needs duration to fire)
# Prometheus UI → Alerts tab

# Check AlertManager config syntax
docker compose exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
```

### Grafana dashboard shows "No Data"

```bash
# Verify datasource is configured
# Grafana → Configuration → Data Sources → Prometheus → Test

# Check the time range in Grafana — set to last 1 hour
# Check the query in panel edit mode — make sure metric exists
curl http://localhost:9090/api/v1/label/__name__/values | jq '.' | grep http_requests
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-05-observability-stack/local/

# Stop all containers
docker compose down

# Full reset including Prometheus data, Loki logs, Grafana config
docker compose down -v
```

### Kubernetes

```bash
# Uninstall Helm releases
helm uninstall kube-prometheus-stack -n monitoring
helm uninstall loki -n monitoring
helm uninstall tempo -n monitoring
helm uninstall thanos -n monitoring

# Delete namespace (removes CRDs and all resources)
kubectl delete namespace monitoring

# If you want to remove the Prometheus Operator CRDs as well
kubectl delete crd prometheuses.monitoring.coreos.com
kubectl delete crd servicemonitors.monitoring.coreos.com
kubectl delete crd alertmanagers.monitoring.coreos.com
```
