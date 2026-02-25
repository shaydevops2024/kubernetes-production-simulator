# Project 09: Kubernetes Disaster Recovery System

Build a production-grade disaster recovery system entirely on your local Kubernetes cluster, with ready-made cloud deployment scripts included.

You protect a real running application — a critical operations dashboard — and take it through the full DR lifecycle: backup, failure simulation, recovery, and validation.

---

## What You're Building

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           Kind Cluster                                   │
│                                                                          │
│  Namespace: dr-lab                                                       │
│  ┌─────────────┐   ┌─────────────────────┐   ┌─────────────────────┐   │
│  │  DR App     │──▶│  postgres-primary    │   │  MinIO              │   │
│  │  port 4545  │   │  (primary region)    │   │  (S3-compatible     │   │
│  │             │──▶│  postgres-secondary  │   │   backup storage)   │   │
│  └─────────────┘   │  (DR region)         │   └─────────┬───────────┘   │
│                    └─────────────────────┘             │               │
│  Namespace: velero                                      ▼               │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │  Velero  ──── hourly backup ──────────────────────────────── │       │
│  │           ──── daily full backup ────────────────────────── │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  Namespace: litmus                                                       │
│  ┌─────────────────────────────┐                                        │
│  │  LitmusChaos Portal         │  ← Inject pod kills, network chaos     │
│  └─────────────────────────────┘                                        │
│                                                                          │
│  Namespace: monitoring                                                   │
│  ┌──────────────┐  ┌──────────────┐                                     │
│  │  Prometheus  │  │  Grafana     │  ← RPO/RTO dashboards               │
│  └──────────────┘  └──────────────┘                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
project-09-disaster-recovery/
├── README.md              ← You are here
├── app/                   ← Critical business service (pre-built FastAPI app)
│   ├── README.md          ← App overview, API contracts, environment variables
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── static/
│       └── index.html     ← DR monitoring dashboard (port 4545)
├── local/                 ← Docker Compose for local development
│   ├── README.md          ← Step-by-step local guide + DevOps tasks
│   └── docker-compose.yml ← App + 2x PostgreSQL + MinIO
├── main/                  ← Kubernetes deployment (you build this)
│   └── README.md          ← Phased guide: Core → Velero → Chaos → Monitoring
└── solution/              ← Reference implementation
    ├── k8s/               ← All Kubernetes manifests
    │   ├── namespace.yaml
    │   ├── app/           ← Deployment, Service, Ingress, ConfigMap, Secret
    │   ├── database/      ← Primary + Secondary PostgreSQL StatefulSets
    │   ├── minio/         ← MinIO StatefulSet + Services
    │   ├── velero/        ← Backup Schedule + Restore manifest
    │   ├── monitoring/    ← Prometheus alerting rules
    │   └── chaos/         ← LitmusChaos pod-kill + network-chaos experiments
    ├── helm/              ← Helm values for Velero, LitmusChaos, Prometheus
    │   ├── velero-values.yaml
    │   ├── litmus-values.yaml
    │   └── prometheus-values.yaml
    └── terraform/
        └── eks/           ← AWS EKS + S3 deployment (cloud migration path)
            ├── main.tf
            ├── variables.tf
            └── outputs.tf
