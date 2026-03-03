# Phase 3 — Deploy to Kubernetes (Multi-Region)

This is where real DR engineering happens.

You will create **two separate Kind clusters** to simulate two geographic regions, deploy the RegionWatch app to both, install Velero for backup/restore, configure cross-cluster traffic routing, and set up RTO/RPO monitoring.

**This folder is intentionally empty** — you build it from scratch.
Use `solution/` as a reference when you're stuck.

---

## Architecture You're Building

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Your Local Machine                               │
│                                                                         │
│   ┌─────────────────────────┐    ┌─────────────────────────────────┐   │
│   │  kind-primary cluster   │    │  kind-secondary cluster         │   │
│   │  (simulates eu-west-1)  │    │  (simulates us-east-1)          │   │
│   │                         │    │                                 │   │
│   │  ┌────────────────────┐ │    │ ┌────────────────────────────┐ │   │
│   │  │ regionwatch (app)  │ │    │ │  regionwatch (app)         │ │   │
│   │  │ role: primary      │ │    │ │  role: secondary           │ │   │
│   │  └────────────────────┘ │    │ └────────────────────────────┘ │   │
│   │  ┌────────────────────┐ │    │ ┌────────────────────────────┐ │   │
│   │  │ PostgreSQL (main)  │ │    │ │ PostgreSQL (replica)       │ │   │
│   │  └────────────────────┘ │    │ └────────────────────────────┘ │   │
│   │  ┌────────────────────┐ │    │                                 │   │
│   │  │     Velero         │◄├────┤►    Velero                     │   │
│   │  └────────────────────┘ │    │ └────────────────────────────┘ │   │
│   └────────────┬────────────┘    └────────────────────────────────┘   │
│                │                                                        │
│   ┌────────────▼────────────┐                                          │
│   │     MinIO (shared)      │  ← S3-compatible backup storage          │
│   │  http://localhost:9000  │     Both Velero instances point here      │
│   └─────────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

Before starting Phase 3:

