# Project 11: Multi-Region Disaster Recovery System

Deploy the same application to two separate Kubernetes clusters — simulating two geographic regions. One cluster is always live; the other is a warm standby ready to take over in minutes.

This is how companies like Netflix, Stripe, and GitHub protect against regional outages.

---

## What You're Building

```
                        Users
                          │
                   [Global DNS / LB]
                     proxy_pass ↓
              ┌──────────────────────────┐
              │       nginx router       │  ← simulates DNS failover
              └──────────┬───────────────┘
                         │
              ┌──────────▼───────────┐   ┌────────────────────────────┐
              │  kind-primary        │   │  kind-secondary             │
              │  eu-west-1  ● ACTIVE │   │  us-east-1  ◌ STANDBY      │
              │                      │   │                             │
              │  RegionWatch app (3) │   │  RegionWatch app (2)        │
              │  PostgreSQL (main)   │   │  PostgreSQL (replica)       │
              │  Velero ─────────────┼───┼─► Velero (restore)         │
              └──────────────────────┘   └─────────────────────────────┘
                                    │
                             ┌──────┴──────┐
                             │    MinIO    │  ← shared backup storage
                             │  (S3 sim.)  │     both clusters back up here
                             └─────────────┘
```

**When primary fails:**
1. Velero backup is on MinIO (RPO = time since last backup, max 15 min)
2. Secondary already has the app running (warm standby)
3. nginx config flips to secondary (RTO target: < 5 minutes)

---

## Folder Structure

```
project-11-multi-region-disaster-recovery/
├── README.md              ← You are here
├── app/                   ← Application source code (RegionWatch DR Dashboard)
│   ├── README.md          ← App overview, API endpoints, environment variables
│   ├── main.py            ← FastAPI app — role changes with REGION_ROLE env var
│   ├── Dockerfile
│   └── requirements.txt
├── local/                 ← Docker Compose simulation (Phase 2)
│   ├── README.md          ← Step-by-step local DR guide
│   ├── docker-compose.yml ← Primary + Secondary + PostgreSQL + MinIO + nginx
│   └── nginx/
│       └── nginx.conf     ← Traffic router (edit to switch between regions)
├── main/                  ← Kubernetes deployment (Phase 3 — you build this)
│   └── README.md          ← Full multi-cluster DR guide
└── solution/              ← Complete reference solution
    ├── k8s/               ← Kubernetes manifests (primary + secondary)
    │   ├── namespace/
    │   ├── configmaps/    ← Separate configs for primary and secondary
    │   ├── secrets/
    │   ├── statefulsets/  ← PostgreSQL StatefulSets
    │   ├── deployments/   ← RegionWatch Deployments
    │   ├── services/
    │   ├── ingress/
    │   ├── minio/         ← Optional: MinIO in-cluster
    │   └── velero/        ← Backup schedule + restore YAML
    ├── helm/
    │   └── velero-values.yaml  ← Velero Helm chart values
    ├── scripts/
    │   ├── setup-clusters.sh   ← Create both Kind clusters
    │   ├── install-velero.sh   ← Install Velero on both clusters
    │   ├── failover.sh         ← Perform manual failover
    │   ├── restore.sh          ← DR test: delete + restore from backup
    │   └── verify-dr.sh        ← Validation checklist
    ├── monitoring/
    │   ├── prometheus-rules.yaml  ← RPO/RTO alerting rules
    │   └── grafana-dashboard.json ← Import into Grafana
    └── gitlab-ci/
        └── .gitlab-ci.yml      ← Full CI/CD + nightly DR test
```

**→ Start with [app/README.md](./app/README.md) to understand the application.**

Then follow: `app/` → `local/` → `main/`

---

## Your DevOps Journey

### Phase 1 — Understand the App (`app/`)

Read the app README. Understand:
- Why the same Docker image can be either `primary` or `secondary` (env vars only)
- What RTO and RPO mean in practice
- Why the `/health` endpoint is critical for failover automation

**Skills:** App architecture, environment variables, health probes, DR concepts

---

### Phase 2 — Run It Locally (`local/`)

Spin up the full multi-region stack with Docker Compose:

```bash
cd hands-on-projects/project-11-multi-region-disaster-recovery/local
docker compose up --build
```

| Access point | URL | Description |
|--|--|--|
| Live (nginx) | http://localhost:5858 | Production entry point — routes to primary |
| Primary direct | http://localhost:5860 | eu-west-1 region |
| Secondary direct | http://localhost:5861 | us-east-1 region (standby) |
| MinIO Console | http://localhost:9001 | Backup storage UI |

