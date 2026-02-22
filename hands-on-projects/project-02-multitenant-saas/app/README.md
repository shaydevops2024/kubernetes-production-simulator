# App — Multi-Tenant SaaS Services

This folder contains the source code for all services in the SaaS platform. Everything is pre-built — your job as a DevOps engineer is to **containerize, run, and deploy** it, not to write application logic.

---

## Services Overview

| Service | Port | Language | Database | Role |
|---------|------|----------|----------|------|
| **platform-api** | 8010 | Python/FastAPI | PostgreSQL | Tenant management — create, suspend, delete tenants |
| **app-service** | 8011 | Python/FastAPI | PostgreSQL | The actual SaaS app (task manager) used by tenants |
| **billing-service** | 8012 | Python/FastAPI | PostgreSQL | Records API calls, calculates costs per tenant |
| **admin-ui** | 80 | HTML/CSS/JS + nginx | — | Admin dashboard — visualises everything above |

---

## The Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Admin Dashboard (UI)                   │
│   Shows tenants, usage stats, tasks, create/suspend UI   │
└──────┬──────────────────┬────────────────────────────────┘
       │ /api/platform/*  │ /api/billing/*    │ /api/app/*
       ▼                  ▼                   ▼
 platform-api        billing-service       app-service
 (tenant CRUD)       (metering)            (task manager)
       │                  │                   │
 postgres-platform   postgres-billing    postgres-app
```

---

## The Core Concept: Two Modes of Tenant Isolation

This is the most important learning in this project:

### Mode 1 — Local (Docker Compose)
**Application-level multi-tenancy**: one shared `app-service` instance serves all tenants. Tenant isolation is enforced by the application itself using the `X-Tenant-ID` HTTP header.

```
POST /tasks   X-Tenant-ID: alice-corp   → creates a task for Alice
POST /tasks   X-Tenant-ID: bob-industries → creates a task for Bob
```

Both end up in the same database, separated by a `tenant_id` column.

### Mode 2 — Kubernetes (main/ folder)
**Infrastructure-level multi-tenancy**: each tenant gets a dedicated Kubernetes namespace with their own `app-service` deployment and their own PostgreSQL database. No header is needed — the namespace boundary *is* the isolation.

```
namespace: tenant-alice-corp
  └── deployment: app-service  → postgres (alice's data only)

namespace: tenant-bob-industries
  └── deployment: app-service  → postgres (bob's data only)
```

---

## API Contracts

### platform-api
```
GET    /tenants              → List all tenants (with plan + resource limits)
POST   /tenants              → Create a new tenant
GET    /tenants/{id}         → Get one tenant
PATCH  /tenants/{id}/suspend → Suspend a tenant
PATCH  /tenants/{id}/activate→ Activate a tenant
DELETE /tenants/{id}         → Delete a tenant
GET    /plans                → List available plans with resource limits
GET    /health               → Health check
```

### app-service
All endpoints require the `X-Tenant-ID` header (tenant slug, e.g. `alice-corp`).

```
GET    /tasks              → List all tasks for the tenant
POST   /tasks              → Create a task
PUT    /tasks/{id}         → Update a task (title, description, status, priority)
DELETE /tasks/{id}         → Delete a task
GET    /stats              → Task counts (todo / in_progress / done)
GET    /health             → Health check
```

### billing-service
```
POST   /record             → Record one API call (called internally by app-service)
GET    /usage              → Usage summary for all tenants (today + total)
GET    /usage/{tenant_id}  → Detailed usage for one tenant (breakdown by endpoint)
GET    /health             → Health check
```

---

## Running a Single Service (without Docker)

Useful for understanding the code before containerising it.

```bash
# Example: run the platform-api
cd platform-api
pip install -r requirements.txt
uvicorn main:app --reload --port 8010
# → http://localhost:8010/docs
```

Every service has an automatic Swagger UI at `/docs`.

---

## Environment Variables

### platform-api
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./platform.db` | Database connection |
| `PORT` | `8010` | Port to listen on |

### app-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./app.db` | Database connection |
| `BILLING_SERVICE_URL` | `http://localhost:8012` | Where to report usage |
| `PORT` | `8011` | Port to listen on |

### billing-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./billing.db` | Database connection |
| `PORT` | `8012` | Port to listen on |

---

## Seed Data

All three services automatically seed demo data on first run:

- **platform-api**: creates 3 tenants — Alice Corp (enterprise/active), Bob Industries (pro/active), Charlie Ltd (starter/suspended)
- **app-service**: creates tasks for each tenant slug (alice-corp, bob-industries, charlie-ltd)
- **billing-service**: generates 300 historical API call events spread over the past 7 days, weighted so Alice Corp is the heaviest user

---

## Dockerfiles

All services follow the same pattern:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE <port>
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "<port>"]
```

**DevOps questions to think about:**
- Why `python:3.11-slim` and not `python:3.11`?
- Why `--no-cache-dir` in a Dockerfile?
- Why `--host 0.0.0.0` instead of the default `127.0.0.1`?
- What's missing for production? (non-root user, health check, multi-stage build)
- How would you reduce the image size further?
