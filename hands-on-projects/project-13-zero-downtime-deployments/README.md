# Project 13 — Zero-Downtime Deployment Platform

> **Your goal:** Deploy a real application to Kubernetes using blue-green and canary strategies,
> with Prometheus-driven automated rollback — no human intervention required when things go wrong.

## The problem this solves

Every team eventually faces this question: **"How do we ship a new version without users noticing?"**

A naive approach — kill v1, start v2 — causes downtime. Real production systems use strategies
that keep traffic flowing while the new version starts up, is validated by real metrics, and
only fully takes over when it has proven itself.

This project teaches you three strategies, why they exist, and when to use each one:

| Strategy     | Risk     | Rollback speed | Resource overhead | Best for                          |
|--------------|----------|----------------|-------------------|-----------------------------------|
| Rolling      | Medium   | Slow           | Minimal           | Stateless apps, low risk changes  |
| Blue-Green   | Low      | Instant        | 2× during deploy  | High-stakes releases              |
| Canary       | Very low | Fast           | Small extra pods  | Data-sensitive or risky changes   |

The standout feature: **Argo Rollouts + Prometheus = automatic rollback**. If your canary's
error rate exceeds 5 % for 60 seconds, the system rolls back without you touching anything.

---

## Folder structure

```
project-13-zero-downtime-deployments/
├── app/           → The sample application (pre-built — your job is to deploy it)
│                    See app/README.md for API docs and endpoints
│
├── local/         → Run the full stack locally with Docker Compose
│                    Includes nginx traffic splitter + Prometheus + Grafana
│                    See local/README.md for exercises
│
├── main/          → Deploy to Kubernetes step-by-step
│                    Covers Argo Rollouts, AnalysisTemplates, and CI/CD
│                    See main/README.md for the complete guide
│
└── solution/      → Reference implementation — all files are here
    ├── k8s/           Kubernetes manifests (namespace, app, rollouts, monitoring, MetalLB)
    ├── helm/          Helm values for Argo Rollouts and kube-prometheus-stack
    ├── scripts/       Helper scripts (setup, trigger rollout, simulate traffic)
    └── github-actions/ CI/CD pipeline definition
```

**How to use this project:**

1. Start with **`app/`** — read the code, understand what you're deploying
2. Run locally with **`local/`** — see canary and blue-green with nginx weights
3. Deploy to Kubernetes with **`main/`** — use the solution only when stuck
4. The **`solution/`** folder is your reference, not your starting point

---

## What you'll build

```
                        nginx-ingress
                             │
              ┌──────────────┴──────────────┐
         stable svc (95%)             canary svc (5%)
              │                             │
         v1 pods (blue)              v2 pods (green)
                                           │
                                    AnalysisRun
                                    (every 30 s)
                                           │
                             error rate > 5%? → rollback
                             error rate < 5%? → advance to 25%
```

---

## Local access points (Docker Compose)

| Service      | URL                       | Credentials   |
|--------------|---------------------------|---------------|
| App (main)   | http://localhost:4545     | —             |
| App v1 direct| http://localhost:4551     | —             |
| App v2 direct| http://localhost:4552     | —             |
| Grafana      | http://localhost:4446     | admin / admin |
| Prometheus   | http://localhost:4447     | —             |

---

## Prerequisites

- Docker + Docker Compose (for local exercises)
- `kubectl` 1.28+
- `helm` 3.x
- `kind` (for local Kubernetes cluster)
- Basic Kubernetes knowledge: Deployments, Services, Ingress, Pods

---

## Start here

**Option A — Local only (Docker Compose)**

```bash
cd local/
docker compose up --build -d
# Open http://localhost:4545
```

Then follow the exercises in [local/README.md](./local/README.md).

**Option B — Full Kubernetes**

```bash
# Create cluster, install tools, build image
bash solution/scripts/setup.sh

# Apply base resources
kubectl apply -f solution/k8s/namespace.yaml
kubectl apply -f solution/k8s/app/
kubectl apply -f solution/k8s/argo-rollouts/

# Watch the rollout
kubectl argo rollouts get rollout deploy-insight -n zero-downtime -w
```

Then follow [main/README.md](./main/README.md) for the full step-by-step guide.

---

## Key concepts you'll master

- **Argo Rollouts** — Kubernetes-native progressive delivery controller
- **AnalysisTemplate** — metric-driven promotion gates with Prometheus queries
- **nginx Ingress canary annotations** — traffic splitting at the ingress layer
- **MetalLB** — bare-metal LoadBalancer for local clusters
- **kube-prometheus-stack** — production-grade monitoring on Kubernetes
- **GitHub Actions** — automated CI/CD that triggers Argo Rollouts
