# YAML Files Explanation - StatefulSet Recovery Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 🗄️ statefulset.yaml

### What is a StatefulSet?
A StatefulSet manages stateful applications that require stable, unique network identities and persistent storage. Unlike Deployments (for stateless apps), StatefulSets guarantee ordered deployment, scaling, and stable pod names that persist across restarts.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
```
**What it is:** The API version for StatefulSet resources
**Options:** `apps/v1` is the current stable version
**Why:** StatefulSets are part of the `apps` API group (same as Deployments)

```yaml
kind: StatefulSet
```
**What it is:** Declares this is a StatefulSet resource
**When to use StatefulSet vs Deployment:**
- **StatefulSet:** Databases, distributed systems, anything needing stable identity
- **Deployment:** Web servers, APIs, stateless microservices
- **DaemonSet:** One pod per node (monitoring, logging)
- **Job/CronJob:** Batch processing, scheduled tasks

**Key StatefulSet features:**
- Stable, unique pod names (pod-0, pod-1, pod-2)
- Ordered, graceful deployment and scaling (0→1→2)
- Ordered, automated rolling updates
- Stable persistent storage via PVC templates
- Stable network identity via headless service

```yaml
metadata:
  name: recovery-demo-db
  namespace: scenarios
```
**What it is:** StatefulSet metadata
- `name`: StatefulSet name (used to generate pod names: `recovery-demo-db-0`, `recovery-demo-db-1`, etc.)
- `namespace`: Logical grouping for resources

**Pod naming pattern:**
```
<statefulset-name>-<ordinal>
recovery-demo-db-0  ← Always first, must be Running before others start
recovery-demo-db-1  ← Second
recovery-demo-db-2  ← Third
```

**Critical:** Pod names are **stable** - if `recovery-demo-db-1` is deleted, it's recreated with the **same name**, not a random name like Deployments.

```yaml
spec:
  serviceName: recovery-demo-headless
```
**What it is:** Name of the headless Service governing this StatefulSet
**Critical:** This service **must exist** before the StatefulSet is created
**Why:** Provides DNS entries for individual pods

**DNS resolution with headless service:**
```
Individual pod DNS:
recovery-demo-db-0.recovery-demo-headless.scenarios.svc.cluster.local
recovery-demo-db-1.recovery-demo-headless.scenarios.svc.cluster.local

Headless service DNS (returns all pod IPs):
recovery-demo-headless.scenarios.svc.cluster.local
```

**Use cases:**
- Database replication (connect to specific pod, not load-balanced)
- Leader election (apps need to find specific pods)
- Peer discovery (pods need to know about each other)

```yaml
  replicas: 3
```
**What it is:** Desired number of pod replicas
**Options:** Any integer ≥ 0
**Behavior:** Unlike Deployments, StatefulSet creates pods **sequentially**:
1. Creates `recovery-demo-db-0`, waits for Running & Ready
2. Creates `recovery-demo-db-1`, waits for Running & Ready
3. Creates `recovery-demo-db-2`, waits for Running & Ready

**Scale-up:** Always sequential (0→1→2→3→4...)
**Scale-down:** Reverse order (4→3→2→1→0...)

**Why ordered creation?**
- Databases often require primary to be ready before replicas
- Distributed systems need leader election
- Prevents split-brain scenarios

```yaml
  selector:
    matchLabels:
      app: recovery-demo
```
**What it is:** How the StatefulSet finds its pods
**Critical:** Must match `template.metadata.labels` exactly
**Why:** StatefulSet uses this to identify which pods it manages

**⚠️ Common mistake:** Selector and template labels don't match → StatefulSet can't find pods → 0/3 pods ready

```yaml
  template:
    metadata:
      labels:
        app: recovery-demo
```
**What it is:** Pod template - blueprint for creating pods
**Labels:** Must include all selector labels (can have additional labels)

**Important:** Changing template labels requires **deleting and recreating** the StatefulSet (can't update selector on existing StatefulSet)

```yaml
    spec:
      containers:
      - name: postgres
        image: postgres:13-alpine
