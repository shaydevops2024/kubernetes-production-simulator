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
| 06 | [GatewayHub — API Gateway with Advanced Traffic Management](./project-06-api-gateway/README.md) | Kong, JWT Auth, Rate Limiting, Request Transform, API Versioning, Helm, ArgoCD | ✅ Available |
| 07 | [Serverless Functions Platform on Kubernetes](./project-07-serverless-platform/README.md) | OpenFaaS, KEDA, Scale-to-Zero, HPA, CronJob, ArgoCD | ✅ Available |
| 08 | [Real-Time Data Pipeline on Kubernetes](./project-08-data-pipeline/README.md) | Kafka/Strimzi, Apache Spark, TimescaleDB, GitLab CI, ArgoCD, KEDA, Vault, Chaos Engineering | ✅ Available |
| 09 | [Kubernetes Disaster Recovery System](./project-09-disaster-recovery/README.md) | Velero, MinIO/S3, LitmusChaos, Prometheus, Terraform/EKS, RPO/RTO Runbooks | ✅ Available |
| 10 | [Zero-Downtime Blue-Green Deployment System](./project-10-blue-green-deployment/README.md) | Blue-Green, GitLab CI, Health Checks, Smoke Tests, DB Migration, nginx Ingress, Rollback | ✅ Available |
| 11 | [Multi-Region Disaster Recovery System](./project-11-multi-region-disaster-recovery/README.md) | Velero, Multi-Cluster Kind, MinIO, PostgreSQL Replication, Failover Scripts, Prometheus/Grafana | ✅ Available |
| 12 | [Enterprise Secrets Management Platform](./project-12-secrets-management/README.md) | HashiCorp Vault, Dynamic Secrets, PKI, Transit Encryption, K8s Auth, Audit Logging | ✅ Available |
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

**Intermediate:** Projects 01–03 (full main/ deployment) → Project 04 → Project 05 (observability) → Project 06 (API gateway) → Project 07 (serverless)

**Advanced:** Project 08 (data pipeline) → Project 09 (disaster recovery) → Project 10 (blue-green) → Project 11 (multi-region DR) → Project 12 (secrets management) → Projects 15, 16
