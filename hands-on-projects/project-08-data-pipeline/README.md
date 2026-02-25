# Project 08: Real-Time Data Pipeline on Kubernetes

Build and operate a production-grade streaming data pipeline. The pipeline ingests events via **Kafka** (Strimzi operator), processes them with **Apache Spark** (Spark operator), stores results in **PostgreSQL/TimescaleDB**, and exposes live metrics through a **web dashboard** — all on Kubernetes.

You don't write application code. Everything is pre-built. Your job is the DevOps: containerizing, deploying, wiring, scaling, securing, and observing.

---

## What You're Building

```
┌──────────────────────────────────────────────────────────────────┐
│                     Data Pipeline System                          │
│                                                                   │
│  [Producer] ──Kafka Topic──▶ [Spark Job] ──▶ [TimescaleDB]       │
│      │                           │                │               │
│      │                      aggregations      time-series         │
│      │                                            │               │
│      └──────────────────── [Dashboard UI] ◀───────┘               │
│                              (live charts)                        │
└──────────────────────────────────────────────────────────────────┘
```

| Component | What It Does |
|-----------|-------------|
| **Pipeline Producer** | Generates simulated IoT sensor events → publishes to Kafka |
| **Pipeline Processor** | Spark Structured Streaming job → consumes Kafka, aggregates, writes to DB |
| **Dashboard UI** | Live web UI showing real-time metrics, pipeline stats, lag charts |
| **Kafka (Strimzi)** | Message broker — decouples producer from processor |
| **TimescaleDB** | PostgreSQL extension for time-series data |

---

## Folder Structure

```
project-08-data-pipeline/
├── README.md              ← You are here
├── app/                   ← Application source code (pre-built, read-only)
│   ├── README.md          ← Understand what each component does
│   ├── pipeline-producer/ ← Python Kafka producer (IoT event simulator)
│   └── pipeline-processor/← PySpark structured streaming job
│   └── dashboard-ui/      ← Simple HTML/JS live dashboard
├── local/                 ← Docker Compose for local development
│   ├── README.md          ← Run the full stack locally
│   └── docker-compose.yml
└── main/                  ← Your DevOps journey guide
    └── README.md          ← Phase-by-phase instructions (your work starts here)
```

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)
Read the app README. Understand what the producer publishes, what Spark processes, and what the dashboard shows.

**Skills:** Reading architecture docs, Kafka concepts, Spark Streaming concepts

### Phase 2 — Run It Locally (`local/`)
Docker Compose brings up Kafka (KRaft mode, no ZooKeeper), Spark, TimescaleDB, and the dashboard.
See the live data flow on your machine before touching Kubernetes.

**Skills:** Docker Compose, Kafka CLI, Spark Submit, port-forwarding

### Phase 3 — Containerize & First K8s Deploy (`main/` Phase 1–2)
Strimzi operator manages Kafka. Spark operator manages Spark jobs. Write the manifests, deploy.

**Skills:** Strimzi CRDs, SparkApplication CRD, Helm, operator pattern

### Phase 4 — GitOps + CI/CD (`main/` Phase 3)
GitLab CI builds and scans images. ArgoCD syncs the cluster. No manual kubectl applies allowed.

**Skills:** GitLab CI pipelines, Trivy image scanning, ArgoCD Applications

### Phase 5 — Observability (`main/` Phase 4)
Prometheus scrapes Kafka lag + Spark metrics. Grafana dashboards. Loki for logs. Alertmanager for lag alerts.

**Skills:** Prometheus, Grafana, Loki, Tempo, AlertManager, PromQL

### Phase 6 — Security (`main/` Phase 5)
Vault stores DB credentials. Trivy scans images in CI. mTLS between services.

**Skills:** Vault Agent Injector, Kubernetes auth, secret rotation

### Phase 7 — Chaos Engineering (`main/` Phase 6)
Kill Kafka brokers, crash Spark executors, and verify the pipeline self-heals.

**Skills:** Chaos Mesh, LitmusChaos, resilience testing

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand the application**

Then follow: `app/` → `local/` → `main/`