```
**What it is:** Container specification
- `name`: Container name within pod (for `kubectl exec`, `kubectl logs`)
- `image`: Docker image to run

**About this image:**
- `postgres:13-alpine` - PostgreSQL 13 on lightweight Alpine Linux
- Official PostgreSQL image
- Alpine variant is smaller (~150MB vs ~300MB for full image)

**Image best practices:**
- ✅ Pin specific versions: `postgres:13-alpine` (reproducible)
- ❌ Avoid `:latest` tag (can break deployments, not reproducible)
- ✅ Use official images from trusted registries
- ✅ Consider specific patch versions for production: `postgres:13.8-alpine`

```yaml
        ports:
        - containerPort: 5432
```
**What it is:** Port the container exposes
**PostgreSQL default port:** 5432
**Why declare:** Documentation and service discovery (doesn't actually open the port)

**Options:**
```yaml
ports:
- containerPort: 5432
  name: postgres     # Named port (can reference in Service)
  protocol: TCP      # TCP (default) or UDP
```

```yaml
        env:
        - name: POSTGRES_PASSWORD
          value: "demo-password"
```
**What it is:** Environment variables passed to the container
**PostgreSQL requirements:**
- `POSTGRES_PASSWORD` is **required** (or `POSTGRES_HOST_AUTH_METHOD=trust` for no auth)
- Sets the password for the `postgres` superuser

**⚠️ Production warning:** Never hardcode passwords in YAML!
**Better approach - use Secrets:**
```yaml
env:
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: postgres-secret
      key: password
```

**Other common PostgreSQL env vars:**
```yaml
env:
- name: POSTGRES_USER          # Custom superuser name (default: postgres)
  value: "myuser"
- name: POSTGRES_DB            # Create database on startup
  value: "myapp"
- name: POSTGRES_INITDB_ARGS   # Args for initdb
  value: "--encoding=UTF8"
```

```yaml
        - name: PGDATA
          value: "/data/pgdata"
```
**What it is:** PostgreSQL data directory location
**Default:** `/var/lib/postgresql/data`
**Why change:** Best practice to use subdirectory of mount point

**Why this matters:**
- PostgreSQL requires PGDATA to be an empty directory
- If you mount PVC at `/data`, it may contain `lost+found` directory
- Using `/data/pgdata` avoids conflicts

**Common issue without PGDATA:**
```
initdb: directory "/data" exists but is not empty
```

```yaml
        volumeMounts:
        - name: data
          mountPath: /data
```
**What it is:** Mounts a volume into the container filesystem
- `name`: References volume name from `volumeClaimTemplates` (must match)
- `mountPath`: Where to mount inside container (`/data` in this case)

**How it works:**
1. StatefulSet creates PVC from `volumeClaimTemplates` (named `data-recovery-demo-db-0`)
2. PVC provisions a PersistentVolume (PV)
3. Volume is mounted at `/data` inside container
4. PostgreSQL writes data to `/data/pgdata`
5. Data persists even if pod is deleted

**Volume mount options:**
```yaml
volumeMounts:
- name: data
  mountPath: /data
  subPath: pgdata           # Mount specific subdirectory
  readOnly: false           # Default: false (read-write)
```

```yaml
  volumeClaimTemplates:
  - metadata:
      name: data
```
**What it is:** Template for creating PersistentVolumeClaims (PVCs)
**Critical for StatefulSets:** This is how each pod gets its own persistent storage

**How it works:**
- StatefulSet creates one PVC per pod using this template
- PVC name format: `<template-name>-<statefulset-name>-<ordinal>`
- Examples:
  - `data-recovery-demo-db-0` (pod 0's storage)
  - `data-recovery-demo-db-1` (pod 1's storage)
  - `data-recovery-demo-db-2` (pod 2's storage)

**Persistence behavior:**
- ✅ PVCs persist when pods are deleted (data survives)
- ✅ PVCs persist when StatefulSet is scaled down
- ✅ Recreated pods reattach to same PVC (data reappears!)
- ❌ PVCs are **NOT** deleted when StatefulSet is deleted (must delete manually)

**Why PVCs persist:**
- Protect data from accidental deletion
- Allow safe scaling operations
- Enable data recovery after disasters

```yaml
    spec:
      accessModes: ["ReadWriteOnce"]
