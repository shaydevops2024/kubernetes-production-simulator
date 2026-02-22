# Project 02: Multi-Tenant SaaS Application Infrastructure

Build and operate a complete multi-tenant SaaS platform. You'll go from a single shared stack on Docker Compose all the way to a production Kubernetes setup with namespace isolation, RBAC, resource quotas, network policies, and tenant-specific databases.

---

## What You're Building

A SaaS platform where companies ("tenants") each get their own isolated environment:

```
┌────────────────────────────────────────────────────────────────────┐
│                    Admin Dashboard (nginx + HTML)                  │
│            Shows all tenants, their usage, and task counts         │
└──────────────┬─────────────────────┬──────────────────────────────┘
               │                     │
        /api/platform/*        /api/billing/*       /api/app/*
               │                     │                    │
        platform-api          billing-service        app-service
       (tenant CRUD)           (metering)           (task manager)
               │                     │                    │
       postgres-platform      postgres-billing       postgres-app
```

| Service | What it does |
|---------|-------------|
| **platform-api** | Create, suspend, and delete tenants. Stores plan limits (CPU, memory, pods) |
| **app-service** | The actual SaaS product — a task manager. Each tenant sees only their own tasks |
| **billing-service** | Records every API call per tenant. Shows usage and estimated cost |
| **admin-ui** | Admin dashboard showing all tenants, their resource limits, task counts, and usage |

---

## Folder Structure

```
project-02-multitenant-saas/
├── README.md           ← You are here
│
├── app/                ← Application source code (pre-built)
│   ├── README.md       ← Service overview, API contracts, env vars
│   ├── platform-api/   ← Tenant management API (FastAPI)
│   ├── app-service/    ← Multi-tenant task manager (FastAPI)
│   ├── billing-service/← Usage metering API (FastAPI)
│   └── admin-ui/       ← Admin dashboard (HTML/CSS/JS + nginx)
│
├── local/              ← Docker Compose — run everything locally
│   ├── README.md       ← Step-by-step local guide + DevOps tasks
│   ├── docker-compose.yml
│   └── nginx/
│       └── nginx.conf
│
└── main/               ← Production Kubernetes deployment
    └── README.md       ← What you'll build: namespaces, RBAC, quotas, network policies
```

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)
Read [app/README.md](./app/README.md). Understand what each service does, what APIs it exposes, and how tenant isolation works at the application level.

**Skills:** Reading architecture docs, understanding multi-tenancy, API contracts, header-based routing

### Phase 2 — Run Locally (`local/`)
Use Docker Compose to get the full stack running on your machine. All tenants share one app-service instance — isolation is enforced by the `X-Tenant-ID` header.

**Skills:** Docker Compose, service networking, environment variables, health checks, database exploration

### Phase 3 — Deploy to Kubernetes (`main/`)
Redesign the architecture for Kubernetes. Each tenant gets their own namespace, database, resource quotas, RBAC rules, and network policies.

**Skills:** Namespaces, RBAC, ResourceQuota, LimitRange, NetworkPolicy, StatefulSets, Ingress, Secrets

---

## The Core Learning: Two Types of Multi-Tenancy

This project is built around one key contrast:

### Application-Level Multi-Tenancy (local/)
One shared service, one shared database. Tenants are separated by a column in the database and a header in the API. Simple to run, hard to truly isolate.

```
tenant-alice-corp ─┐
                   ├─→ app-service → tasks (tenant_id = 'alice-corp')
tenant-bob-ind   ─┘             → tasks (tenant_id = 'bob-industries')
```

### Infrastructure-Level Multi-Tenancy (main/)
Each tenant is a Kubernetes namespace. They get their own pods, their own database, their own resource limits, and are blocked from reaching each other by network policy.

```
namespace: tenant-alice-corp   → app-service → postgres (alice's DB)
namespace: tenant-bob-ind      → app-service → postgres (bob's DB)
namespace: tenant-charlie-ltd  → app-service → postgres (charlie's DB)
```

---

## What the Admin Dashboard Looks Like

When you run `docker compose up --build` and open http://localhost:8090, you'll see:

```
┌────────────────────────────────────────────────────────────┐
│  SaaSPlatform Admin  ● All systems healthy  [+ New Tenant] │
├────────────────────────────────────────────────────────────┤
│  3 Tenants │ 2 Active │ 1 Suspended │ 158 API Calls Today  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ ENTERPRISE  │  │ PRO         │  │ STARTER     │       │
│  │ ● Active    │  │ ● Active    │  │ ● Suspended │       │
│  │ Alice Corp  │  │ Bob Ind.    │  │ Charlie Ltd │       │
│  │ alice-corp  │  │ bob-ind.    │  │ charlie-ltd │       │
│  │ 100+ calls  │  │ 50+ calls   │  │ 10 calls    │       │
│  │ [Tasks][⏸] │  │ [Tasks][⏸] │  │ [Tasks][▶] │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└────────────────────────────────────────────────────────────┘
```

Clicking "View Tasks" on any tenant opens a task panel showing that tenant's tasks only — demonstrating the isolation in action.

---

## Prerequisites

- Docker and Docker Compose (for Phase 2)
- kubectl and a Kubernetes cluster (for Phase 3)
- Basic Python knowledge (to read and understand the services)

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand the platform**

Then follow: `app/` → `local/` → `main/`