```

→ Details for each folder: [app/README.md](./app/README.md) — [local/README.md](./local/README.md) — [main/README.md](./main/README.md)

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)
Read the app README. You don't write application code, but you need to know what you're protecting — what data it stores, how it connects to its databases, and what "healthy" looks like.

**Skills:** Reading architecture docs, API contracts, understanding stateful services

### Phase 2 — Run It Locally (`local/`)
Use Docker Compose to start the full stack: the app, two PostgreSQL instances, and MinIO. Simulate a basic backup and restore manually. Measure your first RTO.

**Skills:** Docker Compose, MinIO/S3, pg_dump/restore, health checks, RPO/RTO concepts

### Phase 3A — Deploy to Kubernetes (`main/`)
Write Kubernetes manifests. Deploy to Kind. Use StatefulSets for databases, ConfigMaps for config, Secrets for credentials. Build and load the Docker image.

**Skills:** Deployments, StatefulSets, Services, Secrets, ConfigMaps, PVCs

### Phase 3B — Backup with Velero
Install Velero via Helm, configure MinIO as the S3-compatible backend, and set up hourly + daily backup schedules. Run a manual backup. Inspect what Velero actually saves.

**Skills:** Velero, Helm, S3/MinIO, backup hooks, TTL, RBAC for backup agents

### Phase 3C — Simulate Disaster and Recover
Delete the entire namespace (catastrophic failure). Restore from the Velero backup. Measure your actual RTO. Fill in the runbook.

**Skills:** Velero restore, namespace recreation, PV restore, measuring RTO

### Phase 3D — Chaos Engineering
Install LitmusChaos. Run a pod-kill experiment to test K8s self-healing. Run a network-partition experiment to test database failover. Observe the dashboard during chaos.

**Skills:** LitmusChaos, chaos experiment YAML, observing graceful degradation

### Phase 3E — Monitoring
Install Prometheus + Grafana. Apply PrometheusRules for RPO breach alerts. View backup metrics in Grafana. Configure AlertManager to fire when RPO is exceeded.

**Skills:** Prometheus, Grafana, PrometheusRule, AlertManager, PromQL

### Phase 4 — Cloud Migration (optional)
Run the Terraform in `solution/terraform/eks/` to provision EKS + S3. Point Velero at the S3 bucket. Run the same restore procedure. Everything works without changes.

**Skills:** Terraform, EKS, AWS S3, IRSA (IAM Roles for Service Accounts), lift-and-shift

---

## What the Final Architecture Validates

| Scenario | Expected Behavior | Your Measurement |
|----------|------------------|-----------------|
| Pod failure | K8s restarts pod, app recovers in < 2 min | RTO: ____ |
| DB connection loss | App degrades gracefully, shows error | RTO: ____ |
| Full namespace deletion | Velero restores in < 15 min | RTO: ____ |
| Hourly backup | No more than 60 min of data loss | RPO: ____ |
| Network partition | App falls back to secondary DB | RTO: ____ |

---

## Prerequisites

- Kind cluster with at least 3 nodes (already set up by the simulator)
- Docker and Docker Compose (for Phase 2)
- kubectl, Helm 3, and basic familiarity with Kubernetes
- 6 GB of free RAM (for the full stack)

---

## RTO/RPO Runbook

Document your measured values as you go:

```
Service: DR Operations Dashboard
Owner: [you]
Last tested: [date]

Recovery Objectives:
  RPO Target: 60 minutes
  RTO Target: 15 minutes

Backup Configuration:
  Tool: Velero
  Backend: MinIO (local) / S3 (cloud)
  Schedule: hourly incremental + daily full
  Retention: 7 days incremental, 30 days full

Recovery Procedure:
  1. Identify failure scope (pod / namespace / data)
  2. Trigger Velero restore: velero restore create --from-backup <name>
  3. Verify pod health: kubectl -n dr-lab get pods
  4. Verify data integrity: curl http://localhost:4545/api/records
  5. Document RTO: (restore_complete_time - failure_detected_time)

Measured Results:
  Last RPO: ____
  Last RTO: ____
  Last test date: ____
  Test result: pass / fail
```

---

## Cloud Option

The `solution/terraform/eks/` folder provisions:
- **EKS cluster** (3 × t3.medium) in a private VPC
- **S3 bucket** for Velero backups with lifecycle rules
- **IAM role** for Velero via IRSA (no static credentials)
- **NGINX Ingress** for external access

To deploy:
```bash
cd solution/terraform/eks/
terraform init
terraform apply

# Configure kubectl
$(terraform output -raw configure_kubectl)

# Install Velero (command from Terraform output)
$(terraform output -raw velero_helm_command)
```

Everything else — the K8s manifests, Velero schedules, chaos experiments — stays identical.

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand what you're protecting**

Then follow: `app/` → `local/` → `main/`