```
**What it is:** How the volume can be mounted
**Options:**
1. **ReadWriteOnce (RWO)** - Used here
   - Volume can be mounted read-write by **one node only**
   - Most common for databases
   - Supported by most storage providers (EBS, GCE PD, local storage)

2. **ReadOnlyMany (ROX)**
   - Volume can be mounted read-only by **multiple nodes**
   - Use case: Shared config files, static content

3. **ReadWriteMany (RWX)**
   - Volume can be mounted read-write by **multiple nodes**
   - Use case: Shared file systems (NFS, CephFS, GlusterFS)
   - **Not supported** by block storage (EBS, GCE PD)

**Why ReadWriteOnce for databases?**
- Databases must have exclusive access (can't share disk with another instance)
- Prevents data corruption from concurrent writes
- Most cloud block storage only supports RWO

**⚠️ Important:** If pod moves to different node, volume must be detached from old node and attached to new node (can cause delays)

```yaml
      resources:
        requests:
          storage: 1Gi
```
**What it is:** Amount of storage requested for each PVC
**Units:**
- `Gi` = Gibibyte (1024³ bytes) - binary, recommended
- `G` = Gigabyte (1000³ bytes) - decimal
- `Mi` = Mebibyte (1024² bytes)
- `Ti` = Tebibyte (1024⁴ bytes)

**Why 1Gi for this demo?**
- Small enough for local testing (Kind, Minikube)
- Sufficient for PostgreSQL + test data
- Doesn't consume too much disk space

**Production considerations:**
- **Small database:** 10Gi - 50Gi
- **Medium database:** 100Gi - 500Gi
- **Large database:** 1Ti - 10Ti+
- **Rule of thumb:** Request 2-3x your expected data size for growth

**Storage provisioning:**
```
1. StatefulSet creates PVC requesting 1Gi
2. PVC triggers dynamic provisioning (if StorageClass configured)
3. Storage provider creates 1Gi PersistentVolume
4. PVC binds to PV
5. Volume mounted into pod
```

**Can you resize later?**
- ✅ Yes, if StorageClass supports `allowVolumeExpansion: true`
- ⚠️ Only **increase** size (can't shrink)
- Some storage types require pod restart after resize

**Example resize:**
```bash
kubectl patch pvc data-recovery-demo-db-0 -n scenarios \
  -p '{"spec":{"resources":{"requests":{"storage":"5Gi"}}}}'
```

---

## 🌐 service.yaml (Headless Service)

### What is a Headless Service?
A headless service (clusterIP: None) doesn't provide load balancing or a single service IP. Instead, it returns DNS records pointing directly to the pod IPs, allowing direct pod-to-pod communication.

### YAML Structure Breakdown:

```yaml
apiVersion: v1
```
**What it is:** Core Kubernetes API (v1)
**Why:** Services are fundamental, part of core API (not apps/v1)

```yaml
kind: Service
```
**What it is:** Declares this is a Service resource
**Purpose:** For StatefulSets, provides stable DNS for individual pods

```yaml
metadata:
  name: recovery-demo-headless
  namespace: scenarios
```
**What it is:** Service metadata
- `name`: DNS name for the service (must match `serviceName` in StatefulSet)
- `namespace`: Must match the StatefulSet namespace

**Critical:** This name must match `spec.serviceName` in the StatefulSet YAML!

```yaml
spec:
  clusterIP: None  # Headless service
