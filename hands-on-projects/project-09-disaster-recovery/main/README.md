# Main — Production Kubernetes Deployment

Deploy the DR Operations system to Kubernetes. This phase takes everything you ran locally and turns it into a production-grade, resilient Kubernetes deployment with automated backups, chaos testing, and recovery procedures.

This folder is intentionally **empty** — you build it. The guide below tells you exactly what to create, step by step.

---

## What You'll Build

```
main/
├── namespace.yaml
├── configmap.yaml
├── secret.yaml
├── app/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── ingress.yaml
├── database/
│   ├── statefulset.yaml
│   ├── service.yaml
│   └── pvc.yaml
├── minio/
│   ├── statefulset.yaml
│   ├── service.yaml
│   └── pvc.yaml
└── velero/
    ├── schedule.yaml
    └── restore.yaml
```

Check `../solution/` for the reference implementation once you've tried building it yourself.

---

## Phase 3A — Core Kubernetes Deployment

### Step 1 — Create the Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: dr-lab
  labels:
    project: disaster-recovery
    managed-by: kubectl
```

Apply it:
```bash
kubectl apply -f namespace.yaml
kubectl get namespace dr-lab
```

---

### Step 2 — Create Secrets and ConfigMaps

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: dr-lab
type: Opaque
stringData:
  POSTGRES_USER:     dr
  POSTGRES_PASSWORD: drpassword
  POSTGRES_DB:       dr_primary
---
apiVersion: v1
kind: Secret
metadata:
  name: minio-credentials
  namespace: dr-lab
type: Opaque
stringData:
  MINIO_ACCESS_KEY: minioadmin
  MINIO_SECRET_KEY: minioadmin
```

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: dr-lab
data:
  APP_ENV:       "kubernetes"
  MINIO_ENDPOINT: "http://minio:9000"
  MINIO_BUCKET:   "dr-backups"
```

**DevOps question:** Why is this a `stringData` Secret instead of base64-encoded `data`? What's the difference in practice?

---

### Step 3 — Deploy Primary PostgreSQL as a StatefulSet

StatefulSets guarantee stable pod names (`postgres-primary-0`) and persistent storage. Always use StatefulSets for databases in Kubernetes.

```yaml
# database/statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-primary
  namespace: dr-lab
spec:
  serviceName: postgres-primary
  replicas: 1
  selector:
    matchLabels:
      app: postgres-primary
  template:
    metadata:
      labels:
        app: postgres-primary
        tier: database
        region: primary
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        env:
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: POSTGRES_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: POSTGRES_PASSWORD
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: POSTGRES_DB
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "dr", "-d", "dr_primary"]
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: 256Mi
            cpu: 100m
          limits:
            memory: 512Mi
            cpu: 500m
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: [ReadWriteOnce]
      resources:
        requests:
          storage: 2Gi
```

**Service for the database:**
```yaml
# database/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres-primary
  namespace: dr-lab
spec:
  selector:
    app: postgres-primary
  ports:
  - port: 5432
    targetPort: 5432
  clusterIP: None   # Headless service for StatefulSet
```

**DevOps question:** Why `clusterIP: None`? What is a headless service and when do you use it with StatefulSets?

---

### Step 4 — Deploy Secondary PostgreSQL (DR Region)

Repeat the StatefulSet for the secondary, with name `postgres-secondary` and db `dr_secondary`. The secondary starts empty — it only gets data after a Velero restore.

---

### Step 5 — Deploy MinIO

```yaml
# minio/statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: minio
  namespace: dr-lab
spec:
  serviceName: minio
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
      - name: minio
        image: minio/minio:latest
        command: ["minio", "server", "/data", "--console-address", ":9001"]
        env:
        - name: MINIO_ROOT_USER
          valueFrom:
            secretKeyRef:
              name: minio-credentials
              key: MINIO_ACCESS_KEY
        - name: MINIO_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: minio-credentials
              key: MINIO_SECRET_KEY
        ports:
        - containerPort: 9000
          name: api
        - containerPort: 9001
          name: console
        volumeMounts:
        - name: minio-data
          mountPath: /data
        readinessProbe:
          httpGet:
            path: /minio/health/ready
            port: 9000
          initialDelaySeconds: 10
          periodSeconds: 10
  volumeClaimTemplates:
  - metadata:
      name: minio-data
    spec:
      accessModes: [ReadWriteOnce]
      resources:
        requests:
          storage: 5Gi
