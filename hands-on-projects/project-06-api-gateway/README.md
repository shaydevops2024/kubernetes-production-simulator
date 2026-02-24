# Project 06: GatewayHub — API Gateway with Advanced Traffic Management

Deploy Kong API Gateway in front of a real REST API. Configure JWT authentication, per-consumer rate limiting, request transformation, API versioning (v1/v2), and a live analytics dashboard — then deploy it all to Kubernetes using Kong Ingress Controller, Helm, and ArgoCD.

---

## What You're Building

```
┌──────────────────────────────────────────────────────────────────┐
│                    Browser / curl / API Client                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼ :8888 (local) / :80 (K8s)
┌──────────────────────────────────────────────────────────────────┐
│                     Kong API Gateway                             │
│                                                                  │
│  Plugins: JWT Auth │ Rate Limiting │ Request Transform │ CORS    │
│           Prometheus Metrics │ Consumer Management               │
│                                                                  │
│  Routes:  /v1/products (public, 10 req/min)                      │
│           /v1/users /v1/orders (JWT required, 30 req/min)        │
│           /v2/* (JWT required, 60 req/min, enhanced headers)     │
│           /auth  (no auth, token generation)                     │
│           /analytics (analytics service)                         │
└──────┬──────────────────────────┬────────────────────────────────┘
       │                          │
       ▼                          ▼
┌─────────────┐          ┌──────────────────┐
│ api-service │          │analytics-service │
│   :8001     │          │    :8002         │
│             │          │                  │
│ v1 routes   │          │ Kong stats       │
│ v2 routes   │          │ API metrics      │
│ auth/login  │          │ Route config     │
└──────┬──────┘          └──────────────────┘
       │
┌──────▼──────┐  ┌─────────────┐
│ PostgreSQL  │  │    Redis    │
│  (app data) │  │ (rate limit │
│             │  │  backend)   │
└─────────────┘  └─────────────┘
```

By the end of this project you will have a production-style API gateway setup with:

- **JWT authentication** validated at the gateway before any request reaches your backend
- **Per-consumer rate limiting** backed by Redis — free users get 30 req/min, v2 routes get 60 req/min, public endpoints get 10 req/min
- **Request transformation** — Kong injects `X-API-Version` and `X-Enhanced-Response` headers on all v2 responses
- **API versioning** — v1 (public + protected) and v2 (enhanced response format, JWT required)
- **Live analytics dashboard** — a second FastAPI service reads the Kong Admin API and your API service metrics
- **Kong Ingress Controller** — Kong running natively in Kubernetes, configured entirely through CRDs
- **GitOps delivery** — Kong plugin configuration changes applied through ArgoCD

---

## Folder Structure

```
project-06-api-gateway/
├── README.md              ← You are here
│
├── app/                   ← Pre-built application code (do not modify)
│   ├── README.md          ← API reference, env vars, JWT flow explained
│   ├── api-service/       ← FastAPI REST API (v1 + v2 + auth endpoints)
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── analytics-service/ ← FastAPI service that reads Kong Admin API
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── frontend/          ← Nginx-served dashboard UI
│       ├── nginx.conf
│       └── style.css
│
├── local/                 ← Full stack via Docker Compose
│   ├── docker-compose.yml ← Kong + api-service + analytics + redis + postgres
│   └── kong/
│       └── kong.yml       ← Kong declarative config (DB-less mode)
│
└── main/                  ← Production Kubernetes deployment
    └── solution/          ← Complete K8s manifests (reference implementation)
        ├── namespace.yaml
        ├── configmaps/
        ├── secrets/
        ├── deployments/   ← api-service, analytics-service, frontend
        ├── services/      ← ClusterIP services for all workloads
        ├── statefulsets/  ← PostgreSQL and Redis
        ├── hpa/           ← HorizontalPodAutoscaler for api-service
        └── kong/
            ├── consumers.yaml     ← KongConsumer + JWT credential Secrets
            └── plugins/           ← KongPlugin CRDs
                ├── jwt.yaml
                ├── cors.yaml
                ├── prometheus.yaml
                ├── rate-limiting-public.yaml
                ├── rate-limiting-consumer.yaml
                └── request-transformer.yaml
```

---

## Your DevOps Journey

### Phase 1 — Understand the Application (app/)

Read [app/README.md](./app/README.md) to understand the API before touching any infrastructure.

- Explore the FastAPI code for `api-service` and `analytics-service`
- Understand the v1 vs v2 versioning strategy and response format differences
- Understand how JWT is generated and what claims Kong validates
- Read the analytics service to see how it polls the Kong Admin API

**Key questions to answer before proceeding:**
- What is the `iss` claim in the JWT, and why does Kong care about it?
- What is the difference between the v1 and v2 products response?
- How does `analytics-service` get its data without any authentication?

**Skills:** API design, JWT structure, FastAPI, service-to-service communication

---

### Phase 2 — Run Locally with Docker Compose (local/)

Start the full stack locally to understand how Kong, Redis, and the application services interact before you touch Kubernetes.

```bash
cd local/
docker compose up -d
```

What runs:
- **Kong** at `:8888` (proxy) and `:8001` (Admin API)
- **api-service** at `:8001` (internal, not exposed directly)
- **analytics-service** at `:8002` (internal, routed through Kong at `/analytics`)
- **Redis** for rate limit state storage
- **PostgreSQL** for application data