```
**What it is:** Service type - headless (no ClusterIP)
**Critical:** `clusterIP: None` makes this a **headless service**

### Headless vs Normal Service:

**Normal Service (ClusterIP):**
```yaml
spec:
  type: ClusterIP  # or omit (default)
  # Gets assigned IP like 10.96.45.123
```
- ✅ Load balances traffic across all pods
- ✅ Single stable IP address
- ✅ Good for stateless apps
- ❌ Can't address individual pods
- DNS returns service IP

**Headless Service (clusterIP: None):**
```yaml
spec:
  clusterIP: None  # Headless
```
- ✅ Can address individual pods directly
- ✅ DNS returns all pod IPs
- ✅ Required for StatefulSet pod DNS
- ❌ No load balancing
- ❌ No stable service IP

### DNS Behavior Comparison:

**Normal Service:**
```bash
nslookup my-service.default.svc.cluster.local
# Returns: 10.96.45.123 (service IP)
```

**Headless Service:**
```bash
nslookup recovery-demo-headless.scenarios.svc.cluster.local
# Returns:
# 10.244.1.5 (recovery-demo-db-0 IP)
# 10.244.2.8 (recovery-demo-db-1 IP)
# 10.244.1.9 (recovery-demo-db-2 IP)
```

**Individual pod DNS (only with headless service):**
```bash
nslookup recovery-demo-db-0.recovery-demo-headless.scenarios.svc.cluster.local
# Returns: 10.244.1.5 (specific pod IP)
```

### Why Headless Service for StatefulSets?

**Use case 1: Database replication**
```yaml
# PostgreSQL primary/replica setup
Primary connects to: recovery-demo-db-0.recovery-demo-headless
Replicas connect to primary directly, not load-balanced
```

**Use case 2: Leader election**
```yaml
# Application needs to find leader pod
Leader is always: myapp-0.myapp-headless.default.svc.cluster.local
```

**Use case 3: Peer discovery**
```yaml
# Kafka/Cassandra cluster - pods need to discover each other
Pod 0 discovers Pod 1 at: kafka-1.kafka-headless.default.svc.cluster.local
```

**Use case 4: Direct pod communication**
```yaml
# Stateful distributed system
Each node needs stable DNS name to communicate with specific peers
```

```yaml
  selector:
    app: recovery-demo
```
**What it is:** How Service finds pods to create DNS entries for
**Critical:** Must match pod labels from StatefulSet (`template.metadata.labels`)

**How it works:**
1. Service watches for pods with label `app: recovery-demo`
2. Creates DNS A records for each matching pod
3. Updates DNS when pods are added/removed
4. Provides stable DNS even as pods restart (IP changes, DNS name stays same)

**Check which pods are selected:**
```bash
kubectl get pods -n scenarios -l app=recovery-demo
```

```yaml
  ports:
  - protocol: TCP
    port: 5432
    targetPort: 5432
```
**What it is:** Port configuration
**Fields:**
- `protocol`: TCP (default) or UDP
- `port`: Port for the service (even headless services need this for DNS SRV records)
- `targetPort`: Port the pod containers listen on (PostgreSQL: 5432)

**For headless services:**
- Port is used for **DNS SRV records** (service discovery)
- Not used for load balancing (no load balancing in headless)

**DNS SRV records:**
```bash
dig SRV _postgres._tcp.recovery-demo-headless.scenarios.svc.cluster.local

# Returns SRV records:
# _postgres._tcp.recovery-demo-headless.scenarios.svc.cluster.local. 30 IN SRV 0 33 5432 recovery-demo-db-0...
# _postgres._tcp.recovery-demo-headless.scenarios.svc.cluster.local. 30 IN SRV 0 33 5432 recovery-demo-db-1...
```

**Named ports example:**
```yaml
ports:
- name: postgres
  protocol: TCP
  port: 5432
  targetPort: postgres  # References container port name