Manually simulate a failover by editing `nginx/nginx.conf` and reloading.
Measure your RTO. Observe the secondary dashboard change state.

**Skills:** Docker Compose, nginx upstreams, failover mechanics, RTO measurement

---

### Phase 3 — Deploy to Kubernetes (`main/`)

Create two Kind clusters and deploy the full stack:

```bash
# Create both clusters
./solution/scripts/setup-clusters.sh

# Install Velero on both
./solution/scripts/install-velero.sh

# Build and load the image
cd app && docker build -t regionwatch:v1 .
kind load docker-image regionwatch:v1 --name primary
kind load docker-image regionwatch:v1 --name secondary

# Deploy to primary
kubectl --context kind-primary  apply -f solution/k8s/ -n dr-system

# Deploy to secondary
kubectl --context kind-secondary apply -f solution/k8s/ -n dr-system
```

**Skills:** Multi-cluster kubectl, Kind, Velero install, StatefulSets, manifests

---

### Phase 4 — Configure Backup & Restore

Create scheduled backups and test restoring:

```bash
# Create a manual backup
velero --kubecontext kind-primary backup create dr-test-1 \
  --include-namespaces dr-system --wait

# Full DR test: delete + restore
./solution/scripts/restore.sh dr-test-1
```

**Skills:** Velero, MinIO, RPO calculation, backup lifecycle

---

### Phase 5 — Test Failover

```bash
# Dry run first (see what would happen)
./solution/scripts/failover.sh --dry-run

# Real failover (primary → secondary)
./solution/scripts/failover.sh

# Verify the whole stack
./solution/scripts/verify-dr.sh
```

**Skills:** Failover procedures, RTO measurement, runbook execution

---

### Phase 6 — Set Up Monitoring

Install the Prometheus + Grafana stack and import the custom DR dashboard:

```bash
helm --kube-context kind-primary install prometheus \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=admin

kubectl --context kind-primary apply -f solution/monitoring/prometheus-rules.yaml -n monitoring
```

Then import `solution/monitoring/grafana-dashboard.json` into Grafana.

**Skills:** Prometheus, Grafana, custom alerting rules, SLO/SLA monitoring

---

### Phase 7 — GitLab CI Pipeline

Automate deployment and nightly DR testing using `solution/gitlab-ci/.gitlab-ci.yml`.

Configure these variables in GitLab CI/CD settings:
- `KUBE_CONFIG_PRIMARY` — base64 kubeconfig for primary
- `KUBE_CONFIG_SECONDARY` — base64 kubeconfig for secondary

**Skills:** GitLab CI, multi-environment pipelines, scheduled DR tests

---

## Key Concepts You'll Master

| Concept | What you'll do |
|---------|----------------|
| **RTO** (Recovery Time Objective) | Measure time from failure to recovery — your failover scripts time this |
| **RPO** (Recovery Point Objective) | Measure max data loss — determined by backup frequency (15 min = 15 min RPO) |
| **Warm Standby** | Secondary runs at reduced capacity, scales up on failover |
| **Active/Passive** | Only one region serves traffic at a time — simpler, slightly slower RTO |
| **Velero** | Kubernetes-native backup tool — backs up namespaces to S3 |
| **MinIO** | S3-compatible local storage — Velero target without needing AWS |
| **nginx failover** | Flip upstream in nginx.conf + reload = near-instant traffic switch |

---

## Prerequisites

- Docker & Docker Compose (Phase 2)
- `kind` — Kubernetes in Docker (Phase 3+)
- `kubectl` (Phase 3+)
- `helm` (Phase 6)
- `velero` CLI (Phase 4+)
- Basic Kubernetes knowledge (Deployments, Services, Namespaces)

---

## The Project vs. Project 09

| | Project 09 | Project 11 |
|--|--|--|
| Clusters | 1 cluster | **2 separate clusters** |
| Scope | Single-region backup/restore | **Multi-region active/standby** |
| Failover | Manual restore runbook | **Automated failover scripts** |
| Traffic routing | Not covered | **nginx upstream switching** |
| Chaos testing | LitmusChaos | Manual simulation + DR scripts |
| Complexity | Medium | **Advanced** |

---

## Start Here

**→ Go to [app/README.md](./app/README.md) to understand the RegionWatch application.**

Then: `app/` → `local/` → `main/`

Reference solution (for when you're stuck): `solution/`
