# Project 07: Serverless Functions Platform on Kubernetes

Build your own Functions-as-a-Service (FaaS) platform from scratch. You'll deploy OpenFaaS on Kubernetes, configure auto-scaling from zero, set up HTTP/Cron/Kafka triggers, and manage everything with ArgoCD — all while watching a live dashboard show your functions running in real time.

---

## What You're Building

A fully operational serverless platform — the same concepts behind AWS Lambda, Google Cloud Functions, and Azure Functions, but running on your own Kubernetes cluster.

```
┌──────────────────────────────────────────────────────────────┐
│                    Ingress (NGINX)                            │
└──────┬─────────────────────────────────┬──────────────────────┘
       │ /api/*                          │ /*
       ▼                                 ▼
function-service                      frontend (nginx)
  - function registry                   - dashboard UI
  - invocation router                   - marketplace
  - stats                               - scaling demo
       │                                - cron simulator
       │ POST /run/{name}
       ▼
function-runner
  - hello-world
  - fibonacci (CPU-heavy, scaling demo)
  - text-processor
  - image-info
  - weather-report (cron trigger)
       │
       ▼ (Phase 3C+)
OpenFaaS Gateway ← Prometheus ← AlertManager ← Auto-scaling
KEDA HTTP Add-on ← Scale-to-zero ← Cold start demos
```

---

## Folder Structure

```
project-07-serverless-platform/
├── README.md          ← You are here
├── app/               ← Application source code (pre-built)
│   ├── README.md      ← API contracts, env vars, running locally
│   ├── function-service/   ← Registry & invocation proxy
│   ├── function-runner/    ← Function executor
│   └── frontend/           ← Dashboard UI (nginx)
├── local/             ← Docker Compose for local development
│   ├── README.md      ← Step-by-step local guide + DevOps tasks
│   └── docker-compose.yml
└── main/              ← Production Kubernetes deployment
    ├── README.md      ← Full K8s guide: Core → HPA → OpenFaaS → KEDA → ArgoCD
    └── solution/      ← Completed manifests to compare with your work
        ├── namespace.yaml
        ├── configmaps/
        ├── deployments/
        ├── services/
        ├── ingress/
        ├── hpa/
        ├── keda/
        ├── functions/    ← OpenFaaS Function CRDs
        ├── helm/         ← OpenFaaS install script + values
        └── argocd/
```

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)

Read the app README. Understand what each service does and how they communicate. You don't write code, but you need to know what you're deploying.

**Skills:** Reading architecture docs, understanding service-to-service communication, API contracts

### Phase 2 — Run It Locally (`local/`)

Bring the full stack up with Docker Compose. Inspect the network, trigger functions via curl, scale the runner manually, and simulate a cold start.

**Skills:** Docker Compose, service networking, health checks, manual scaling, environment variables

### Phase 3 — Deploy to Kubernetes (`main/`)

Write Kubernetes manifests for every service. Deploy to a real cluster. Then progressively add more advanced features:

| Phase | What you add | New skills |
|-------|-------------|------------|
| 3A | Deployments, Services, ConfigMap, Ingress | Core K8s objects |
| 3B | HPA (CPU-based auto-scaling) | autoscaling/v2, metrics-server |
| 3C | OpenFaaS (proper FaaS platform) | Helm, CRDs, faas-cli, scale-to-zero |
| 3D | KEDA (event-driven scaling) | KEDA, HTTP ScaledObject, scale-to-zero |
| 3E | Cron triggers | CronJob, scheduled invocations |
| 3F | GitOps with ArgoCD | ArgoCD, Application CRD, auto-sync |

---

## What the Final Architecture Looks Like

```
Internet
    │
    ▼
[NGINX Ingress Controller]
    │
    ├── /api/*  → [function-service]  ──→ [function-runner ×N]
    │               (registry)              (executor, HPA: 2-10)
    │                                           ↑
    │                                    [OpenFaaS Gateway]
    │                                    [KEDA HTTP Scaler]
    │                                    [Prometheus metrics]
    │
    └── /*      → [frontend (nginx)]
                   (dashboard UI)

[ArgoCD]  ← watches Git → auto-syncs all manifests
[CronJob] ← fires weather-report every hour
```

---

## Available Functions

| Function | Trigger | What it does |
|----------|---------|-------------|
| `hello-world` | HTTP | Returns a greeting — baseline function |
| `fibonacci` | HTTP | Computes Fibonacci(N) — CPU-intensive, scaling demo |
| `text-processor` | HTTP | Analyzes text: word count, sentiment, reading time |
| `image-info` | HTTP | Returns metadata for an image URL |
| `weather-report` | HTTP + Cron | Mock weather report, 3-day forecast |

---

## Prerequisites

- Docker and Docker Compose installed
- `kubectl` installed and configured
- A Kubernetes cluster (Kind, Minikube, or cloud)
- Helm 3 installed
- Basic understanding of containers and networking

---

## Start Here

**→ [app/README.md](./app/README.md)** — understand the services

Then follow: `app/` → `local/` → `main/`