```

---

## 🔄 How Everything Works Together

### Complete Flow - StatefulSet Deployment:

1. **Apply headless service first:**
   ```bash
   kubectl apply -f service.yaml
   ```
   - Service controller creates headless service (no ClusterIP assigned)
   - CoreDNS prepared to create pod DNS entries
   - Service watches for pods with label `app: recovery-demo`
   - No pods yet, so no DNS entries created

2. **Apply StatefulSet:**
   ```bash
   kubectl apply -f statefulset.yaml
   ```
   - StatefulSet controller starts creating pods **sequentially**

3. **Pod-0 creation:**
   - Creates `recovery-demo-db-0`
   - Creates PVC `data-recovery-demo-db-0` (1Gi requested)
   - PVC triggers dynamic provisioning → PV created
   - PVC binds to PV
   - Scheduler assigns pod to node
   - Kubelet pulls `postgres:13-alpine` image
   - Volume mounted at `/data`
   - Container starts, PostgreSQL initializes at `/data/pgdata`
   - Pod enters Running state
   - DNS entry created: `recovery-demo-db-0.recovery-demo-headless.scenarios.svc.cluster.local`
   - **Waits for pod to be Ready** before creating next pod

4. **Pod-1 creation:**
   - Once pod-0 is Ready, creates `recovery-demo-db-1`
   - Same process: PVC created, bound, pod scheduled, started
   - DNS entry created: `recovery-demo-db-1.recovery-demo-headless.scenarios.svc.cluster.local`
   - **Waits for Ready** before creating pod-2

5. **Pod-2 creation:**
   - Creates `recovery-demo-db-2`
   - Same process
   - DNS entry created: `recovery-demo-db-2.recovery-demo-headless.scenarios.svc.cluster.local`

6. **Final state:**
   - 3 pods running: `recovery-demo-db-0/1/2`
   - 3 PVCs bound: `data-recovery-demo-db-0/1/2`
   - 3 PVs provisioned and bound
   - DNS fully configured

### Complete Flow - Pod Deletion & Recovery:

7. **Delete pod-0:**
   ```bash
   kubectl delete pod recovery-demo-db-0 -n scenarios
   ```
   - Pod deleted immediately
   - Container stops, pod removed
   - **PVC remains** (not deleted!)
   - DNS entry temporarily points to non-existent IP

8. **StatefulSet recreates pod-0:**
   - Detects pod-0 missing, creates new pod-0
   - **Same name:** `recovery-demo-db-0` (stable identity!)
   - Finds existing PVC: `data-recovery-demo-db-0`
   - **Reattaches same PVC** (data reappears!)
   - Pod scheduled, container starts
   - PostgreSQL finds existing data at `/data/pgdata`
   - **Data intact!** (database comes back with all data)
   - DNS updated with new pod IP

9. **Result:**
   - Pod has new IP, but same DNS name
   - Same PVC reattached
   - Data persisted through pod deletion!

### Complete Flow - Scaling:

10. **Scale down to 1:**
    ```bash
    kubectl scale statefulset recovery-demo-db --replicas=1 -n scenarios
    ```
    - StatefulSet deletes pods in **reverse order**
    - Deletes `recovery-demo-db-2`, waits for termination
    - Deletes `recovery-demo-db-1`, waits for termination
    - Keeps `recovery-demo-db-0`
    - **PVCs remain!** (`data-recovery-demo-db-1` and `data-recovery-demo-db-2` still exist)
    - DNS entries removed for pod-1 and pod-2

11. **Scale up to 3:**
    ```bash
    kubectl scale statefulset recovery-demo-db --replicas=3 -n scenarios
    ```
    - Creates `recovery-demo-db-1` (finds existing PVC, reattaches!)
    - Creates `recovery-demo-db-2` (finds existing PVC, reattaches!)
    - **Data from before scale-down is still there!**

---

## 🎯 Best Practices & Production Recommendations

### 1. Always Use Headless Service with StatefulSets
✅ **Required for stable DNS**
```yaml
# Create service BEFORE StatefulSet
kubectl apply -f service.yaml
kubectl apply -f statefulset.yaml
```

### 2. Set Pod Resource Requests/Limits
✅ **StatefulSets should have resource limits**
```yaml
containers:
- name: postgres
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 2000m
      memory: 2Gi
