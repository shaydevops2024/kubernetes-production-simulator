# Project 03: Real-Time Chat / Messaging Platform

Build and deploy a production-grade real-time chat platform using WebSockets, Redis pub/sub, and S3-compatible file storage. You'll go from understanding the architecture all the way to a horizontally scalable Kubernetes deployment.

---

## What You're Building

A working chat application that actually scales — because you'll build the infrastructure right:

```
┌──────────────────────────────────────────────────────────────┐
│                    API Gateway (nginx)                        │
│         WebSocket + REST routing + file upload proxy          │
└────┬───────────┬──────────────┬───────────────┬──────────────┘
     │           │              │               │
  /ws/*    /api/chat/*  /api/presence/*   /api/files/*
     │           │              │               │
 chat-service  chat-service  presence-service  file-service
  (WebSocket)   (REST)         (Redis TTL)      (MinIO)
     │                │                         │
  Redis          PostgreSQL                  MinIO
  pub/sub        (messages)               (S3-compatible)
                                               │
                                     notifications-service
                                          (PostgreSQL)
```

| Service | What it does |
|---------|-------------|
| **chat-service** | WebSocket engine. Handles connections, broadcasts messages via Redis pub/sub, persists to PostgreSQL |
| **presence-service** | Who's online + typing indicators. Pure Redis — TTL-based, handles disconnects automatically |
| **notification-service** | Tracks mentions and system notifications. PostgreSQL-backed |
| **file-service** | Upload images and files. Stores in MinIO (S3-compatible). Proxies downloads so the browser never talks to MinIO directly |
| **frontend** | Single-page chat UI. WebSocket client + REST calls. Rooms, typing indicators, file uploads, notifications |

---

## Folder Structure

```
project-03-realtime-chat/
├── README.md          ← You are here
├── app/               ← Application source code (pre-built)
│   ├── README.md      ← Services, APIs, env vars, design decisions
│   ├── chat-service/
│   ├── presence-service/
│   ├── notification-service/
│   ├── file-service/
│   └── frontend/
├── local/             ← Docker Compose for local development
│   ├── README.md      ← Step-by-step local guide + DevOps tasks
│   ├── docker-compose.yml
│   └── nginx/nginx.conf
└── main/              ← Production Kubernetes deployment
    └── README.md      ← What you'll build in the K8s phase
```

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)

Read `app/README.md`. Understand:
- How WebSocket pub/sub works across multiple replicas
- Why Redis TTL is better than connection-event presence tracking
- How MinIO maps to AWS S3 in production

**Skills:** WebSocket architecture, Redis pub/sub, object storage, service communication

### Phase 2 — Run It Locally (`local/`)

Get the full stack running with Docker Compose. Explore:
- WebSocket traffic in browser DevTools
- Redis pub/sub with `redis-cli SUBSCRIBE`
- File storage in the MinIO Console
- Horizontal scaling with `docker compose --scale chat-service=2`

**Skills:** Docker Compose, nginx WebSocket proxying, Redis CLI, MinIO

### Phase 3 — Deploy to Kubernetes (`main/`)

Write K8s manifests for all services. The interesting challenges:
- WebSocket-aware Ingress configuration (timeouts, Upgrade headers)
- Redis as a StatefulSet (or use Redis Cluster for HA)
- MinIO as a StatefulSet with persistent storage
- HPA for chat-service (scale on connections/CPU)
- Secrets for database credentials and MinIO keys

**Skills:** Deployments, StatefulSets, Services, Ingress (WebSocket), Secrets, HPA, PVCs

### Phase 4 — Add Horizontal Scaling

Deploy 3 replicas of chat-service. Verify that messages from one replica reach users on another — thanks to Redis pub/sub.

**Skills:** HPA, ReplicaSets, Redis pub/sub validation, load testing with WebSocket clients

### Phase 5 — Observability

Add Prometheus metrics to the chat-service (active WebSocket connections per room, messages per second, Redis latency). Deploy Grafana dashboards.

**Skills:** Prometheus Python client, custom metrics, Grafana dashboards

### Phase 6 — Production Hardening

Replace MinIO with AWS S3 (or GCS). Add mTLS between services with Istio. Configure Redis Sentinel for HA. Add rate limiting on the WebSocket endpoint.

**Skills:** S3 integration, Istio, Redis HA, WebSocket rate limiting

---

## What the Final K8s Architecture Looks Like

```
Internet
    │
    ▼
[Ingress — nginx]
  WebSocket: proxy_read_timeout 3600s + Upgrade headers
    │
    ├──→ [frontend — Deployment 1 pod]
    │
    ├──→ [chat-service — Deployment 3 pods, HPA enabled]
    │         │                 │
    │    Redis pub/sub    PostgreSQL StatefulSet
    │    (all pods share)  (messages + rooms)
    │
    ├──→ [presence-service — Deployment 2 pods]
    │         │
    │    Redis (same instance — shared state)
    │
    ├──→ [notification-service — Deployment 2 pods]
    │         │
    │    PostgreSQL StatefulSet (notifications)
    │
    └──→ [file-service — Deployment 2 pods]
              │
         MinIO StatefulSet  (or AWS S3 in production)
         PostgreSQL StatefulSet (file metadata)
```

---

## Why This Project Teaches Real DevOps Skills

| What you configure | What you learn |
|--------------------|----------------|
| nginx WebSocket proxy | How WebSocket upgrades work, why timeouts matter |
| Redis pub/sub | Why stateful services need external coordination |
| Redis TTL presence | Pattern for handling network disconnects gracefully |
| MinIO → S3 swap | How to design for cloud portability from day one |
| HPA on chat-service | How to scale stateful-feeling services horizontally |
| StatefulSets for Redis/PG | When to use StatefulSet vs Deployment and why |

---

## Prerequisites

- Docker and Docker Compose (for Phase 2)
- kubectl and a Kubernetes cluster (for Phase 3+)
- Helm (for Redis/MinIO operators or direct install)
- Basic understanding of WebSockets

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand the platform**

Then follow: `app/` → `local/` → `main/`
