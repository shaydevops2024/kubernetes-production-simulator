# YAML Files Explanation - StatefulSet Operations Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 🌐 service.yaml (Headless Service)

### What is a Headless Service?
A headless service (ClusterIP: None) doesn't provide load balancing or a single service IP. Instead, it creates DNS records for each individual pod, allowing direct pod-to-pod communication. This is essential for StatefulSets.

### YAML Structure Breakdown:

```yaml
apiVersion: v1
```
**What it is:** Core Kubernetes API (v1)
**Why:** Services are fundamental resources in the core API group

```yaml
kind: Service
```
**What it is:** Declares this is a Service resource
**Purpose:** Provides network identity for StatefulSet pods

```yaml
metadata:
  name: sts-demo-headless
  namespace: scenarios
```
**What it is:** Service metadata
- `name`: Service name used in DNS records
- `namespace`: Must match StatefulSet namespace

**DNS Pattern for StatefulSet pods:**
```
<pod-name>.<service-name>.<namespace>.svc.cluster.local

Examples:
sts-demo-app-0.sts-demo-headless.scenarios.svc.cluster.local
sts-demo-app-1.sts-demo-headless.scenarios.svc.cluster.local
sts-demo-app-2.sts-demo-headless.scenarios.svc.cluster.local
```

```yaml
spec:
  clusterIP: None
```
**What it is:** Makes this a **headless service**
**Critical:** `clusterIP: None` is required for StatefulSet stable network identities

**What it means:**
- No cluster IP allocated
- No load balancing
- DNS returns individual pod IPs instead of a single service IP
- Each pod gets its own DNS A record

**Comparison:**

| Normal Service | Headless Service |
|----------------|------------------|
| ClusterIP: 10.96.1.5 | ClusterIP: None |
| DNS → Single IP | DNS → All pod IPs |
| Load balanced | Direct pod access |
| Use: Stateless apps | Use: StatefulSets |

**Why headless for StatefulSets?**
- Databases need to connect to specific replicas (primary vs replica)
- Leader election requires stable identities
- Peer discovery in distributed systems (Kafka, Cassandra)

```yaml
  selector:
    app: sts-demo
```
**What it is:** Selects which pods to create DNS records for
**Must match:** StatefulSet's `template.metadata.labels`

**How it works:**
1. Service watches for pods with label `app: sts-demo`
2. For each pod, creates DNS A record
3. Updates DNS when pods are added/removed
4. No load balancing happens

```yaml
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
```
**What it is:** Port configuration
**Note:** For headless services, this is mostly documentation

**Fields:**
- `protocol`: TCP or UDP
- `port`: Port number (less relevant for headless, but required)
- `targetPort`: Container port

**Important:** Even though headless services don't load balance, you still need to define ports for:
- DNS SRV records (service discovery)
- Port forwarding
- Documentation

---

## 📦 statefulset.yaml

### What is a StatefulSet?
A StatefulSet manages stateful applications that require:
- **Stable, unique pod identities** (predictable names)
- **Ordered deployment and scaling** (sequential, not parallel)
- **Stable persistent storage** (PVC per pod that persists)
- **Stable network identities** (consistent DNS names)

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
```
**What it is:** Apps API group, version 1
**Why:** StatefulSet is part of the apps API (like Deployment, DaemonSet)

```yaml
kind: StatefulSet
```
**What it is:** Declares this is a StatefulSet resource
**Alternatives:**
- `Deployment` - For stateless applications (web servers, APIs)
- `DaemonSet` - One pod per node (monitoring agents)
- `Job` - Run-to-completion tasks

```yaml
metadata:
  name: sts-demo-app
  namespace: scenarios
```
**What it is:** StatefulSet metadata
- `name`: StatefulSet name (used as prefix for pod names)
- `namespace`: Logical grouping

**Pod naming convention:**
```
<statefulset-name>-<ordinal>

