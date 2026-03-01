# Project 10: Zero-Downtime Blue-Green Deployment System

Deploy the same application to two identical environments — blue and green. Only one is live at a time. Traffic switches in milliseconds. Rollbacks are instant because the old environment never stopped running.

This is how production deployments work at companies that can't afford downtime.

---

## What You're Building

```
                    Users
                      │
                      ▼
          ┌─────────────────────┐
          │  nginx / K8s Ingress │   ← single entry point
          └──────────┬──────────┘
                     │
              (service selector)
                  ┌──┴──┐
                  │     │
              ┌───┴──┐ ┌┴────┐
              │ BLUE  │ │GREEN│    ← both running simultaneously
              │  v1   │ │ v2  │
              └───────┘ └─────┘
                  │         │
                  └────┬────┘
                       │
               ┌───────┴────────┐
               │  PostgreSQL DB  │   ← shared database
               └────────────────┘
```

Only one environment receives live traffic at a time. The other stays on standby for instant rollback.

---

## Folder Structure

```
project-10-blue-green-deployment/
├── README.md              ← You are here
├── app/                   ← Application source code (pre-built: DeployTrack)
│   ├── README.md          ← App overview, API, environment variables
│   ├── main.py            ← FastAPI app — changes color/version via env vars
│   ├── Dockerfile
│   └── requirements.txt
├── local/                 ← Docker Compose simulation
│   ├── README.md          ← Step-by-step local blue-green guide
│   ├── docker-compose.yml ← Blue + Green + nginx + PostgreSQL
│   └── nginx/
│       └── nginx.conf     ← Traffic router (edit to switch blue ↔ green)
├── main/                  ← Production Kubernetes deployment
│   └── README.md          ← Full K8s blue-green guide (you build this)
└── solution/              ← Complete reference solution
    ├── k8s/               ← Ready-made Kubernetes manifests
    │   ├── namespace/
    │   │   ├── namespace.yaml
    │   │   └── postgres.yaml
    │   ├── configmaps/
    │   │   └── app-config.yaml
    │   ├── deployments/
    │   │   ├── deployment-blue.yaml
    │   │   ├── deployment-green.yaml
    │   │   └── job-db-migrate.yaml
    │   ├── services/
    │   │   └── services.yaml        ← blue + green + live (3 services)
    │   └── ingress/
    │       └── ingress.yaml
    ├── gitlab-ci/
    │   └── .gitlab-ci.yml           ← Full automated pipeline
    └── scripts/
        ├── health-check.sh          ← Validates env before switch
        ├── smoke-tests.sh           ← Tests new version before + after switch
        ├── switch-traffic.sh        ← Patches service selector
        └── rollback.sh              ← Instant rollback script
```

**→ Go to [app/README.md](./app/README.md) to understand what you're deploying.**

Then follow: `app/` → `local/` → `main/`

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)

Read the app README. Understand:
- Why the same Docker image runs as both blue and green (env vars only)
- How `/health` enables automated health checks before traffic switching
- What "backward-compatible database schema" means and why it's non-negotiable

**Skills:** App architecture, environment variable configuration, health probes

### Phase 2 — Run It Locally (`local/`)

Run both blue and green side by side with Docker Compose:
- Blue on http://localhost:4456 (direct access, v1 theme)
- Green on http://localhost:4457 (direct access, v2 theme)
- **Live** on http://localhost:4455 (nginx routes to blue by default)

Manually switch traffic by editing nginx.conf and reloading. Observe zero downtime.

**Skills:** Docker Compose, nginx upstreams, zero-downtime nginx reload, shared databases

### Phase 3 — Deploy to Kubernetes (`main/`)

Write K8s manifests for the full blue-green pattern:
- Deploy both blue and green environments
- Create 3 services: `service-blue`, `service-green`, `service-live`
- Wire the Ingress to `service-live`
- Write health check and smoke test scripts
- Switch traffic by patching the `service-live` selector (one kubectl command)

**Skills:** Deployments, Services, Ingress, `kubectl patch`, readinessProbes, Jobs

### Phase 4 — Database Migration Handling

Add a Kubernetes Job that runs schema migrations before switching traffic:
- Migrations are backward-compatible (blue v1 still works with new schema)
- Job runs and exits before the traffic switch
- If the migration fails, the pipeline stops and blue stays live

**Skills:** Kubernetes Jobs, database migration safety, rollback triggers

### Phase 5 — GitLab CI Automation

Build the full pipeline that automates every step:
1. Build new Docker image (v2)
2. Deploy to green (0 → 3 replicas)
3. Run health check against green
4. Run smoke tests against green (before going live)
5. Run database migration Job
6. Switch `service-live` selector from blue → green
7. Run post-switch smoke test through the Ingress
8. Scale blue to 0 replicas (rollback still possible in seconds)

**Auto-rollback:** Any pipeline stage failure triggers `rollback.sh` automatically.

**Skills:** GitLab CI stages, artifacts, `kubectl set image`, automated rollback

---

## The Three Core Scripts

| Script | When to run | What it does |
|--------|-------------|--------------|
| `health-check.sh` | After deploying green | Checks pods ready + /health endpoint |
| `smoke-tests.sh` | Before AND after switching | 5 API tests: health, version, list, write, homepage |
| `switch-traffic.sh` | After all checks pass | Patches `service-live` selector to new color |
| `rollback.sh` | Emergency | Switches back to previous color in < 1 second |

---

## What the Final Architecture Looks Like

```
GitLab CI
    │
    1. Build image → push to registry
    │
    2. kubectl set image deploytrack-green → new image
    3. kubectl scale deployment deploytrack-green --replicas=3
    4. kubectl rollout status (wait for ready)
    │
    5. health-check.sh green → all pods healthy?
    6. Run migration Job (backward-compatible)
    7. smoke-tests.sh green (via port-forward, not yet live)
    │
    8. switch-traffic.sh green
       └─ kubectl patch service deploytrack-live
              selector.color: blue → green        (INSTANT SWITCH)
    │
    9. smoke-tests.sh live (via Ingress)
    │
    10. kubectl scale deployment deploytrack-blue --replicas=0

    ROLLBACK (any step fails):
       └─ rollback.sh → switch selector back to blue (< 1 second)
```

---

## Prerequisites

- Docker & Docker Compose installed (Phase 2)
- kubectl configured with a Kubernetes cluster (Phase 3+)
- nginx Ingress Controller installed on the cluster
- GitLab account + repository (Phase 5)
- Basic understanding of Kubernetes Deployments and Services

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand the application**

Then follow: `app/` → `local/` → `main/`

Reference solution (for when you're stuck): `solution/`
