# Project 09 — Disaster Recovery System: Explained

---

## 1. The App

You are building a **production-grade disaster recovery (DR) system** around a real application — a **Critical Operations Dashboard** (FastAPI). The app intentionally stores important operational data in PostgreSQL. Your job is to protect it: set up backups, stream the database to a secondary, inject real failures with a chaos engineering tool, then prove you can recover — and measure exactly how long recovery takes (RTO) and how much data you lose (RPO).

```
Kind Cluster
│
├── Namespace: dr-lab
│   ├── DR App (:4545)       ← FastAPI operations dashboard
│   ├── postgres-primary     ← Primary database
│   └── postgres-secondary   ← Streaming replica (WAL-based)
│
├── Namespace: velero
│   └── Velero               ← K8s backup tool
│         ├── Hourly backup  → MinIO (S3 storage)
│         └── Daily full backup
│
├── Namespace: litmus
│   └── LitmusChaos Portal   ← Chaos engineering platform
│         ├── Pod kill experiments
│         └── Network partition experiments
│
└── Namespace: monitoring
    ├── Prometheus            ← Metrics collection
    └── Grafana               ← RPO/RTO dashboards
```

| Component | Role |
|-----------|------|
| **DR App** | The application being protected — tracks operational events, incidents |
| **postgres-primary** | Primary PostgreSQL — all writes go here |
| **postgres-secondary** | Hot standby — streams WAL from primary; can take over if primary fails |
| **Velero** | K8s-native backup tool — snapshots namespaces, PVCs, and resources to MinIO |
| **MinIO** | S3-compatible object storage — stores Velero backups (simulates AWS S3) |
| **LitmusChaos** | Chaos engineering — injects pod kills, network delays, disk failures |
| **Prometheus + Grafana** | Measures and visualizes RPO/RTO metrics during experiments |

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-09-disaster-recovery/local/

docker compose up --build
```

| UI | URL |
|----|-----|
| DR App Dashboard | http://localhost:4545 |
| MinIO Console | http://localhost:9001 (minioadmin / minioadmin) |
| Primary PostgreSQL | localhost:5432 |
| Secondary PostgreSQL | localhost:5433 |

**Basic workflow:**
1. Open http://localhost:4545 — see the operations dashboard
2. Create some data (incidents, events) via the UI
3. Observe the secondary is already streaming from primary
4. Simulate a primary failure and promote secondary

### Phase 2 — Deploy to Kubernetes

```bash
cd hands-on-projects/project-09-disaster-recovery/main/

# Deploy the DR application
kubectl apply -f solution/k8s/app/

# Deploy MinIO (backup storage)
kubectl apply -f solution/k8s/minio/

# Install Velero
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --bucket velero-backups \
  --secret-file ./credentials-velero \
  --use-volume-snapshots=false \
  --backup-location-config \
    region=minio,s3ForcePathStyle=true,s3Url=http://minio-svc.minio.svc:9000

# Install LitmusChaos
kubectl apply -f https://litmuschaos.github.io/litmus/litmus-operator-v3.3.0.yaml

# Install monitoring
kubectl apply -f solution/k8s/monitoring/

# Create scheduled backup
velero schedule create daily-backup \
  --schedule="0 */1 * * *" \
  --include-namespaces dr-lab \
  --ttl 168h
```

---

## 3. How to Test It

### Verify Database Replication

```bash
# Local: write to primary, verify secondary gets it
docker compose exec postgres-primary \
  psql -U dr_user -d drdb -c "INSERT INTO events VALUES (DEFAULT, 'test event', NOW());"

# Immediately check secondary
docker compose exec postgres-secondary \
  psql -U dr_user -d drdb -c "SELECT * FROM events ORDER BY id DESC LIMIT 1;"
# Should show the same row with very small lag
```

### Velero Backup Test

```bash
# Create a manual backup
velero backup create manual-test-backup \
  --include-namespaces dr-lab

# Check backup status
velero backup describe manual-test-backup

# List all backups
velero backup get

# Verify backup in MinIO
# Open MinIO console: http://localhost:9001
# Navigate to velero-backups bucket
```

### Disaster Simulation — Delete Everything

```bash
# SIMULATE DISASTER: delete the dr-lab namespace
kubectl delete namespace dr-lab

# Verify the app is gone
kubectl get pods -n dr-lab  # Should return: No resources found

# RESTORE from Velero backup
velero restore create --from-backup manual-test-backup

# Watch restoration progress
velero restore describe --last

# Verify the app is back
kubectl get pods -n dr-lab
curl http://localhost:4545/api/events  # Should show all data
```

### RTO/RPO Measurement

```bash
# Start the timer when disaster begins
DISASTER_TIME=$(date +%s)