Examples:
sts-demo-app-0  ← First pod (ordinal 0)
sts-demo-app-1  ← Second pod (ordinal 1)
sts-demo-app-2  ← Third pod (ordinal 2)
```

**Why predictable names matter:**
- Databases identify primary/replica by name
- Configuration files can reference specific pods
- Monitoring knows which pod is which
- Persistent storage binds to specific pod names

```yaml
spec:
  serviceName: sts-demo-headless
```
**What it is:** **CRITICAL** - Name of headless service
**Must match:** The headless Service's `metadata.name`

**Why required:**
- StatefulSet uses this service for DNS records
- Creates stable network identity for each pod
- Without this, pods won't get DNS entries

**DNS created:**
```
Pod FQDN format:
<pod-name>.<serviceName>.<namespace>.svc.cluster.local

Example:
sts-demo-app-0.sts-demo-headless.scenarios.svc.cluster.local
```

**⚠️ Common mistake:** Forgetting to create the headless service first
- StatefulSet will create, but pods won't have DNS
- Many stateful apps (databases) require DNS to work

```yaml
  replicas: 3
```
**What it is:** Desired number of pods
**Behavior:** Pods created **sequentially**, not in parallel

**Ordered creation:**
```
Time 0s:   Create sts-demo-app-0
Time 10s:  sts-demo-app-0 Running → Create sts-demo-app-1
Time 20s:  sts-demo-app-1 Running → Create sts-demo-app-2
Time 30s:  sts-demo-app-2 Running → All ready
```

**vs Deployment (parallel creation):**
```
Time 0s:   Create pod-abc, pod-def, pod-ghi (all at once)
Time 10s:  All running
```

**Why sequential?**
- Databases need primary before replicas
- Leader election requires one pod first
- Safer for distributed systems (quorum formation)

**Scaling behavior:**
- **Scale up:** Adds pods sequentially (3→4→5)
- **Scale down:** Removes pods in reverse order (5→4→3)

```yaml
  selector:
    matchLabels:
      app: sts-demo
```
**What it is:** How StatefulSet finds its pods
**Critical:** Must match `template.metadata.labels` exactly

**Why needed:**
- StatefulSet doesn't create pods directly
- Creates pods with specific labels
- Selector tells StatefulSet which pods it owns

**⚠️ Immutable:** Cannot change after creation! Must delete and recreate StatefulSet.

```yaml
  template:
    metadata:
      labels:
        app: sts-demo
```
**What it is:** Pod template - blueprint for creating pods
**Labels must include:** All selector labels (can have additional ones)

**Why labels matter:**
- StatefulSet selector matches these
- Headless service selector matches these
- Monitoring/logging tools use labels

```yaml
    spec:
      containers:
      - name: nginx
        image: nginx:1.21-alpine
```
**What it is:** Container specification
- `name`: Container name (for kubectl logs/exec)
- `image`: Docker image (pinned version recommended)

**Image best practices:**
- ✅ `nginx:1.21-alpine` - Specific version, small image
- ❌ `nginx:latest` - Unpredictable, can break
- ✅ `nginx:1.21` - Stable version
- ✅ Alpine variants - Smaller, faster pulls

```yaml
        ports:
        - containerPort: 80
```
**What it is:** Port the container listens on
**Purpose:** Documentation and service discovery

**Note:** Containers can listen on any port regardless of this declaration. This is for:
- Kubernetes service discovery
- Network policies
- Documentation for developers

```yaml
        volumeMounts:
        - name: data
          mountPath: /data
```
**What it is:** Mounts a volume into the container
**Critical for StatefulSets:** This is where persistent data is stored

**Fields:**
- `name`: Must match volume name from `volumeClaimTemplates`
- `mountPath`: Directory inside container where volume appears

**How it works:**
1. StatefulSet creates PVC from `volumeClaimTemplates`
2. PVC binds to a PersistentVolume
3. Volume mounted at `/data` in container
4. Data written to `/data` persists beyond pod lifetime

**Example usage inside pod:**
```bash
# Inside container
echo "Hello from sts-demo-app-0" > /data/identity.txt
# This file persists even if pod is deleted and recreated
```

**Why `/data`?**
- Common convention for application data
- Keep separate from OS files (/var, /etc)
- Easy to backup/restore

```yaml
  volumeClaimTemplates:
  - metadata:
      name: data