```

---

### Step 6 — Deploy the Application

```yaml
# app/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dr-app
  namespace: dr-lab
spec:
  replicas: 2
  selector:
    matchLabels:
      app: dr-app
  template:
    metadata:
      labels:
        app: dr-app
        version: v1
    spec:
      containers:
      - name: dr-app
        image: dr-app:latest     # you'll build and push this
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 4545
        env:
        - name: DATABASE_URL
          value: "postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@postgres-primary:5432/dr_primary"
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: POSTGRES_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: POSTGRES_PASSWORD
        - name: DATABASE_SECONDARY_URL
          value: "postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@postgres-secondary:5432/dr_secondary"
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: minio-credentials
        readinessProbe:
          httpGet:
            path: /health
            port: 4545
          initialDelaySeconds: 15
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 4545
          initialDelaySeconds: 30
          periodSeconds: 30
        resources:
          requests:
            memory: 128Mi
            cpu: 50m
          limits:
            memory: 256Mi
            cpu: 200m
```

Build and load the image into Kind:
```bash
# From the project root
docker build -t dr-app:latest ./app

# Load into Kind cluster (no registry needed)
kind load docker-image dr-app:latest --name kind

# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml configmap.yaml
kubectl apply -f database/
kubectl apply -f minio/
kubectl apply -f app/
```

Verify:
```bash
kubectl -n dr-lab get pods
kubectl -n dr-lab get svc
kubectl -n dr-lab logs -l app=dr-app -f
```

---

## Phase 3B — Install Velero (Backup & Restore)

### Install Velero CLI

```bash
# Download Velero CLI
VELERO_VERSION=v1.13.0
wget https://github.com/vmware-tanzu/velero/releases/download/${VELERO_VERSION}/velero-${VELERO_VERSION}-linux-amd64.tar.gz
tar -xzf velero-${VELERO_VERSION}-linux-amd64.tar.gz
sudo mv velero-${VELERO_VERSION}-linux-amd64/velero /usr/local/bin/

# Verify
velero version --client-only
```

### Install Velero in the Cluster (using Helm)

```bash
# Add Velero Helm repo
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm repo update

# Create MinIO credentials file for Velero
cat > /tmp/velero-credentials.txt << 'EOF'
[default]
aws_access_key_id = minioadmin
aws_secret_access_key = minioadmin
EOF

# Install Velero with MinIO as backend
helm install velero vmware-tanzu/velero \
  --namespace velero \
  --create-namespace \
  --set configuration.backupStorageLocation[0].name=minio \
  --set configuration.backupStorageLocation[0].provider=aws \
  --set configuration.backupStorageLocation[0].bucket=velero \
  --set configuration.backupStorageLocation[0].config.region=minio \
  --set configuration.backupStorageLocation[0].config.s3ForcePathStyle=true \
  --set configuration.backupStorageLocation[0].config.s3Url=http://minio.dr-lab.svc.cluster.local:9000 \
  --set configuration.volumeSnapshotLocation[0].name=minio \
  --set configuration.volumeSnapshotLocation[0].provider=aws \
  --set configuration.volumeSnapshotLocation[0].config.region=minio \
  --set credentials.useSecret=true \
  --set credentials.secretContents.cloud="$(cat /tmp/velero-credentials.txt)"

# Wait for Velero to be ready
kubectl -n velero rollout status deployment/velero
```

### Create a Manual Backup

```bash
# Backup the entire dr-lab namespace
velero backup create dr-lab-manual-01 \
  --include-namespaces dr-lab \
  --wait

# Check backup status
velero backup describe dr-lab-manual-01
velero backup logs dr-lab-manual-01
```

### Schedule Automated Backups

```yaml
# velero/schedule.yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: dr-lab-hourly
  namespace: velero
spec:
  schedule: "0 * * * *"   # Every hour
  template:
    includedNamespaces:
      - dr-lab
    storageLocation: minio
    ttl: 168h0m0s           # Keep backups for 7 days
    snapshotVolumes: true
---
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: dr-lab-daily-full
  namespace: velero
spec:
  schedule: "0 2 * * *"   # 2am daily
  template:
    includedNamespaces:
      - dr-lab
    storageLocation: minio
    ttl: 720h0m0s           # Keep for 30 days
    snapshotVolumes: true
