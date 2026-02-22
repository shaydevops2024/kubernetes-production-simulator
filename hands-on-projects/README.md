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
| 02 | GitOps CI/CD Pipeline | GitHub Actions, ArgoCD, Helm, Automated Testing | 🔜 Coming Soon |
| 03 | Observability & Monitoring Platform | Prometheus, Grafana, Jaeger, EFK Stack | 🔜 Coming Soon |
| 04 | Zero-Trust Security Platform | OPA, Network Policies, Pod Security Standards | 🔜 Coming Soon |
| 05 | High-Availability Database Cluster | PostgreSQL HA, Redis Cluster, StatefulSets | 🔜 Coming Soon |
| 06 | Multi-Region Active-Active Setup | Federation, Global Load Balancing | 🔜 Coming Soon |
| 07 | Autoscaling & Cost Optimization | HPA, VPA, KEDA, Spot Instances | 🔜 Coming Soon |
| 08 | Disaster Recovery System | Velero, Cross-Region Replication, RTO/RPO | 🔜 Coming Soon |
| 09 | Platform Engineering (IDP) | Backstage, Self-Service Infrastructure | 🔜 Coming Soon |
| 10 | MLOps Pipeline | Kubeflow, Model Serving, A/B Testing | 🔜 Coming Soon |
| 11 | Serverless on Kubernetes | Knative, Event-Driven Architecture | 🔜 Coming Soon |
| 12 | Multi-Tenant SaaS Platform | Namespace Isolation, Resource Quotas, Billing | 🔜 Coming Soon |
| 13 | API Gateway & Rate Limiting | Kong, OAuth2, JWT, Traffic Policies | 🔜 Coming Soon |
| 14 | Edge Computing Setup | K3s, Edge Nodes, CDN Integration | 🔜 Coming Soon |
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

**Intermediate:** Projects 01-05 (full main/ deployment) → Project 03 (observability) → Project 04

**Advanced:** Projects 06, 09, 10, 11, 15, 16