```
**What it is:** Template for creating PersistentVolumeClaims (PVCs)
**Critical difference from Deployment:** Each pod gets its **own** PVC

**How it works:**
```
StatefulSet with 3 replicas creates:
- PVC: data-sts-demo-app-0 (for pod sts-demo-app-0)
- PVC: data-sts-demo-app-1 (for pod sts-demo-app-1)
- PVC: data-sts-demo-app-2 (for pod sts-demo-app-2)

Each PVC binds to its own PersistentVolume
Each pod has isolated, persistent storage
```

**Naming pattern:**
```
<volumeClaimTemplate.name>-<statefulset-name>-<ordinal>

Examples:
data-sts-demo-app-0
data-sts-demo-app-1
data-sts-demo-app-2
```

**Key behavior:**
- PVCs created automatically when pods are created
- PVCs **persist** when pods are deleted
- When pod recreates, it binds to the **same** PVC
- Data survives pod restarts, crashes, updates

**vs Deployment volumes:**
| StatefulSet | Deployment |
|-------------|------------|
| PVC per pod | Shared PVC (all pods) |
| Isolated storage | Shared storage |
| Data persists with pod identity | Data shared/ephemeral |

```yaml
    spec:
      accessModes: ["ReadWriteOnce"]
```
**What it is:** How the volume can be accessed
**Options:**

1. **ReadWriteOnce (RWO)** - Used here ✅
   - Volume mounted read-write by **one node**
   - Multiple pods on same node can use it
   - **Use case:** Block storage (AWS EBS, GCP PD), most databases
   - **Cloud:** AWS EBS, GCP Persistent Disk, Azure Disk

2. **ReadOnlyMany (ROX)**
   - Volume mounted read-only by **many nodes**
   - **Use case:** Static content, shared read-only data

3. **ReadWriteMany (RWX)**
   - Volume mounted read-write by **many nodes**
   - **Use case:** Shared file systems (NFS, EFS, Azure Files)
   - **Cloud:** AWS EFS, GCP Filestore, Azure Files
   - ⚠️ More expensive, slower

**Why RWO for StatefulSets?**
- Each pod gets its own volume (no sharing needed)
- Better performance (block storage)
- Cheaper than RWX
- Sufficient for most databases

**Important:** RWO means one **node**, not one pod. Multiple pods on the same node can use RWO.

```yaml
      resources:
        requests:
          storage: 1Gi
```
**What it is:** How much storage to request
**Behavior:** Dynamic provisioner creates PV of this size

**Storage units:**
- `Gi` = Gibibyte (1024^3 bytes) - Binary, recommended
- `G` = Gigabyte (1000^3 bytes) - Decimal
- `Mi` = Mebibyte (1024^2 bytes)
- `Ti` = Tebibyte (1024^4 bytes)

**Why 1Gi?**
- Small enough for demo/testing
- Free tier eligible on cloud providers
- Not for production databases!

**Production sizing:**
```yaml
# Development
storage: 1Gi

# Small database
storage: 20Gi

# Medium database
storage: 100Gi

# Large database
storage: 500Gi - 1Ti
```

**Cost consideration:**
- Cloud providers charge per GB-month
- Over-provisioning wastes money
- Under-provisioning causes failures
- Monitor actual usage and resize

**Storage classes:**
```yaml
# Specify storage class (optional)
volumeClaimTemplates:
- metadata:
    name: data
  spec:
    storageClassName: fast-ssd  # Use specific storage class
    accessModes: ["ReadWriteOnce"]
    resources:
      requests:
        storage: 100Gi