```

```bash
kubectl apply -f velero/schedule.yaml

# List scheduled backups
velero schedule get
```

**DevOps question:** What is the TTL on a Velero backup? What happens when it expires?

---

## Phase 3C — Simulate Disaster and Recover

This is the core learning. Follow these steps carefully and measure your RTO.

### Simulate Primary Region Failure

```bash
# Start a timer
FAILURE_TIME=$(date +%s)
echo "Failure simulated at: $(date)"

# Delete the entire dr-lab namespace (catastrophic failure)
kubectl delete namespace dr-lab

# Verify it's gone
kubectl get namespace dr-lab
# Error: namespace "dr-lab" not found
```

### Restore from Velero Backup

```bash
# List available backups
velero backup get

# Restore from the latest backup
velero restore create dr-lab-restore-01 \
  --from-backup dr-lab-manual-01 \
  --wait

# Check restore status
velero restore describe dr-lab-restore-01
velero restore logs dr-lab-restore-01

# Calculate RTO
RESTORE_TIME=$(date +%s)
RTO_SECONDS=$((RESTORE_TIME - FAILURE_TIME))
echo "RTO: ${RTO_SECONDS} seconds ($(echo "$RTO_SECONDS / 60" | bc) minutes)"
```

### Verify Recovery

```bash
# All pods should be running again
kubectl -n dr-lab get pods

# Data should be intact
kubectl -n dr-lab exec -it $(kubectl -n dr-lab get pod -l app=dr-app -o jsonpath='{.items[0].metadata.name}') -- \
  curl -s http://localhost:4545/api/records | python3 -m json.tool

# Dashboard should show all 10 records
kubectl -n dr-lab port-forward svc/dr-app 4545:4545
# Open http://localhost:4545
```

---

## Phase 3D — Chaos Engineering with LitmusChaos

### Install LitmusChaos

```bash
# Install LitmusChaos via Helm
helm repo add litmuschaos https://litmuschaos.github.io/litmus-helm/
helm repo update

helm install chaos litmuschaos/litmus \
  --namespace litmus \
  --create-namespace \
  --set portal.frontend.service.type=NodePort

# Wait for portal to be ready
kubectl -n litmus get pods -w
```

### Run a Pod Kill Experiment

```yaml
# Apply the chaos experiment (already in solution/k8s/chaos/)
kubectl apply -f ../solution/k8s/chaos/pod-kill.yaml
```

After the experiment:
1. Verify the DR app recovers automatically (K8s restarts the pod)
2. Check how long it takes for the readinessProbe to succeed
3. Record this as your "pod failure RTO"

### Run a Network Chaos Experiment

Simulates a network partition between the app and primary database:
```bash
kubectl apply -f ../solution/k8s/chaos/network-chaos.yaml
```

Observe the dashboard — does it gracefully degrade to the secondary? Does it show an error? This is where the secondary database becomes important.

---

## Phase 3E — Monitoring with Prometheus + Grafana

```bash
# Install kube-prometheus-stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.service.type=NodePort \
  --set grafana.service.nodePort=32300 \
  --values ../solution/helm/prometheus-values.yaml

# Access Grafana
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
# Open http://localhost:3000 (admin/prom-operator)
```

Import the DR dashboard from `../solution/k8s/monitoring/grafana-dashboard.json`.

---

## RTO/RPO Runbook

Document your measurements:

| Metric | Target | Measured | Pass/Fail |
|--------|--------|----------|-----------|
| RPO (hourly backup) | ≤ 60 min | ? | |
| RTO (full namespace restore) | ≤ 15 min | ? | |
| RTO (pod failure + restart) | ≤ 2 min | ? | |
| RTO (DB connection loss + failover) | ≤ 5 min | ? | |

Fill this in as you run through the phases. The goal is to have measurable, documented recovery objectives — not just guesses.

---

## Cloud Migration Path

See `../solution/terraform/` for the Terraform scripts to deploy this exact setup to AWS EKS + S3 instead of Kind + MinIO.

The migration is:
1. Run Terraform → creates EKS cluster + S3 bucket
2. Point `s3Url` in Velero to the S3 bucket endpoint instead of MinIO
3. Change `credentials.secretContents.cloud` to AWS credentials
4. Everything else (schedules, restore procedures, chaos tests) stays identical

This is the power of infrastructure as code — same runbook, different backend.
