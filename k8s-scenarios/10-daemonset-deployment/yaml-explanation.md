# YAML Files Explanation - DaemonSet Deployment Scenario

This guide explains the DaemonSet YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 📄 daemonset.yaml

### What is a DaemonSet?
A DaemonSet ensures that **exactly one pod runs on every node** (or a subset of nodes) in your Kubernetes cluster. It's perfect for node-level services like logging agents, monitoring exporters, network plugins, and storage daemons.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
```
**What it is:** The API version for DaemonSet resources
**Options:** `apps/v1` is the current stable version
**Why:** DaemonSets are part of the `apps` API group, same as Deployments and StatefulSets

```yaml
kind: DaemonSet
```
**What it is:** Declares this is a DaemonSet resource
**Options:** DaemonSet, Deployment, StatefulSet, Job, CronJob
**Why:** Tells Kubernetes to create a DaemonSet controller that ensures one pod per node
**When to use DaemonSet vs Deployment:**
- DaemonSet: Node-level services (logging, monitoring, networking)
- Deployment: Application workloads with configurable replica counts

```yaml
metadata:
  name: daemonset-demo
  namespace: scenarios
  labels:
    app: daemonset-demo
    scenario: "11"
```
**What it is:** Metadata identifying the DaemonSet
- `name`: Unique identifier within the namespace (used in kubectl commands)
- `namespace`: Where this DaemonSet lives
- `labels`: Key-value pairs for organization and selection

**Naming Options:** Use lowercase alphanumeric + hyphens, must be DNS-compliant
**Why labels?**
- Organize resources (`kubectl get ds -l app=daemonset-demo`)
- Used by monitoring tools, Helm, and other operators
- Help identify resources in large clusters

**Best practices:** Use consistent label keys (`app`, `version`, `environment`, `component`)

---

### Spec Section

```yaml
spec:
  selector:
    matchLabels:
      app: daemonset-demo
```
**What it is:** How the DaemonSet finds its pods
**Critical:** Must match `template.metadata.labels`
**Why:** DaemonSets don't own pods - they select them by labels
**Options:**
- `matchLabels`: Simple equality-based selection (most common)
- `matchExpressions`: Complex logic (In, NotIn, Exists, DoesNotExist)

**⚠️ Common mistake:** Selector and template labels don't match → DaemonSet can't find pods

**Example with matchExpressions:**
```yaml
selector:
  matchExpressions:
  - key: app
    operator: In
    values:
    - daemonset-demo
  - key: tier
    operator: NotIn
    values:
    - frontend
```

---

### Pod Template

```yaml
  template:
    metadata:
      labels:
        app: daemonset-demo
```
**What it is:** Template for creating pods on each node
**Why:** This is the actual pod specification that gets scheduled
**Labels:** Must include all selector labels (can have additional labels)
**Best practice:** Keep labels minimal but descriptive

```yaml
    spec:
      containers:
      - name: fluentd
        image: fluentd:v1.14-1
```
**What it is:** Container specification
- `name`: Container name within the pod (for `kubectl exec`, logs, debugging)
- `image`: Docker image to run on each node

**Image best practices:**
- `fluentd:v1.14-1` - Specific version + variant ✅ (recommended)
- `fluentd:v1.14` - Version without variant ⚠️ (acceptable)
- `fluentd:latest` - ❌ Avoid! Not reproducible, can break unexpectedly
- `fluentd` - ❌ Defaults to :latest (avoid!)

**Why pin versions?** Ensures consistent behavior across all nodes and over time

---

### Resource Management

```yaml
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
```
**What it is:** Resource allocation for the container

**Requests** - Guaranteed resources:
- `cpu: 100m` - 100 millicores (0.1 CPU core) guaranteed
- `memory: 128Mi` - 128 mebibytes (134 MB) guaranteed
- Used by scheduler to decide which node can fit the pod
- Pod won't start if node doesn't have requested resources

**Limits** - Maximum allowed resources:
- `cpu: 200m` - Can burst up to 0.2 CPU cores
- `memory: 256Mi` - Hard limit, pod killed if exceeded (OOMKilled)
- Prevents runaway processes from consuming entire node

**CPU units:**
- `1000m` = 1 CPU core
- `100m` = 0.1 CPU core (10% of one core)
- Can also use decimals: `0.1` = `100m`

**Memory units:**
- `Mi` = Mebibyte (1024^2 bytes) - recommended
- `M` = Megabyte (1000^2 bytes)
- Also: `Gi` (gibibyte), `G` (gigabyte), `Ki` (kibibyte), `K` (kilobyte)

**Why set resources on DaemonSets?**
✅ Prevents one DaemonSet from starving node resources
✅ Essential since DaemonSets run on ALL nodes (can't avoid)
✅ Helps with capacity planning and node sizing
⚠️ Be conservative - DaemonSets multiply resource usage by node count

**Best practices:**
- Start conservative, monitor actual usage, adjust
- For logging/monitoring agents: typically 100-200m CPU, 128-512Mi memory
- Set limits 1.5-2x requests for burstable workloads
- Use `kubectl top pod` to monitor actual usage

---

### Volume Mounts

```yaml
        volumeMounts:
        - name: varlog
          mountPath: /var/log
