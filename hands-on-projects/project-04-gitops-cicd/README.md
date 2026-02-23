# Project 04: Full GitOps CI/CD Pipeline with Progressive Delivery

Build a complete end-to-end GitOps pipeline — from code commit to production canary deployment. You'll wire up GitHub Actions for CI, ArgoCD for GitOps sync, and Flagger for progressive delivery with automated rollback.

The application you deploy is the **DevOps Projects Hub**: a live dashboard listing all 16 hands-on projects in this series. It displays its own version number prominently — which means when you do a canary deployment, you can literally watch traffic shifting between v1 and v2 by refreshing the browser.

---

## What You're Building

```
Developer pushes code
        │
        ▼
[GitHub Actions — CI Pipeline]
  ├── Run tests
  ├── Build Docker image
  ├── Scan image (Trivy)
  └── Push image + update GitOps repo
        │
        ▼
[ArgoCD — GitOps Sync]
  └── Detects manifest change → syncs to cluster
        │
        ▼
[Flagger — Progressive Delivery]
  ├── Canary: 10% → 30% → 50% → 100% traffic
  ├── Automated analysis (success rate, latency)
  └── Auto-rollback on failure
        │
        ▼
[DevOps Projects Hub — Live UI]
  └── Users see v1 or v2 depending on traffic split
```

| Component | Role |
|-----------|------|
| **GitHub Actions** | CI pipeline — test, build, scan, push |
| **ArgoCD** | GitOps operator — watches Git, syncs cluster |
| **Flagger** | Progressive delivery — canary, analysis, rollback |
| **Istio / NGINX Ingress** | Traffic splitting between canary and stable |
| **Prometheus** | Metrics source for Flagger analysis |
| **DevOps Projects Hub** | The app being deployed — your live test subject |

---

## Folder Structure

```
project-04-gitops-cicd/
├── README.md          ← You are here
├── app/               ← Application source code (pre-built)
│   ├── README.md      ← API docs, env vars, how to run locally
│   ├── main.py        ← FastAPI backend + static file server
│   ├── Dockerfile     ← Single-stage, production-ready
│   ├── requirements.txt
│   └── static/        ← Frontend: Projects Hub UI
│       ├── index.html
│       ├── style.css
│       └── app.js
├── local/             ← Docker Compose to simulate canary locally
│   ├── README.md      ← Step-by-step local setup + DevOps tasks
│   ├── docker-compose.yml
│   └── nginx/
│       └── nginx.conf ← Load balancer simulating canary split
└── main/              ← Production GitOps deployment (what you build)
    └── README.md      ← Phase-by-phase build guide
```

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)
Read the app README. Understand what the Projects Hub does, what endpoints it exposes, and how `APP_VERSION` controls which version users see.

**Skills:** Reading architecture docs, understanding 12-factor app design, environment-based configuration

### Phase 2 — Run It Locally (`local/`)
Use Docker Compose to run **two versions simultaneously** with an nginx load balancer splitting traffic between them. This simulates what Flagger does in Kubernetes — before you ever touch a cluster.

**Skills:** Docker Compose, nginx upstream load balancing, canary traffic simulation, health checks

### Phase 3 — Deploy to Kubernetes (`main/`)
Write the Kubernetes Deployment, Service, and Ingress for the app. Get it running on your cluster.

**Skills:** Deployments, Services, Ingress, ConfigMaps, namespaces, resource limits

### Phase 4 — Add ArgoCD GitOps
Install ArgoCD, point it at your manifest repo, and let Git become the source of truth for your cluster state. No more `kubectl apply` by hand.

**Skills:** ArgoCD Application, App of Apps pattern, sync policies, Git-driven deployments

### Phase 5 — Wire Up GitHub Actions CI
Build a pipeline that runs tests, builds the Docker image, scans it with Trivy, pushes to a registry, and updates the GitOps manifest repo to trigger ArgoCD.

**Skills:** GitHub Actions workflows, Docker build/push, Trivy image scanning, automated GitOps promotion

### Phase 6 — Progressive Delivery with Flagger
Install Flagger, configure a Canary resource, and watch it automatically shift traffic from v1 to v2 — then trigger a failure and watch the automated rollback.

**Skills:** Flagger Canary CRD, traffic analysis, success-rate thresholds, automated rollback, Prometheus integration

---

## What the Final Architecture Looks Like

```
GitHub Repo (app code)
        │  git push
        ▼
[GitHub Actions]
  test → build → scan → push → update gitops repo
        │
        ▼
GitHub Repo (gitops manifests)  ←── ArgoCD watches this
        │
        ▼
[ArgoCD]  (running in cluster)
  detects drift → applies manifests
        │
        ▼
[Kubernetes Cluster]
  ┌─────────────────────────────────────────┐
  │  namespace: gitops-cicd                 │
  │                                         │
  │  [Flagger Canary Controller]            │
  │       │                                 │
  │       ├── projects-hub (stable/v1)      │ ← 90% traffic
  │       └── projects-hub-canary (v2)      │ ← 10% → 100%
  │                                         │
  │  [Ingress / Istio Gateway]              │
  │  [Prometheus]  ← metrics for analysis   │
  └─────────────────────────────────────────┘
        │
        ▼
Browser: http://projects-hub.example.com
  (refresh → sometimes v1, sometimes v2 during canary)
```

---

## Prerequisites

- Docker and Docker Compose (for Phase 2)
- `kubectl` and a Kubernetes cluster (for Phase 3+)
- Helm (for ArgoCD, Flagger, Prometheus installation)
- A GitHub account with a repo for app code and a repo for GitOps manifests
- A container registry (Docker Hub, GHCR, or ECR)

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand the application**

Then follow: `app/` → `local/` → `main/`
