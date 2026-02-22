# Project 01: Production-Ready Microservices E-Commerce Platform

Build and deploy a fully containerized e-commerce platform using microservices architecture. You'll go from raw application code all the way to a production Kubernetes deployment with Istio service mesh, distributed tracing, circuit breakers, and rate limiting.

---

## What You're Building

A working online store with 5 backend services and a UI:

```
┌─────────────────────────────────────────────────────────┐
│                    API Gateway (nginx)                   │
└──────┬──────┬──────┬───────────┬──────────────────────-─┘
       │      │      │           │           │
  Products  Cart  Orders  Payments  Inventory
  Service  Service Service  Service   Service
       │      │      │           │           │
  PostgreSQL Redis PostgreSQL PostgreSQL PostgreSQL
```

| Service | Responsibility |
|---------|---------------|
| **Product Service** | Product catalog — browse, search, filter |
| **Cart Service** | Shopping cart — add, remove, view items |
| **Order Service** | Order management — create, track orders |
| **Payment Service** | Payment processing (mock gateway) |
| **Inventory Service** | Stock management — track and reserve inventory |
| **Frontend** | Simple web UI to see everything in action |

---

## Folder Structure

```
project-01-ecommerce-platform/
├── README.md          ← You are here
├── app/               ← Application source code (pre-built)
│   ├── README.md      ← How to run each service individually
│   ├── product-service/
│   ├── cart-service/
│   ├── order-service/
│   ├── payment-service/
│   ├── inventory-service/
│   └── frontend/
├── local/             ← Docker Compose for local development
│   ├── README.md      ← Step-by-step local setup guide
│   └── docker-compose.yml
└── main/              ← Production Kubernetes deployment
    └── README.md      ← What you'll build in the K8s phase
```

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)
Read the app README and understand what each service does. You don't write application code, but you need to know what you're deploying.

**Skills:** Reading architecture docs, understanding microservices, API contracts

### Phase 2 — Run It Locally (`local/`)
Use Docker Compose to get the entire stack running on your machine. Inspect how services discover each other, how the API gateway routes traffic, and how data flows between services.

**Skills:** Docker Compose, service networking, volume mounts, environment variables, health checks

### Phase 3 — Deploy to Kubernetes (`main/`)
Write Kubernetes manifests for every service. Deploy to a real cluster. Add ConfigMaps, Secrets, Services, Ingress, PersistentVolumeClaims.

**Skills:** Deployments, Services, Ingress, ConfigMaps, Secrets, PVCs, namespaces

### Phase 4 — Add Istio Service Mesh
Install Istio, enable sidecar injection, configure traffic management, canary deployments, and mutual TLS between services.

**Skills:** Istio, VirtualService, DestinationRule, mTLS, traffic shifting

### Phase 5 — Circuit Breakers & Rate Limiting
Protect your services from cascade failures and abuse. Configure Istio circuit breakers, outlier detection, and rate limiting with Envoy filters.

**Skills:** Circuit breakers, outlier detection, rate limiting, Envoy filters

### Phase 6 — Distributed Tracing
Deploy Jaeger, configure Istio tracing, and follow a request as it flows through all 5 services.

**Skills:** Jaeger, OpenTelemetry, trace sampling, span correlation

---

## What the Final Architecture Looks Like

```
Internet
    │
    ▼
[Ingress / Istio Gateway]
    │
    ▼
[Frontend - nginx]
    │  (calls /api/* routes)
    ▼
[Istio Envoy Sidecar] ← Rate Limiting, mTLS, Tracing
    │
    ├──→ product-service  ──→ PostgreSQL
    ├──→ cart-service     ──→ Redis
    ├──→ order-service    ──→ PostgreSQL  ──→ (calls payment + inventory)
    ├──→ payment-service  ──→ PostgreSQL
    └──→ inventory-service──→ PostgreSQL
         │
         ▼
    [Jaeger] ← All traces collected here
    [Prometheus + Grafana] ← Metrics from Istio + services
```

---

## Prerequisites

- Docker and Docker Compose (for Phase 2)
- kubectl and a Kubernetes cluster (for Phase 3+)
- Helm (for Istio installation)
- Basic Python knowledge (to understand the services, not write them)

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand the application**

Then follow: `app/` → `local/` → `main/`
