# Project 11 — Multi-Region Disaster Recovery: Explained

---

## 1. The App

You are deploying **the same application to two separate Kubernetes clusters**, simulating two geographic regions. One cluster is always "active" (serving live traffic), the other is a "warm standby" ready to take over in minutes if the active region fails.

This is how companies like Netflix, Stripe, and GitHub protect against regional cloud outages.

```
                     Users
                       │
               [nginx — simulates DNS/LB]
                       │
         ┌─────────────┴──────────────┐
         │                            │
  kind-primary (eu-west-1)     kind-secondary (us-east-1)
  ● ACTIVE                     ◌ STANDBY
  │                            │
  RegionWatch app (3 pods)     RegionWatch app (2 pods)
  PostgreSQL (main)            PostgreSQL (replica)
  Velero ──────── backup ─────►Velero (restore target)
         │
         ▼
     [MinIO — shared backup storage]
     Both clusters back up here
```

**RegionWatch** is the application: a FastAPI DR dashboard that shows:
- Current region (eu-west-1 or us-east-1)
- Current role (ACTIVE / STANDBY)
- Replication lag from primary
- Incident log and DR event timeline

**Failover flow:**
1. Primary cluster fails (pod kill, node failure, or simulated)
2. Velero backup is available in MinIO (RPO = 15 min max)
3. Secondary already runs the app (warm standby)
4. Operator edits nginx config to route traffic to secondary → RTO < 5 minutes

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-11-multi-region-disaster-recovery/local/

docker compose up --build
```

| UI | URL |
|----|-----|
| Active Region (via nginx) | http://localhost:8080 |
| Primary (eu-west-1) | http://localhost:8081 |
| Secondary (us-east-1) | http://localhost:8082 |
| MinIO Console | http://localhost:9001 (minioadmin / minioadmin) |

**Simulate a failover:**
```bash
# Stop the primary region
docker compose stop app-primary

# Edit nginx.conf to route to secondary
# In local/nginx/nginx.conf:
#   proxy_pass http://app-primary:8000;
# Change to:
#   proxy_pass http://app-secondary:8000;

docker compose exec nginx nginx -s reload

# Verify: http://localhost:8080 now shows "us-east-1 | STANDBY→ACTIVE"
```

### Phase 2 — Deploy to Two Kind Clusters

```bash
cd hands-on-projects/project-11-multi-region-disaster-recovery/main/

# Create two separate Kind clusters
kind create cluster --name primary --config kind-primary-config.yaml
kind create cluster --name secondary --config kind-secondary-config.yaml

# Deploy to primary cluster
kubectl config use-context kind-primary
kubectl apply -f solution/k8s/primary/

# Deploy to secondary cluster
kubectl config use-context kind-secondary
kubectl apply -f solution/k8s/secondary/

# Install Velero on BOTH clusters (pointing to same MinIO)
# Primary cluster
kubectl config use-context kind-primary
velero install --provider aws \
  --bucket velero-dr-backups \
  --backup-location-config s3Url=http://<minio-ip>:9000,s3ForcePathStyle=true \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --secret-file ./velero-credentials \
  --use-volume-snapshots=false

# Secondary cluster
kubectl config use-context kind-secondary
velero install --provider aws \
  --bucket velero-dr-backups \
  --backup-location-config s3Url=http://<minio-ip>:9000,s3ForcePathStyle=true \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --secret-file ./velero-credentials \
  --use-volume-snapshots=false

# Set up scheduled backup on primary (every 15 min for low RPO)
kubectl config use-context kind-primary
velero schedule create region-backup \
  --schedule="*/15 * * * *" \
  --include-namespaces regionwatch \
  --ttl 24h
```

---

## 3. How to Test It

### Verify Active/Standby Status

```bash
# Check primary is active
curl http://localhost:8081/api/status | jq '{region: .region, role: .role}'
# Expected: {"region": "eu-west-1", "role": "ACTIVE"}

# Check secondary is standby
curl http://localhost:8082/api/status | jq '{region: .region, role: .role}'
# Expected: {"region": "us-east-1", "role": "STANDBY"}
```

### PostgreSQL Replication Lag Test

```bash
# Check lag on secondary
docker compose exec postgres-secondary \
  psql -U rw -d regiondb -c \
  "SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;"

# Should be < 1 second in normal operation
# Large lag indicates network or I/O issues
```

### Velero Backup Verification

```bash
# K8s: check backups are being created on schedule
kubectl config use-context kind-primary
velero backup get | head -5

# Verify backup is visible from secondary cluster (shared MinIO)
kubectl config use-context kind-secondary
velero backup get | head -5
# Same backups should be visible here
```

### Full Failover Test (Kubernetes)

```bash
# Step 1: Record current time (disaster starts)
FAILOVER_START=$(date +%s)

# Step 2: Simulate primary cluster failure
kubectl config use-context kind-primary
kubectl delete namespace regionwatch  # Simulate region outage