```

**Common storage classes:**
- `standard` - HDD, cheap, slow
- `fast` / `ssd` - SSD, expensive, fast
- `premium` - NVMe SSD, very expensive, very fast

---

## 🔄 How StatefulSet Works - Complete Flow

### Initial Deployment:

1. **Apply headless service:**
   ```bash
   kubectl apply -f service.yaml
   ```
   - Service created with ClusterIP: None
   - No pods yet, so no DNS records

2. **Apply StatefulSet:**
   ```bash
   kubectl apply -f statefulset.yaml
   ```
   - StatefulSet controller starts

3. **Ordered pod creation:**
   ```
   t=0s:  Create pod sts-demo-app-0
          Create PVC data-sts-demo-app-0
          Storage provisioner creates PV
          PVC binds to PV
          Kubelet pulls nginx:1.21-alpine
          Mount volume at /data
          Container starts

   t=10s: sts-demo-app-0 becomes Ready
          DNS record created: sts-demo-app-0.sts-demo-headless.scenarios.svc.cluster.local

          Create pod sts-demo-app-1
          Create PVC data-sts-demo-app-1
          (repeat process)

   t=20s: sts-demo-app-1 becomes Ready
          DNS record created

          Create pod sts-demo-app-2
          Create PVC data-sts-demo-app-2
          (repeat process)

   t=30s: sts-demo-app-2 becomes Ready
          All pods running!
   ```

4. **Final state:**
   ```
   Pods:
   - sts-demo-app-0 (Running)
   - sts-demo-app-1 (Running)
   - sts-demo-app-2 (Running)

   PVCs:
   - data-sts-demo-app-0 → Bound to PV
   - data-sts-demo-app-1 → Bound to PV
   - data-sts-demo-app-2 → Bound to PV

   DNS:
   - sts-demo-app-0.sts-demo-headless.scenarios.svc.cluster.local → Pod IP
   - sts-demo-app-1.sts-demo-headless.scenarios.svc.cluster.local → Pod IP
   - sts-demo-app-2.sts-demo-headless.scenarios.svc.cluster.local → Pod IP
   ```

### Pod Deletion & Recreation (Self-Healing):

```bash
# Delete a pod
kubectl delete pod sts-demo-app-1 -n scenarios
```

**What happens:**
```
t=0s:  Pod sts-demo-app-1 deleted
       StatefulSet controller detects missing pod

t=2s:  Create new pod sts-demo-app-1 (SAME NAME!)
       PVC data-sts-demo-app-1 still exists
       New pod binds to SAME PVC
       Data from old pod still there!

t=10s: New sts-demo-app-1 Running
       DNS record updated to new pod IP
       Application data intact!
```

**Key insight:** Pod name stays the same → PVC stays the same → Data persists!

### Scaling Up (3 → 5 replicas):

```bash
kubectl scale statefulset sts-demo-app --replicas=5 -n scenarios
```

**What happens:**
```
Current: sts-demo-app-0, sts-demo-app-1, sts-demo-app-2

t=0s:  Create sts-demo-app-3 (wait for Ready)
t=10s: sts-demo-app-3 Ready
       Create sts-demo-app-4 (wait for Ready)
t=20s: sts-demo-app-4 Ready
       Done!

Final: sts-demo-app-0, sts-demo-app-1, sts-demo-app-2, sts-demo-app-3, sts-demo-app-4
```

**Note:** Sequential, not parallel!

### Scaling Down (5 → 3 replicas):

```bash
kubectl scale statefulset sts-demo-app --replicas=3 -n scenarios
```

**What happens:**
```
Current: sts-demo-app-0, sts-demo-app-1, sts-demo-app-2, sts-demo-app-3, sts-demo-app-4

t=0s:  Delete sts-demo-app-4 (highest ordinal first)
       Wait for termination
t=30s: sts-demo-app-4 terminated
       Delete sts-demo-app-3
t=60s: sts-demo-app-3 terminated
       Done!

Final: sts-demo-app-0, sts-demo-app-1, sts-demo-app-2

