# Project 14: Self-Service Developer Platform (Internal PaaS)

Build a complete Internal Developer Platform (IDP) from scratch — the same kind of platform that large engineering teams use to let developers self-serve infrastructure without waiting on the ops team.

By the end you'll have a fully working platform on a local Kind cluster where teams can provision namespaces, deploy services, inject secrets, provision databases, and track costs — all from a self-service portal.

---

## What You're Building

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Developer Portal (Backstage)                      │
│             Self-service UI — teams manage their own infra           │
└──────┬───────────┬──────────────┬──────────────┬────────────────────┘
       │           │              │              │
       ▼           ▼              ▼              ▼
 [Gitea]     [Woodpecker]    [Harbor]      [ArgoCD]
 Git hosting  CI pipelines   Image registry  GitOps sync
       │           │              │              │
       └───────────┴──────────────┴──────────────┘
                           │
             ┌─────────────▼──────────────┐
             │    Kubernetes (Kind Cluster) │
             │   1 control-plane + 3 nodes  │
             │                              │
             │  ┌──────────┐ ┌──────────┐   │
             │  │ Team A ns│ │ Team B ns│   │  ← Crossplane provisions
             │  │ RBAC     │ │ RBAC     │   │    namespace + RBAC + quota
             │  │ Quota    │ │ Quota    │   │
             │  └──────────┘ └──────────┘   │
             │                              │
             │  ┌──────────┐ ┌──────────┐   │
             │  │  Vault   │ │CloudNaPG │   │  ← Secrets & databases
             │  │ (HA mode)│ │(Postgres)│   │    injected into pods
             │  └──────────┘ └──────────┘   │
             │                              │
             │  ┌──────────┐ ┌──────────┐   │
             │  │ Kyverno  │ │OpenCost  │   │  ← Policies enforced
             │  │ Policies │ │Per-team  │   │    cost tracked per team
             │  └──────────┘ └──────────┘   │
             │                              │
             │  ┌──────────────────────┐    │
             │  │ Prometheus + Grafana │    │  ← Observability
             │  └──────────────────────┘    │
             └──────────────────────────────┘
```

---

## Folder Structure

```
project-14-internal-paas/
├── README.md          ← You are here
├── app/               ← The developer portal application (pre-built)
│   ├── README.md      ← How the portal app works, API reference
│   └── portal/        ← FastAPI + HTML/CSS/JS portal UI
├── local/             ← Docker Compose to run the portal locally
│   ├── README.md      ← Step-by-step local setup guide
│   └── docker-compose.yml
└── main/              ← Production deployment on Kind
    ├── README.md      ← Phase-by-phase K8s deployment guide
    └── solution/      ← Complete reference implementation
        ├── phase-1-cluster/          ← Kind cluster + ingress + MetalLB
        ├── phase-2-registry-gitea/   ← Harbor + Gitea + Woodpecker CI
        ├── phase-3-namespace-rbac/   ← Crossplane + RBAC
        ├── phase-4-vault/            ← HashiCorp Vault
        ├── phase-5-database/         ← CloudNativePG
        ├── phase-6-backstage/        ← Backstage portal
        ├── phase-7-observability/    ← Prometheus + Grafana + OpenCost
        ├── phase-8-policies/         ← Kyverno policies
        └── argocd/                   ← GitOps with ArgoCD
```

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)
The portal app is a FastAPI web application that gives developers a self-service interface. You don't write it — you run, containerize, and deploy it.

→ Read [app/README.md](./app/README.md)

### Phase 2 — Run It Locally (`local/`)
Use Docker Compose to run the portal app locally with mock data. Understand what the platform looks like from a developer's perspective before you build the real infrastructure.

→ Follow [local/README.md](./local/README.md)

### Phase 3 — Build the Full Platform (`main/`)
Build the production platform phase by phase. Each phase delivers a real working system you verify before moving on.

→ Follow [main/README.md](./main/README.md)

---

## Tools You'll Use

| Tool | Why |
|------|-----|
| **Kind** | Local Kubernetes cluster (multi-node) |
| **Harbor** | Self-hosted container registry |
| **Gitea** | Self-hosted Git hosting |
| **Woodpecker CI** | CI/CD pipelines connected to Gitea |
| **ArgoCD** | GitOps — syncs cluster state from Git |
| **Crossplane** | Provisions namespaces + RBAC as Kubernetes resources |
| **HashiCorp Vault** | Secrets management + dynamic credentials |
| **CloudNativePG** | PostgreSQL provisioning on Kubernetes |
| **Backstage** | Developer portal — the "front door" to your platform |
| **Kyverno** | Policy enforcement (require labels, restrict images, etc.) |
| **OpenCost** | Per-team cost tracking |
| **kube-prometheus-stack** | Prometheus + Grafana + AlertManager |
| **MetalLB** | LoadBalancer simulation on bare metal |
| **ingress-nginx** | Ingress controller |

---

## Prerequisites

- Docker & Docker Compose
- `kubectl` installed
- `kind` CLI installed
- `helm` 3.x installed
- At least 8 GB free RAM (the full stack is resource-heavy)
- Basic Kubernetes knowledge (Deployments, Services, namespaces)

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand what you're deploying**

Then follow: `app/` → `local/` → `main/`