```
**Why:** Prevents one pod from consuming all node resources

### 3. Use Secrets for Passwords
❌ **Never hardcode passwords:**
```yaml
env:
- name: POSTGRES_PASSWORD
  value: "demo-password"  # BAD!
```

✅ **Use Secrets:**
```yaml
# Create secret
kubectl create secret generic postgres-secret \
  --from-literal=password='SecureP@ssw0rd!'

# Reference in StatefulSet
env:
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: postgres-secret
      key: password
```

### 4. Configure Pod Disruption Budgets (PDB)
✅ **Protect StatefulSets during maintenance**
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: recovery-demo-pdb
spec:
  maxUnavailable: 1      # At most 1 pod down during disruption
  selector:
    matchLabels:
      app: recovery-demo
```

**Why:** Prevents node drain from taking down entire database cluster

### 5. Use Init Containers for Setup
✅ **Prepare environment before PostgreSQL starts**
```yaml
initContainers:
- name: set-permissions
  image: busybox
  command: ['sh', '-c', 'chown -R 999:999 /data']
  volumeMounts:
  - name: data
    mountPath: /data
```

### 6. Add Liveness and Readiness Probes
✅ **Ensure PostgreSQL is healthy**
```yaml
livenessProbe:
  exec:
    command:
    - pg_isready
    - -U
    - postgres
  initialDelaySeconds: 30
  periodSeconds: 10
readinessProbe:
  exec:
    command:
    - pg_isready
    - -U
    - postgres
  initialDelaySeconds: 5
  periodSeconds: 5
```

**Why:**
- Liveness: Restarts pod if PostgreSQL crashes
- Readiness: Prevents traffic to pod until PostgreSQL is ready

### 7. Use StorageClass for Dynamic Provisioning
✅ **Specify storage class in volumeClaimTemplates**
```yaml
volumeClaimTemplates:
- metadata:
    name: data
  spec:
    accessModes: ["ReadWriteOnce"]
    storageClassName: fast-ssd  # Use specific storage class
    resources:
      requests:
        storage: 50Gi
```

**Production storage classes:**
- **AWS:** `gp3`, `io2` (SSD), `st1` (HDD)
- **GCP:** `pd-ssd`, `pd-standard`
- **Azure:** `managed-premium`, `managed-standard`

### 8. Plan for Backups
✅ **StatefulSet data must be backed up**

**Option 1: Volume snapshots**
```bash
# Create VolumeSnapshot
kubectl apply -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: postgres-backup-2024
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: data-recovery-demo-db-0
EOF
```

**Option 2: PostgreSQL pg_dump**
```bash
kubectl exec recovery-demo-db-0 -n scenarios -- \
  pg_dump -U postgres > backup.sql
```

**Option 3: Backup CronJob**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:13-alpine
            command: ["/bin/sh", "-c"]
            args:
            - pg_dump -h recovery-demo-db-0.recovery-demo-headless -U postgres > /backup/backup-$(date +\%Y\%m\%d).sql
            volumeMounts:
            - name: backup
              mountPath: /backup
```

### 9. Monitor StatefulSet Health
✅ **Key metrics to watch**
- Pod count vs desired replicas
- PVC status (bound vs pending)
- Disk usage per PVC
- Pod restart count
- PostgreSQL connection count
- Database replication lag (if using replication)

**Useful commands:**
```bash
# Check StatefulSet status
kubectl get statefulset -n scenarios

# Check PVC status
kubectl get pvc -n scenarios

# Check disk usage
kubectl exec recovery-demo-db-0 -n scenarios -- df -h /data

# Check PostgreSQL connections
kubectl exec recovery-demo-db-0 -n scenarios -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```

### 10. Cleanup Considerations
⚠️ **StatefulSet deletion does NOT delete PVCs**

**Manual cleanup required:**
```bash
# Delete StatefulSet
kubectl delete statefulset recovery-demo-db -n scenarios

