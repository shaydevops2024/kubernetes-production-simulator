# Hands-On DevOps Projects

Real-world, production-grade projects you build from scratch — learning DevOps by doing, not just reading.

Each project includes a pre-built application so you can focus **100% on DevOps tasks**: containerization, orchestration, service mesh, CI/CD, observability, security, and more.

---

## How Each Project is Structured

Every project has three folders:

| Folder | Purpose |
|--------|---------|
| `app/` | The application source code — services, Dockerfiles, and app-level README. You don't write this, but you containerize and deploy it. |
| `local/` | Docker Compose setup to run the full stack locally. Your first DevOps task. |
| `main/` | Production-ready deployment — Kubernetes manifests, Helm charts, service mesh config, CI/CD pipelines. This is what you build toward. |

**Workflow:** `app/` → understand → `local/` → run locally → `main/` → deploy to production

---

## Projects

| # | Project | Topics | Status |
|---|---------|--------|--------|
| 01 | [Production-Ready Microservices E-Commerce Platform](./project-01-ecommerce-platform/README.md) | Istio, Distributed Tracing, Circuit Breakers, Rate Limiting | ✅ Available |
| 02 | [Multi-Tenant SaaS Application Infrastructure](./project-02-multitenant-saas/README.md) | Namespaces, RBAC, ResourceQuota, NetworkPolicy, Multi-tenancy | ✅ Available |
| 03 | [Real-Time Chat / Messaging Platform](./project-03-realtime-chat/README.md) | WebSockets, Redis pub/sub, MinIO/S3, Horizontal Scaling, Presence | ✅ Available |
| 04 | [Full GitOps CI/CD Pipeline with Progressive Delivery](./project-04-gitops-cicd/README.md) | GitHub Actions, ArgoCD, Flagger, Canary Deployments, Rollback | ✅ Available |
| 05 | [Complete Observability Stack](./project-05-observability-stack/README.md) | Prometheus, Grafana, Loki, Tempo, Jaeger, AlertManager, Thanos, SLO/SLI | ✅ Available |
| 06 | High-Availability Database Cluster | PostgreSQL HA, Redis Cluster, StatefulSets | 🔜 Coming Soon |
| 07 | Multi-Region Active-Active Setup | Federation, Global Load Balancing | 🔜 Coming Soon |
| 08 | Autoscaling & Cost Optimization | HPA, VPA, KEDA, Spot Instances | 🔜 Coming Soon |
| 09 | Disaster Recovery System | Velero, Cross-Region Replication, RTO/RPO | 🔜 Coming Soon |
| 10 | Platform Engineering (IDP) | Backstage, Self-Service Infrastructure | 🔜 Coming Soon |
| 11 | MLOps Pipeline | Kubeflow, Model Serving, A/B Testing | 🔜 Coming Soon |
| 12 | Serverless on Kubernetes | Knative, Event-Driven Architecture | 🔜 Coming Soon |
| 13 | Zero-Downtime Deployment Strategies | Argo Rollouts, Canary, Blue-Green | 🔜 Coming Soon |
| 14 | API Gateway & Rate Limiting | Kong, OAuth2, JWT, Traffic Policies | 🔜 Coming Soon |
| 15 | SRE Practices Platform | SLOs, Error Budgets, Chaos Engineering | 🔜 Coming Soon |
| 16 | Security Compliance & Audit | Falco, OPA Gatekeeper, CIS Benchmarks | 🔜 Coming Soon |

---

## Prerequisites

Before starting any project:
- Docker & Docker Compose installed
- `kubectl` installed and configured
- A Kubernetes cluster (Kind, Minikube, or cloud)
- Basic understanding of containers and Linux

---

## Learning Path

**Beginner:** Start with Project 01 (local/ folder only) → Project 02 → Project 07

**Intermediate:** Projects 01–03 (full main/ deployment) → Project 04 → Project 05 (observability)

**Advanced:** Projects 07, 10, 11, 12, 15, 16