PVCs remain:
- data-sts-demo-app-3 (still exists!)
- data-sts-demo-app-4 (still exists!)
```

**⚠️ Important:** PVCs are NOT automatically deleted!
- Data preserved for safety
- Can scale back up and data is still there
- Must manually delete PVCs if no longer needed

**Manual PVC cleanup:**
```bash
kubectl delete pvc data-sts-demo-app-3 -n scenarios
kubectl delete pvc data-sts-demo-app-4 -n scenarios
```

---

## 🎯 StatefulSet vs Deployment - When to Use Which?

### Use StatefulSet When:

✅ **Application needs stable identity**
- Databases (MySQL, PostgreSQL, MongoDB)
- Message brokers (Kafka, RabbitMQ)
- Distributed systems (Zookeeper, etcd, Cassandra)

✅ **Application needs persistent storage per instance**
- Each instance stores unique data
- Data must survive pod restarts

✅ **Application needs ordered deployment**
- Primary/replica setup (master first, then replicas)
- Quorum-based systems (need majority before starting more)

✅ **Application needs stable DNS names**
- Peers discover each other by name
- Configuration references specific pods

### Use Deployment When:

✅ **Stateless applications**
- Web servers (Nginx, Apache)
- REST APIs (Node.js, Python, Go)
- Microservices

✅ **Any pod is interchangeable**
- No pod is special
- Traffic can go to any pod

✅ **No persistent storage needed (or shared storage)**
- Ephemeral data
- Shared ReadWriteMany volume

✅ **Want fast parallel scaling**
- Scale 2→10 instantly
- No ordering needed

---

## 📊 Best Practices & Production Recommendations

### 1. Always Use Headless Service
```yaml
# Required for StatefulSet DNS
apiVersion: v1
kind: Service
metadata:
  name: myapp-headless
spec:
  clusterIP: None  # Critical!
  selector:
    app: myapp
```

### 2. Set Pod Management Policy (Optional)
```yaml
spec:
  podManagementPolicy: OrderedReady  # Default - sequential
  # OR
  podManagementPolicy: Parallel      # Faster, but less safe
```

**OrderedReady** (default):
- ✅ Safe for databases
- ✅ One pod at a time
- 🐌 Slower scaling

**Parallel:**
- ⚡ Fast scaling
- ⚠️ Risky for databases
- ✅ OK for some stateful apps (Elasticsearch)

### 3. Set Update Strategy
```yaml
spec:
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      partition: 0  # Update all pods
```

**partition:**
- `partition: 2` → Only update pods with ordinal ≥ 2
- **Use case:** Canary updates (test new version on subset)

```yaml
# Canary example
partition: 2
# sts-demo-app-0, sts-demo-app-1 stay old version
# sts-demo-app-2, sts-demo-app-3, sts-demo-app-4 get new version
```

### 4. Configure PodDisruptionBudget
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: sts-demo-pdb
spec:
  minAvailable: 2  # At least 2 pods must be available
  selector:
    matchLabels:
      app: sts-demo
```

**Why?**
- Prevents node drain from killing all pods
- Ensures quorum during maintenance
- Required for high availability

### 5. Resource Requests/Limits
```yaml
containers:
- name: nginx
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi
```

**Important for StatefulSets:**
- Ensures consistent performance per replica
- Prevents resource starvation
- Helps scheduler place pods on appropriate nodes

### 6. Set Termination Grace Period
```yaml
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 60
```

**Why?**
- Databases need time to flush buffers
- Graceful shutdown prevents data corruption
- Default 30s often too short for databases

### 7. Use Storage Classes Explicitly
```yaml
volumeClaimTemplates:
- spec:
    storageClassName: fast-ssd  # Don't rely on default
    accessModes: ["ReadWriteOnce"]
    resources:
      requests:
        storage: 100Gi
```

**Why?**
- Default storage class may change
- Different apps need different performance
- Explicit is better than implicit

### 8. Backup Strategy for PVCs
```yaml
# Use VolumeSnapshot (if supported)
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: sts-demo-app-0-snapshot
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: data-sts-demo-app-0
```

