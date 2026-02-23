# Project 05: Complete Observability Stack

Build a production-grade observability platform from scratch — metrics, logs, traces, dashboards, and alerting all working together.

---

## What You're Building

You'll deploy a real observability stack around a pre-built web application. By the end you'll have:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ObserveApp (UI)                              │
│              Your pre-instrumented SaaS analytics app                │
└──────┬──────────────────────────────────────────────────────────────┘
       │ generates
       ├── Prometheus metrics  ──→ Prometheus  ──→ [Thanos on K8s]
       ├── JSON logs           ──→ Promtail   ──→ Loki
       └── OTLP traces         ──→ Jaeger     ──→ [Tempo on K8s]
                                                        │
                                               Grafana ◄┘ (unified UI)
                                                        │
                                              AlertManager
                                         (PagerDuty on K8s)
```

---

## Folder Structure

```
project-05-observability-stack/
├── README.md          ← You are here
├── app/               ← Pre-built application (Python/FastAPI)
│   ├── README.md      ← How the app works and what metrics it exposes
│   ├── main.py        ← Application with Prometheus + OTel + JSON logs
│   ├── requirements.txt
│   ├── Dockerfile
│   └── static/        ← Live dashboard UI (served by the app itself)
├── local/             ← Full observability stack via Docker Compose
│   ├── README.md      ← Step-by-step local setup guide
│   ├── docker-compose.yml
│   ├── prometheus/    ← Prometheus config + alerting rules
│   ├── grafana/       ← Datasource provisioning + pre-built dashboard
│   ├── loki/          ← Loki log aggregation config
│   ├── promtail/      ← Log collector config (Docker → Loki)
│   └── alertmanager/  ← Alert routing config
└── main/              ← Production Kubernetes deployment
    ├── README.md      ← What you'll build in the K8s phase
    └── solution/      ← Complete K8s solution (reference)
        ├── README.md
        ├── deploy.sh  ← One-script deploy
        ├── app/       ← App deployment + ServiceMonitor + Ingress
        ├── kube-prometheus-stack/  ← Helm values for Prometheus+Grafana
        ├── loki/      ← Helm values for Loki
        ├── tempo/     ← Helm values for Tempo
        ├── jaeger/    ← Helm values for Jaeger
        ├── thanos/    ← Helm values for long-term metrics storage
        ├── alertmanager/   ← AlertManager config + PagerDuty secret
        ├── grafana/        ← Dashboard ConfigMaps
        └── prometheusrules/  ← SLO alerting rules
```

---

## Your DevOps Journey

### Phase 1 — Understand the App (app/)

Read [app/README.md](./app/README.md) to understand what the app does and what observability signals it already emits. You don't write any application code in this project.

**Skills:** Reading instrumentation docs, understanding Prometheus metrics, structured logging, OpenTelemetry

### Phase 2 — Run the Full Stack Locally (local/)

Use Docker Compose to run the app alongside Prometheus, Grafana, Loki, Promtail, Jaeger, and AlertManager. Explore each tool, trigger scenarios using the app's dashboard, and watch the signals appear in Grafana.

**Skills:** Docker Compose, service networking, volume mounts, observability tool configuration

→ See [local/README.md](./local/README.md) for the full guide

### Phase 3 — Deploy to Kubernetes (main/)

Deploy the application and the entire observability stack to a Kubernetes cluster. You'll write the app manifests yourself (Deployment, Service, Ingress, ServiceMonitor), then install the monitoring tools via Helm.

**Skills:** K8s deployments, Helm, ServiceMonitor, PrometheusRule, Ingress, secrets management

→ See [main/README.md](./main/README.md) for the full guide

### Phase 4 — Configure Alerting

Write PrometheusRules for SLO-based alerting (availability, error budget burn rate, latency). Connect AlertManager to a notification channel (Slack or PagerDuty).

**Skills:** PromQL, SLO definitions, error budgets, AlertManager routing, inhibition rules

### Phase 5 — Add Thanos for Long-Term Storage

Install Thanos sidecar next to Prometheus to ship metrics to object storage (S3/MinIO). Configure Grafana to query Thanos instead of Prometheus directly for historical data.

**Skills:** Thanos architecture, object storage, sidecar pattern, multi-cluster queries

---

## Key Tools

| Tool | Purpose | Local Port |
|------|---------|------------|
| ObserveApp | Pre-instrumented demo app with live dashboard | 8000 |
| Prometheus | Metrics scraping and storage | 9090 |
| Grafana | Unified dashboards for metrics, logs, traces | 3000 |
| Loki | Log aggregation (like Prometheus, but for logs) | 3100 |
| Promtail | Collects Docker logs and ships them to Loki | — |
| Jaeger | Distributed tracing UI | 16686 |
| AlertManager | Alert routing and deduplication | 9093 |
| Thanos | Long-term metrics storage (K8s only) | — |
| Tempo | Trace backend (K8s only) | — |

---

## Prerequisites

- Docker and Docker Compose (for Phase 2)
- kubectl and a Kubernetes cluster (for Phase 3+)
- Helm v3 (for Phase 3+)
- Basic understanding of metrics, logs, and traces

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand what you're observing**

Then follow: `app/` → `local/` → `main/`