```
**What it is:** Mounts a volume into the container filesystem
**How it works:**
1. Volume `varlog` (defined in `volumes` section) is mounted at `/var/log` inside the container
2. Container can now read/write to `/var/log`, which actually accesses the node's `/var/log`
3. Perfect for log collection agents like Fluentd

**Parameters:**
- `name`: Must match a volume name in the `volumes` section
- `mountPath`: Directory path inside the container where volume appears

**Advanced options:**
```yaml
volumeMounts:
- name: varlog
  mountPath: /var/log
  readOnly: true           # Prevent container from writing (recommended for logs)
  subPath: pods            # Mount only /var/log/pods, not entire /var/log
  mountPropagation: HostToContainer  # Propagate host mounts into container
```

**Why use volumes?**
- Access node-level data (logs, metrics, host info)
- Share data between containers in the pod
- Persist data beyond pod lifecycle

---

### Volumes - HostPath

```yaml
      volumes:
      - name: varlog
        hostPath:
          path: /var/log
```
**What it is:** Mounts a directory from the **node's filesystem** into the pod
**How it works:**
- `name`: Identifier for this volume (referenced in `volumeMounts`)
- `path`: Absolute path on the host node to mount

**⚠️ Security Warning:** HostPath gives pods access to node filesystem - use with caution!

**Advanced HostPath options:**
```yaml
volumes:
- name: varlog
  hostPath:
    path: /var/log
    type: Directory        # Ensures path exists and is a directory
```

**HostPath Types:**
- `""` (empty) - No checks, create if missing (default, avoid in production)
- `Directory` - Must exist and be a directory (recommended)
- `DirectoryOrCreate` - Create directory if doesn't exist
- `File` - Must exist and be a file
- `FileOrCreate` - Create file if doesn't exist
- `Socket` - Must be a Unix socket
- `CharDevice` - Must be a character device
- `BlockDevice` - Must be a block device

**Common HostPath use cases for DaemonSets:**

1. **Log collection:**
```yaml
hostPath:
  path: /var/log
  type: Directory
```

2. **Container runtime socket (Docker/containerd):**
```yaml
hostPath:
  path: /var/run/docker.sock
  type: Socket
```

3. **Node metrics:**
```yaml
hostPath:
  path: /proc
  type: Directory
```

4. **System information:**
```yaml
hostPath:
  path: /sys
  type: Directory
```

**Security best practices:**
⚠️ Use `readOnly: true` in volumeMounts whenever possible
⚠️ Limit HostPath access to specific directories
⚠️ Use Pod Security Standards to restrict HostPath usage
⚠️ Consider security policies (PSP/PSS/PSA) in production
✅ Set `type` to validate path existence and type

**Alternatives to HostPath:**
- `emptyDir` - Temporary storage, safer but not persistent
- `persistentVolumeClaim` - Persistent storage, managed by cluster
- `configMap` / `secret` - Configuration data
- `nfs` / `csi` - Network-attached storage

---

## 🔄 How DaemonSets Work

### Scheduling Process:

1. **DaemonSet Created** (`kubectl apply -f daemonset.yaml`)
   - DaemonSet controller watches for changes
   - Controller queries cluster for all nodes

2. **Pod Scheduling:**
   - Controller creates one pod per node
   - Pods inherit node name (not randomly scheduled)
   - Pods scheduled even if node is under resource pressure (higher priority)

3. **Node Added to Cluster:**
   - DaemonSet controller detects new node
   - Automatically creates pod on new node
   - No manual intervention needed

4. **Node Removed from Cluster:**
   - Pods on removed node automatically deleted
   - DaemonSet adjusts to new node count

5. **DaemonSet Updated:**
   - Uses `updateStrategy` (RollingUpdate by default)
   - Updates one pod at a time across nodes
   - Ensures logging/monitoring stays operational during updates

### Update Strategies:

```yaml
spec:
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1  # Update 1 node at a time
```

**RollingUpdate** (default):
- Updates pods gradually, one (or few) at a time
- Controlled by `maxUnavailable` (default 1)
- Safe for production

**OnDelete**:
- Pods only updated when manually deleted
- Useful for maintenance windows
- More control, less automation

---

## 🎯 Advanced DaemonSet Features

### 1. Node Selectors (Target Specific Nodes)

```yaml
spec:
  template:
    spec:
      nodeSelector:
        disktype: ssd
        region: us-west