**Or use tool-based backups:**
- Velero (cluster backup/restore)
- Cloud provider snapshots (AWS EBS, GCP PD)
- Application-level backups (mysqldump, pg_dump)

---

## 🔍 Debugging Commands

```bash
# Get StatefulSet status
kubectl get statefulset sts-demo-app -n scenarios

# Watch pod creation in real-time
kubectl get pods -n scenarios -w -l app=sts-demo

# Describe StatefulSet (see events)
kubectl describe statefulset sts-demo-app -n scenarios

# Check PVCs
kubectl get pvc -n scenarios

# See which PVC is bound to which pod
kubectl get pods -n scenarios -o json | \
  jq '.items[] | {pod: .metadata.name, pvcs: .spec.volumes[].persistentVolumeClaim.claimName}'

# Test DNS resolution
kubectl run -it --rm debug --image=busybox -n scenarios -- sh
nslookup sts-demo-app-0.sts-demo-headless.scenarios.svc.cluster.local

# Check pod logs
kubectl logs sts-demo-app-0 -n scenarios

# Exec into pod
kubectl exec -it sts-demo-app-0 -n scenarios -- sh

# See storage usage
kubectl exec sts-demo-app-0 -n scenarios -- df -h /data

# Force delete stuck pod (dangerous!)
kubectl delete pod sts-demo-app-1 -n scenarios --grace-period=0 --force
```

---

## 🚨 Common Issues & Solutions

### Issue 1: Pods stuck in Pending
```bash
$ kubectl get pods -n scenarios
NAME              READY   STATUS    RESTARTS   AGE
sts-demo-app-0   0/1     Pending   0          5m
```

**Causes:**
1. No storage provisioner configured
2. Insufficient node resources
3. PVC can't bind to PV

**Debug:**
```bash
kubectl describe pod sts-demo-app-0 -n scenarios
kubectl get pvc -n scenarios
kubectl describe pvc data-sts-demo-app-0 -n scenarios
```

**Solution:**
- Install storage provisioner (local-path, CSI driver)
- Add more nodes
- Check storage class exists

### Issue 2: PVC stuck in Pending
```bash
$ kubectl get pvc -n scenarios
NAME                      STATUS    VOLUME   CAPACITY   ACCESS MODES
data-sts-demo-app-0      Pending
```

**Causes:**
- No default storage class
- Storage class doesn't exist
- No available PVs (static provisioning)

**Solution:**
```bash
# Check storage classes
kubectl get storageclass

# Set default storage class
kubectl annotate storageclass standard storageclass.kubernetes.io/is-default-class=true
```

### Issue 3: Pod recreated with different PVC
**Symptom:** Data lost after pod deletion

**Cause:** Pod name changed (shouldn't happen with StatefulSet)

**Debug:**
```bash
# Check pod and PVC names match
kubectl get pods -n scenarios
kubectl get pvc -n scenarios
```

### Issue 4: Can't scale down
```bash
$ kubectl scale sts sts-demo-app --replicas=1 -n scenarios
# Stuck at 2 replicas
```

**Cause:** PodDisruptionBudget blocking

**Debug:**
```bash
kubectl get pdb -n scenarios
kubectl describe pdb sts-demo-pdb -n scenarios
```

**Solution:** Adjust PDB `minAvailable` or `maxUnavailable`

---

## 🎓 Key Takeaways

1. **StatefulSets provide stable pod identities** - Predictable names (app-0, app-1, app-2)
2. **Require headless service** - ClusterIP: None for DNS records
3. **Ordered operations** - Sequential creation, deletion, updates
4. **PVC per pod** - Each pod gets isolated persistent storage
5. **PVCs persist** - Even when pods are deleted, PVCs remain
6. **Stable DNS** - Each pod gets its own DNS record
7. **Use for stateful apps** - Databases, message queues, distributed systems
8. **NOT for stateless apps** - Use Deployment for web servers, APIs

---

*This explanation provides deep insights into StatefulSets and how they differ from Deployments. Essential for running databases and stateful applications in Kubernetes!*