# Perform restore
velero restore create --from-backup daily-backup-<timestamp>

# Wait until app is healthy
until curl -s http://localhost:4545/health | grep -q "ok"; do sleep 5; done

# Calculate RTO
RECOVERY_TIME=$(date +%s)
echo "RTO: $((RECOVERY_TIME - DISASTER_TIME)) seconds"

# Check what data was lost (RPO = last backup time - disaster time)
velero backup describe daily-backup-<timestamp> | grep StartTimestamp
```

### Chaos Engineering Test (LitmusChaos)

```bash
# Kill the primary database pod (simulates node failure)
kubectl apply -f - <<EOF
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: postgres-chaos
  namespace: dr-lab
spec:
  engineState: "active"
  appinfo:
    appns: dr-lab
    applabel: "app=postgres-primary"
    appkind: deployment
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "30"
EOF

# Watch what happens to the app during primary failure
watch curl -s http://localhost:4545/health

# Observe secondary promotion timing
kubectl logs -n dr-lab deploy/postgres-secondary | grep "promoted"
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Velero** | K8s backup/restore | `velero backup create` snapshots namespaces; `velero restore create` restores them |
| **MinIO** | S3-compatible storage | Velero stores backup archives here; simulates AWS S3 or GCS |
| **PostgreSQL streaming replication** | Database HA | WAL records shipped from primary to secondary in real time |
| **LitmusChaos** | Chaos engineering | Injects controlled failures (pod kill, network partition, disk I/O) to test resilience |
| **Prometheus + Grafana** | DR metrics | Tracks availability, measures RTO and RPO during experiments |
| **velero CLI** | Operations | Create backups, schedules, restores, describe status |
| **kubectl** | K8s operations | Simulate failures, observe recovery, check pod status |

### Key DR Concepts Practiced

- **RPO (Recovery Point Objective)**: Maximum acceptable data loss — "how old can the backup be?"
- **RTO (Recovery Time Objective)**: Maximum acceptable downtime — "how fast can we restore?"
- **Warm standby**: Secondary is running and streaming but not serving traffic — fast failover
- **Velero namespace backup**: Backs up all K8s resources + PVCs in a namespace
- **Chaos engineering**: Deliberately breaking things to prove your recovery works

---

## 5. Troubleshooting

### Velero backup stuck in "InProgress"

```bash
# Check Velero pod logs
kubectl logs -n velero deploy/velero -f

# Check if MinIO is accessible from Velero
kubectl exec -n velero deploy/velero -- \
  curl http://minio-svc.minio.svc:9000/velero-backups

# Common fix: wrong MinIO credentials or bucket doesn't exist
# Check the BackupStorageLocation status
kubectl describe backupstoragelocation default -n velero
```

### Postgres secondary not receiving WAL

```bash
# Check replication status on primary
docker compose exec postgres-primary \
  psql -U dr_user -d drdb -c "SELECT * FROM pg_stat_replication;"
# Should show secondary's connection details

# Check secondary logs for connection errors
docker compose logs postgres-secondary | grep -i "error\|connect"

# Verify pg_hba.conf allows replication connections
docker compose exec postgres-primary cat /etc/postgresql/pg_hba.conf | grep replication
```

### Restore completes but app can't connect to DB

```bash
# The restored pod may use different DB hostnames
kubectl describe pod -n dr-lab -l app=dr-app | grep -A5 env

# Check secrets were restored
kubectl get secret -n dr-lab

# If secrets are missing (Velero may skip some resources):
kubectl apply -f solution/k8s/secrets/  # Reapply manually
```

### LitmusChaos experiment not running

```bash
# Check ChaosEngine status
kubectl describe chaosengine postgres-chaos -n dr-lab

# Check if ServiceAccount has required RBAC
kubectl get rolebinding -n dr-lab | grep litmus

# Common fix: install chaos RBAC
kubectl apply -f https://hub.litmuschaos.io/api/chaos/3.3.0?file=charts/generic/pod-delete/rbac.yaml \
  -n dr-lab
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-09-disaster-recovery/local/

# Stop everything
docker compose down

# Full reset (remove DB data, MinIO backups, checkpoint files)
docker compose down -v
```

### Kubernetes

```bash
# Delete DR app namespace
kubectl delete namespace dr-lab

# Remove Velero and all its backups
velero backup delete --all --confirm
kubectl delete namespace velero

# Remove LitmusChaos
kubectl delete -f https://litmuschaos.github.io/litmus/litmus-operator-v3.3.0.yaml
kubectl delete namespace litmus

# Remove monitoring
kubectl delete namespace monitoring

# Remove MinIO
kubectl delete namespace minio
```