- [ ] Docker installed and running
- [ ] `kubectl` installed
- [ ] `kind` installed (`brew install kind` or https://kind.sigs.k8s.io/)
- [ ] `helm` installed (`brew install helm` or https://helm.sh/)
- [ ] `velero` CLI installed (`brew install velero` or https://velero.io/docs/)
- [ ] Completed Phase 2 (you understand the app and the 2-region concept)

---

## Phase 3A — Create Two Kind Clusters

### Why two clusters?

In production, "multi-region" means multiple **separate** Kubernetes clusters in different data centres. A single cluster cannot span geographic regions. We simulate this locally with two Kind clusters.

**Step 1: Create the primary cluster**

```bash
kind create cluster --name primary --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF
```

**Step 2: Create the secondary cluster**

```bash
kind create cluster --name secondary --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
EOF
```

**Step 3: Verify both clusters**

```bash
kubectl config get-contexts
# You should see: kind-primary, kind-secondary

kubectl --context kind-primary get nodes
kubectl --context kind-secondary get nodes
```

---

## Phase 3B — Install nginx Ingress on Both Clusters

```bash
# Primary cluster
kubectl --context kind-primary apply -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Secondary cluster
kubectl --context kind-secondary apply -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for both to be ready
kubectl --context kind-primary  -n ingress-nginx wait --for=condition=ready pod \
  -l app.kubernetes.io/component=controller --timeout=120s
kubectl --context kind-secondary -n ingress-nginx wait --for=condition=ready pod \
  -l app.kubernetes.io/component=controller --timeout=120s
```

---

## Phase 3C — Deploy MinIO (shared backup storage)

MinIO runs as a single instance accessible by both clusters. Use the same MinIO from `local/`:

```bash
cd ../local
docker compose up -d minio minio-setup
```

Or deploy it standalone:

```bash
docker run -d \
  --name minio \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  quay.io/minio/minio server /data --console-address ":9001"

# Create the velero bucket
docker exec minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec minio mc mb local/velero
```

---

## Phase 3D — Deploy the App to Both Clusters

### Tasks to complete:

**1. Create namespace on both clusters**

```bash
kubectl --context kind-primary  create namespace dr-system
kubectl --context kind-secondary create namespace dr-system
```

**2. Build and load the Docker image**

Kind clusters don't have internet access to pull the image, so you need to load it:

```bash
cd ../app
docker build -t regionwatch:v1 .

kind load docker-image regionwatch:v1 --name primary
kind load docker-image regionwatch:v1 --name secondary
```

**3. Create K8s manifests — what you need to write:**

For each cluster, create:

| Manifest | Why |
|----------|-----|
| `namespace.yaml` | Isolate the DR stack |
| `configmap.yaml` | `REGION_NAME`, `REGION_ROLE`, `MINIO_ENDPOINT` etc. |
| `secret.yaml` | DB password, MinIO credentials |
| `deployment.yaml` | RegionWatch app (3 replicas on primary, 2 on secondary) |
| `service.yaml` | ClusterIP + NodePort for access |
| `ingress.yaml` | Route `/` to the app |
| `postgres-statefulset.yaml` | PostgreSQL with persistent volume |

**Hint for the Deployment:**

```yaml
# Primary cluster deployment (kind-primary context)
env:
  - name: REGION_NAME
    value: "eu-west-1"
  - name: REGION_ROLE
    value: "primary"
  - name: MINIO_ENDPOINT
    value: "http://host.docker.internal:9000"  # MinIO running on host machine

# Secondary cluster deployment (kind-secondary context)
env:
  - name: REGION_NAME
    value: "us-east-1"
  - name: REGION_ROLE
    value: "secondary"
```

**4. Apply to both clusters**

```bash
kubectl --context kind-primary  apply -f main/k8s/ -n dr-system
kubectl --context kind-secondary apply -f main/k8s/ -n dr-system
```

**5. Verify**

```bash
kubectl --context kind-primary  -n dr-system get pods
kubectl --context kind-secondary -n dr-system get pods

# Access the apps (Kind exposes Ingress on localhost)
curl http://localhost/health                    # primary (default context)
kubectl --context kind-secondary port-forward svc/regionwatch 5900:80 -n dr-system
curl http://localhost:5900/health               # secondary
```

---

## Phase 3E — Install Velero on Both Clusters

Velero backs up Kubernetes resources (PVCs, Deployments, ConfigMaps, etc.) to S3/MinIO.

**1. Get your host machine IP** (MinIO is running there):

```bash
# On Linux/WSL
ip route | grep default | awk '{print $3}'
# e.g. 172.17.0.1
```

**2. Create MinIO credentials file**

```bash
cat > /tmp/credentials-velero <<EOF
[default]
aws_access_key_id = minioadmin
aws_secret_access_key = minioadmin
EOF
```

**3. Install Velero on primary cluster**

```bash
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.9.0 \
  --bucket velero \
  --secret-file /tmp/credentials-velero \
  --use-volume-snapshots=false \
  --backup-location-config \
    region=minio,s3ForcePathStyle=true,s3Url=http://<YOUR-HOST-IP>:9000 \
  --kubeconfig ~/.kube/config \
  --kube-context kind-primary
```

**4. Install Velero on secondary cluster** (same MinIO bucket, different prefix)

```bash
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.9.0 \
  --bucket velero \
  --secret-file /tmp/credentials-velero \
  --use-volume-snapshots=false \
  --backup-location-config \
    region=minio,s3ForcePathStyle=true,s3Url=http://<YOUR-HOST-IP>:9000 \
  --kubeconfig ~/.kube/config \
  --kube-context kind-secondary
```

**5. Verify Velero is ready**

```bash
kubectl --context kind-primary  -n velero get pods
kubectl --context kind-secondary -n velero get pods

velero --kubecontext kind-primary  backup-location get
velero --kubecontext kind-secondary backup-location get
# Should show: "PHASE: Available"
```

---

## Phase 3F — Create Scheduled Backups

```bash
# Backup the dr-system namespace every 15 minutes (primary cluster)
velero --kubecontext kind-primary schedule create dr-system-backup \
  --schedule="*/15 * * * *" \
  --include-namespaces dr-system \
  --ttl 48h0m0s

# Or apply from the YAML in solution/k8s/velero/
kubectl --context kind-primary apply -f solution/k8s/velero/backup-schedule.yaml
```

**Trigger a manual backup to test:**

```bash
velero --kubecontext kind-primary backup create dr-test-backup-1 \
  --include-namespaces dr-system --wait

velero --kubecontext kind-primary backup describe dr-test-backup-1
# Should show: STATUS: Completed
```

---

## Phase 3G — Test Restore on Secondary

This is the real DR test: simulate the primary cluster failing, then restore the backup onto the secondary.

```bash
# 1. Delete everything in dr-system on secondary (simulate fresh cluster after DR)
kubectl --context kind-secondary delete namespace dr-system

# 2. Restore from primary's backup
velero --kubecontext kind-secondary restore create \
  --from-backup dr-test-backup-1 \
  --include-namespaces dr-system \
  --wait

# 3. Verify restore
kubectl --context kind-secondary -n dr-system get pods
# Everything should be running again

# 4. Check the app
kubectl --context kind-secondary port-forward svc/regionwatch 5902:80 -n dr-system
curl http://localhost:5902/health
```

**Measure your RTO:** Time between step 1 and step 3 completing successfully.

---

## Phase 3H — Configure Failover Routing

In production, failover involves updating a DNS record or load balancer rule.
Locally, we simulate this with the nginx from Phase 2 or a `kubectl` context switch.

**Simulate DNS-based failover:**

```bash
# "Switch DNS" — update a local /etc/hosts entry to point to secondary
# Or use the nginx from local/ and change the upstream:
cd ../local
# Edit nginx/nginx.conf: change proxy_pass to point to secondary
docker compose exec nginx nginx -s reload

# Now http://localhost:5858 serves from secondary
curl http://localhost:5858/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('Active:', d['region_name'])"
```

---

## Phase 3I — Set Up Prometheus Monitoring

Apply the monitoring stack to the primary cluster:

```bash
# Install kube-prometheus-stack via Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl --context kind-primary create namespace monitoring

helm --kube-context kind-primary install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.adminPassword=admin \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false

# Apply custom DR alerting rules
kubectl --context kind-primary apply -f solution/monitoring/prometheus-rules.yaml -n monitoring
```

Access Grafana:
```bash
kubectl --context kind-primary -n monitoring port-forward svc/prometheus-grafana 3001:80
# http://localhost:3001  admin/admin
```

Import the dashboard from `solution/monitoring/grafana-dashboard.json`.

---

## Phase 3J — GitLab CI Pipeline

Automate the entire DR deployment pipeline using `solution/gitlab-ci/.gitlab-ci.yml`:

1. On every push to `main`: deploy to primary cluster
2. On every push to `release/*`: deploy to both clusters
3. Scheduled pipeline (nightly): run DR test (backup → delete → restore → verify)

See `solution/gitlab-ci/.gitlab-ci.yml` for the complete pipeline.

---

## Self-Assessment Checklist

When you've completed all phases, you should be able to:

- [ ] Create two Kind clusters and switch between them with `kubectl --context`
- [ ] Deploy the same Docker image to two clusters with different environment variables
- [ ] Install and configure Velero with MinIO as the backup backend
- [ ] Create a manual backup and verify it appears in MinIO
- [ ] Create a scheduled backup (every 15 minutes)
- [ ] Restore a backup to a different cluster
- [ ] Measure RTO (time to restore) and RPO (data age at backup)
- [ ] Perform a manual failover by changing nginx upstream or a K8s Service selector
- [ ] Explain the difference between RTO and RPO to a colleague
- [ ] Explain why Velero does NOT protect against accidental `kubectl delete` in real-time

---

## Stretch Goals

1. **Chaos testing:** Use `kubectl delete pod` to kill pods and verify auto-recovery
2. **Database replication:** Set up real PostgreSQL streaming replication between clusters using `postgres-operator` or manual `pg_basebackup`
3. **Automated failover script:** Write a shell script that checks primary health, triggers failover if unhealthy, and logs the RTO
4. **Velero file-system backup:** Enable `--default-volumes-to-fs-backup` to also back up PVC data
5. **Multi-region Grafana:** Set up Grafana with two Prometheus data sources (one per cluster) on a single dashboard

---

## Reference

All manifests and scripts are in `../solution/`:
```
solution/
├── k8s/           ← Ready-made Kubernetes manifests
├── helm/          ← Velero Helm chart values
├── scripts/       ← setup-clusters.sh, failover.sh, verify-dr.sh
├── monitoring/    ← Prometheus rules + Grafana dashboard JSON
└── gitlab-ci/     ← Full CI/CD pipeline
```