**Exercises:**

1. Get a JWT token:
   ```bash
   curl -s -X POST http://localhost:8888/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "alice"}' | jq .
   ```

2. Hit the public endpoint (no token needed):
   ```bash
   curl http://localhost:8888/v1/products
   ```

3. Hit it 11 times and watch the rate limit kick in (limit is 10/min):
   ```bash
   for i in {1..12}; do
     curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8888/v1/products
   done
   ```

4. Access a protected endpoint with your token:
   ```bash
   TOKEN="<paste token here>"
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8888/v1/users/me
   ```

5. Compare v1 vs v2 product responses:
   ```bash
   curl http://localhost:8888/v1/products/1
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8888/v2/products
   ```

6. Inspect Kong Admin API directly:
   ```bash
   curl localhost:8001/services
   curl localhost:8001/routes
   curl localhost:8001/plugins
   curl localhost:8001/consumers
   ```

7. View live analytics:
   ```bash
   curl http://localhost:8888/analytics/stats | jq .
   ```

**Skills:** Docker Compose, Kong declarative config, DB-less mode, JWT, rate limiting, Redis

---

### Phase 3 — Deploy to Kubernetes (main/)

Install Kong Ingress Controller via Helm, then deploy all application services and stateful backends to Kubernetes.

See [main/README.md](./main/README.md) for the complete step-by-step guide.

**You will:**
- Install Kong via Helm into the `api-gateway` namespace
- Deploy api-service, analytics-service, and frontend as Deployments
- Deploy PostgreSQL and Redis as StatefulSets with PersistentVolumeClaims
- Create Kubernetes Secrets and ConfigMaps for configuration

**Skills:** Helm, Kubernetes Deployments, StatefulSets, PersistentVolumes, Secrets, ConfigMaps

---

### Phase 4 — Configure Kong Plugins as CRDs

This is where Kubernetes-native Kong configuration diverges from the local Docker Compose setup. Instead of a `kong.yml` file, you apply Kubernetes Custom Resources.

```bash
kubectl apply -f solution/kong/plugins/
kubectl apply -f solution/kong/consumers.yaml
```

Each file maps to a Kong concept:
- `KongPlugin` — a named, reusable plugin configuration
- `KongConsumer` — a Kong consumer identity (linked to a K8s Secret holding JWT credentials)
- Ingress annotations — wire plugins to specific routes

**Skills:** Kubernetes CRDs, KongPlugin, KongConsumer, Ingress annotations

---

### Phase 5 — API Versioning and Traffic Management

Wire route-level plugin configurations with differentiated policies:

| Route | Auth | Rate Limit | Extra |
|-------|------|------------|-------|
| `/v1/products` | None | 10 req/min (IP) | Public access |
| `/v1/users`, `/v1/orders` | JWT | 30 req/min (consumer) | Standard tier |
| `/v2/*` | JWT | 60 req/min (consumer) | + request-transformer headers |
| `/auth` | None | None | Token generation |
| `/analytics` | None | None | Internal analytics |

After applying all resources:
- Verify consumers are created: `kubectl get kongconsumers -n api-gateway`
- Verify plugins are created: `kubectl get kongplugins -n api-gateway`
- Test that alice (premium) and bob (free) both authenticate successfully
- Confirm v2 responses include `X-API-Version: 2.0` and `X-Enhanced-Response: true` headers
- Enable Kong Prometheus metrics and scrape `/metrics` from the Kong proxy

**Skills:** Traffic management, consumer-based rate limiting, request transformation, Prometheus

---

### Phase 6 — GitOps with ArgoCD (advanced)

Install ArgoCD and manage Kong configuration changes through Git.

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Create an ArgoCD Application pointing at your fork of this repository. ArgoCD will watch the `main/solution/kong/` directory and apply any changes you push.

**Simulate a policy change via GitOps:**
1. Update the rate limit in `rate-limiting-public.yaml` from 10 to 20 req/min
2. Commit and push
3. Watch ArgoCD detect the diff and sync the change
4. Verify the new limit is enforced

**Skills:** ArgoCD, GitOps, Application manifests, drift detection

---

## Tools You'll Use

| Tool | Purpose |
|------|---------|
| Kong Gateway | API Gateway, plugin engine |
| Kong Ingress Controller | K8s-native Kong config via CRDs |
| Helm | Install Kong on Kubernetes |
| ArgoCD | GitOps delivery for gateway configuration |
| Redis | Rate limiting state storage |
| PostgreSQL | Application data (users, orders, products) |
| Prometheus | Kong metrics export via `/metrics` |
| kubectl | Kubernetes resource management |
| Docker Compose | Local full-stack development |

---

## Prerequisites

- Docker and Docker Compose (for Phase 2)
- kubectl connected to a Kind or Minikube cluster (for Phase 3+)
- Helm 3.x installed (for Phase 3+)
- ArgoCD CLI (optional, for Phase 6)
- Basic understanding of HTTP, REST APIs, and Kubernetes fundamentals

---

## Start Here

**→ Read [app/README.md](./app/README.md) first** to understand what you are protecting.

Then follow the phases in order:

`app/` → `local/` → `main/`