# PVCs still exist! Must delete manually:
kubectl delete pvc -l app=recovery-demo -n scenarios

# Or delete individually
kubectl delete pvc data-recovery-demo-db-0 -n scenarios
```

**Why PVCs persist:**
- Prevents accidental data loss
- Allows data recovery after mistakes
- Enables safe StatefulSet updates

**Production:** Always backup before deleting PVCs!

---

## 🔍 Debugging Commands Reference

```bash
# Check StatefulSet status
kubectl get statefulset recovery-demo-db -n scenarios
kubectl describe statefulset recovery-demo-db -n scenarios

# Watch pod creation in real-time
kubectl get pods -n scenarios -l app=recovery-demo -w

# Check individual pod status
kubectl describe pod recovery-demo-db-0 -n scenarios

# Check PVC status
kubectl get pvc -n scenarios
kubectl describe pvc data-recovery-demo-db-0 -n scenarios

# Check PV (PersistentVolume) details
kubectl get pv

# Check headless service
kubectl get svc recovery-demo-headless -n scenarios
kubectl describe svc recovery-demo-headless -n scenarios

# Check service endpoints (should list pod IPs)
kubectl get endpoints recovery-demo-headless -n scenarios

# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup recovery-demo-headless.scenarios.svc.cluster.local

# Test individual pod DNS
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup recovery-demo-db-0.recovery-demo-headless.scenarios.svc.cluster.local

# Check PostgreSQL logs
kubectl logs recovery-demo-db-0 -n scenarios

# Connect to PostgreSQL
kubectl exec -it recovery-demo-db-0 -n scenarios -- psql -U postgres

# Check disk usage
kubectl exec recovery-demo-db-0 -n scenarios -- df -h /data

# View StatefulSet events
kubectl get events -n scenarios --field-selector involvedObject.name=recovery-demo-db --sort-by='.lastTimestamp'

# Force delete stuck pod (use with caution!)
kubectl delete pod recovery-demo-db-0 -n scenarios --force --grace-period=0
```

---

## 🎓 Key Takeaways

1. **StatefulSets provide stable identities** - Pod names persist across restarts (recovery-demo-db-0/1/2)
2. **Ordered creation/deletion** - Pods created sequentially (0→1→2), deleted in reverse (2→1→0)
3. **Headless service required** - Provides stable DNS for individual pods
4. **PVCs persist through everything** - Pod deletion, scale-down, even StatefulSet deletion
5. **Each pod gets own storage** - volumeClaimTemplates create per-pod PVCs
6. **Data survives pod restarts** - Recreated pods reattach same PVC with data intact
7. **Use for stateful apps** - Databases, distributed systems, anything needing stable identity
8. **Always backup** - PVCs persist, but can still be deleted (data loss!)
9. **Set resource limits** - Prevent pods from consuming entire node
10. **Monitor PVC usage** - Disk can fill up, causing PostgreSQL failures

---

## 🚀 Production Checklist

Before deploying StatefulSets to production:

- [ ] Resource requests and limits configured
- [ ] Secrets used for passwords (not hardcoded)
- [ ] Liveness and readiness probes configured
- [ ] PodDisruptionBudget created
- [ ] Backup strategy implemented (snapshots, pg_dump, CronJob)
- [ ] Monitoring and alerts configured
- [ ] StorageClass configured with appropriate performance tier
- [ ] Sufficient storage requested (2-3x expected data size)
- [ ] Headless service created before StatefulSet
- [ ] Tested scale-up/scale-down operations
- [ ] Tested pod deletion and recovery
- [ ] Tested data persistence through restarts
- [ ] Disaster recovery plan documented

---

*This explanation provides comprehensive insights into StatefulSets, persistent storage, and headless services. StatefulSets are powerful but complex - start simple (3 replicas, basic config), then add production features (probes, PDB, backups) as you gain confidence!*