```
**What it does:** Only schedules pods on nodes with matching labels
**Use case:** Run SSD monitoring only on SSD nodes, region-specific logging

### 2. Node Affinity (Advanced Node Selection)

```yaml
spec:
  template:
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: node-role.kubernetes.io/worker
                operator: Exists
```
**What it does:** More flexible node selection with AND/OR logic
**Use case:** Run only on worker nodes, not control-plane

### 3. Tolerations (Run on Tainted Nodes)

```yaml
spec:
  template:
    spec:
      tolerations:
      - key: node-role.kubernetes.io/control-plane
        operator: Exists
        effect: NoSchedule
```
**What it does:** Allows pods to run on tainted nodes (like control-plane)
**Use case:** Monitoring needs to run on control-plane nodes too

### 4. Host Networking

```yaml
spec:
  template:
    spec:
      hostNetwork: true
      hostPID: true
      hostIPC: true
```
**What it does:** Pod uses node's network/PID/IPC namespace
**Use case:** Network plugins, deep system monitoring
**⚠️ Security:** High privilege, use carefully

### 5. Priority Class (Ensure DaemonSet Scheduling)

```yaml
spec:
  template:
    spec:
      priorityClassName: system-node-critical
```
**What it does:** Gives pods high priority, ensures scheduling
**Use case:** Critical system services that must run
**Options:** `system-node-critical`, `system-cluster-critical`

---

## 🐛 Common Mistakes & Debugging

### Mistake 1: Pods not scheduled on all nodes
**Symptom:** `kubectl get ds` shows DESIRED > CURRENT
**Causes:**
- Node taints blocking scheduling
- Insufficient resources on nodes
- NodeSelector doesn't match node labels

**Fix:**
```bash
# Check node taints
kubectl describe nodes | grep -A 5 Taints

# Check if resources are available
kubectl describe nodes | grep -A 10 "Allocated resources"

# Check node labels
kubectl get nodes --show-labels

# Add toleration if needed
tolerations:
- key: node.kubernetes.io/disk-pressure
  operator: Exists
  effect: NoSchedule
```

### Mistake 2: Selector doesn't match pod labels
**Symptom:** DaemonSet shows 0 pods, events show selector errors
**Fix:** Ensure `spec.selector.matchLabels` exactly matches `spec.template.metadata.labels`

### Mistake 3: Resource limits too high
**Symptom:** Pods CrashLoopBackOff or OOMKilled
**Fix:**
```bash
# Check actual usage
kubectl top pods -n scenarios -l app=daemonset-demo

# Adjust limits based on actual usage + 20% buffer
```

### Mistake 4: HostPath doesn't exist
**Symptom:** Pod stuck in ContainerCreating, events show volume mount errors
**Fix:**
```yaml
hostPath:
  path: /var/log
  type: Directory  # Validates path exists
```

### Debugging Commands:

```bash
# Check DaemonSet status
kubectl get daemonset daemonset-demo -n scenarios

# Describe for events and errors
kubectl describe daemonset daemonset-demo -n scenarios

# Check pods on each node
kubectl get pods -n scenarios -l app=daemonset-demo -o wide

# View pod logs
kubectl logs -n scenarios -l app=daemonset-demo --tail=50

# Check pod resource usage
kubectl top pods -n scenarios -l app=daemonset-demo

# Verify node count matches pod count
kubectl get nodes --no-headers | wc -l
kubectl get pods -n scenarios -l app=daemonset-demo --no-headers | wc -l