# Step 3: On secondary, restore from Velero backup
kubectl config use-context kind-secondary
BACKUP=$(velero backup get -o json | jq -r '.items[0].metadata.name')
velero restore create --from-backup $BACKUP

# Step 4: Watch restoration
velero restore describe --last

# Step 5: Promote secondary (update role env var)
kubectl set env deployment/regionwatch-app \
  REGION_ROLE=ACTIVE -n regionwatch

# Step 6: Switch nginx to secondary
# (Update nginx config → reload)

# Step 7: Measure RTO
FAILOVER_END=$(date +%s)
echo "RTO: $((FAILOVER_END - FAILOVER_START)) seconds"
# Goal: < 300 seconds (5 minutes)
```

### RPO Measurement

```bash
# Create data on primary, note the timestamp
curl -X POST http://localhost:8081/api/incidents \
  -d '{"title": "Test incident"}' | jq .created_at

# Wait (backup runs every 15 min)
# Simulate disaster
# After restore, check what data survived

curl http://localhost:8082/api/incidents
# Any incidents created after the last backup are the RPO "loss"
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Kind** | Two separate K8s clusters | `kind create cluster --name primary` and `--name secondary` |
| **Velero** | Cross-cluster backup/restore | Creates namespace snapshots on primary; secondary restores them from shared MinIO |
| **MinIO** | Shared backup storage | Both clusters write to/read from the same MinIO — the shared recovery store |
| **PostgreSQL** | Database with streaming replication | Primary → WAL → Secondary; secondary promotes when primary fails |
| **NGINX** | DNS failover simulation | Edits proxy_pass to switch traffic between clusters; simulates DNS change |
| **RegionWatch (FastAPI)** | DR dashboard app | Reads `REGION_ROLE` env var to display role; shows replication lag, incident log |
| **velero CLI** | Backup/restore operations | `velero backup create`, `velero restore create`, `velero schedule create` |
| **kubectl config use-context** | Multi-cluster management | Switches between kind-primary and kind-secondary contexts |

### Key Multi-Region DR Concepts Practiced

- **Warm standby**: Secondary runs the app at reduced capacity — fast RTO because no cold start
- **RPO vs RTO tradeoff**: More frequent backups = lower RPO but more storage costs
- **Shared backup storage**: Both clusters access MinIO — the bridge between them
- **Database promotion**: Standby PostgreSQL promoted to primary during failover
- **Context switching**: Managing two clusters from one machine using kubeconfig contexts

---

## 5. Troubleshooting

### Secondary not receiving PostgreSQL WAL

```bash
# Check replication slots on primary
docker compose exec postgres-primary \
  psql -U rw -d regiondb -c "SELECT * FROM pg_replication_slots;"

# Check secondary's recovery.conf / postgresql.conf
docker compose exec postgres-secondary \
  psql -U rw -d regiondb -c "SELECT * FROM pg_stat_wal_receiver;"

# Common fix: primary_conninfo in recovery.conf points to wrong host
docker compose exec postgres-secondary \
  cat /var/lib/postgresql/data/postgresql.conf | grep primary_conninfo
```

### Velero backup not visible on secondary cluster

```bash
# Both clusters must point to the same MinIO bucket and path
kubectl config use-context kind-primary
kubectl get backupstoragelocation default -n velero -o yaml | grep bucket

kubectl config use-context kind-secondary
kubectl get backupstoragelocation default -n velero -o yaml | grep bucket
# Must match exactly

# Check Velero can reach MinIO from secondary
kubectl exec -n velero deploy/velero -- \
  curl http://<minio-ip>:9000/velero-dr-backups
```

### Restore fails: "namespace already exists"

```bash
# During restore, if namespace wasn't fully deleted
kubectl delete namespace regionwatch --force --grace-period=0

# Wait for termination to complete
kubectl wait namespace regionwatch --for=delete --timeout=60s

# Then retry restore
velero restore create --from-backup $BACKUP
```

### Kind clusters can't communicate with MinIO

```bash
# MinIO runs outside Kind cluster — get your host IP
ip addr show docker0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1

# Use that IP in Velero's s3Url (not "localhost")
velero install \
  --backup-location-config s3Url=http://172.17.0.1:9000,...

# Verify from inside the cluster
kubectl exec -n velero deploy/velero -- \
  curl http://172.17.0.1:9000
```

### nginx not routing to secondary after config edit

```bash
# Test nginx config syntax
docker compose exec nginx nginx -t

# Reload
docker compose exec nginx nginx -s reload

# Verify with curl (check which region responds)
curl http://localhost:8080/api/status | jq .region
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-11-multi-region-disaster-recovery/local/

docker compose down -v
```

### Kubernetes

```bash
# Delete both clusters entirely
kind delete cluster --name primary
kind delete cluster --name secondary

# Stop MinIO (if running separately via Docker)
docker stop minio && docker rm minio

# Remove Velero credentials file
rm -f ./velero-credentials
```