# Check for scheduling issues
kubectl get events -n scenarios --field-selector involvedObject.kind=DaemonSet

# Exec into a pod for debugging
kubectl exec -it -n scenarios <pod-name> -- sh
```

---

## 📊 DaemonSet vs Deployment Comparison

| Feature | DaemonSet | Deployment |
|---------|-----------|------------|
| **Replicas** | One per node (automatic) | User-specified count |
| **Scheduling** | One pod per node | Distributed across cluster |
| **Scaling** | Scales with nodes | Manual or HPA |
| **Node Affinity** | Can target specific nodes | Scheduler decides |
| **Update Strategy** | RollingUpdate, OnDelete | RollingUpdate, Recreate |
| **Use Case** | Node-level services | Application workloads |
| **Examples** | Logging, monitoring, networking | Web apps, APIs, workers |
| **Priority** | Higher (can schedule under pressure) | Standard |
| **Resource Model** | Per-node resource cost | Cluster-wide resource cost |

---

## 🎯 Real-World DaemonSet Examples

### 1. Fluentd Log Collection
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd
  namespace: kube-system
spec:
  selector:
    matchLabels:
      app: fluentd
  template:
    metadata:
      labels:
        app: fluentd
    spec:
      containers:
      - name: fluentd
        image: fluent/fluentd-kubernetes-daemonset:v1-debian-elasticsearch
        env:
        - name: FLUENT_ELASTICSEARCH_HOST
          value: "elasticsearch.logging.svc.cluster.local"
        resources:
          limits:
            memory: 200Mi
          requests:
            cpu: 100m
            memory: 200Mi
        volumeMounts:
        - name: varlog
          mountPath: /var/log
        - name: containers
          mountPath: /var/lib/docker/containers
          readOnly: true
      volumes:
      - name: varlog
        hostPath:
          path: /var/log
      - name: containers
        hostPath:
          path: /var/lib/docker/containers
```

### 2. Node Exporter (Prometheus Metrics)
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      hostNetwork: true
      hostPID: true
      containers:
      - name: node-exporter
        image: prom/node-exporter:v1.3.1
        args:
        - --path.procfs=/host/proc
        - --path.sysfs=/host/sys
        - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)
        ports:
        - containerPort: 9100
          hostPort: 9100
        volumeMounts:
        - name: proc
          mountPath: /host/proc
          readOnly: true
        - name: sys
          mountPath: /host/sys
          readOnly: true
      volumes:
      - name: proc
        hostPath:
          path: /proc
      - name: sys
        hostPath:
          path: /sys
```

### 3. kube-proxy (Kubernetes Networking)
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: kube-proxy
  namespace: kube-system
spec:
  selector:
    matchLabels:
      k8s-app: kube-proxy
  template:
    metadata:
      labels:
        k8s-app: kube-proxy
    spec:
      hostNetwork: true
      priorityClassName: system-node-critical
      tolerations:
      - operator: Exists
      containers:
      - name: kube-proxy
        image: k8s.gcr.io/kube-proxy:v1.24.0
        command:
        - /usr/local/bin/kube-proxy
        - --config=/var/lib/kube-proxy/config.conf
        volumeMounts:
        - name: kube-proxy
          mountPath: /var/lib/kube-proxy
        - name: xtables-lock
          mountPath: /run/xtables.lock
      volumes:
      - name: kube-proxy
        configMap:
          name: kube-proxy
      - name: xtables-lock
        hostPath:
          path: /run/xtables.lock
          type: FileOrCreate
```

---

## 📚 Further Learning

### Next Steps:
1. **StatefulSets** - Ordered pod deployment with stable network identities
2. **Pod Disruption Budgets** - Ensure availability during node maintenance
3. **Pod Security Standards** - Restrict privileged DaemonSets
4. **Custom Schedulers** - Advanced pod placement
5. **Vertical Pod Autoscaler** - Auto-adjust resource requests

### Related Scenarios:
- **05-services-networking** - Expose DaemonSet pods as Services
- **09-rolling-updates** - Deep dive into update strategies
- **12-node-affinity** - Advanced node selection techniques

### Documentation:
- [Kubernetes DaemonSets](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)
- [Node Affinity](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
- [Taints and Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)

---

*This explanation provides a comprehensive understanding of DaemonSets. Start with basic deployment, then experiment with node selectors, tolerations, and advanced features as you gain confidence!*
