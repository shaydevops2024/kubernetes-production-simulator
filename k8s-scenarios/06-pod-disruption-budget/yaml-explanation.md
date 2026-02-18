# YAML Files Explanation - Pod Disruption Budget Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 🚀 deployment.yaml

### What is a Deployment?
A Deployment manages a set of identical pods with declarative updates and self-healing. For PDB scenarios, we need multiple replicas to demonstrate availability protection during disruptions.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
```
**What it is:** The API version for Deployment resources
**Options:** `apps/v1` is the current stable version
**Why:** Deployments are part of the `apps` API group (not core v1)

```yaml
kind: Deployment
```
**What it is:** Declares this is a Deployment resource
**Alternatives:**
- `StatefulSet` - For stateful apps (databases, persistent storage)
- `DaemonSet` - One pod per node (logging, monitoring agents)
- `Job` - Run-to-completion tasks
- `ReplicaSet` - Lower-level, prefer Deployment

```yaml
metadata:
  name: pdb-demo-app
  namespace: scenarios
  labels:
    app: pdb-demo
    scenario: "07"
```
**What it is:** Metadata identifying the Deployment

**Fields:**
- `name: pdb-demo-app` - Unique deployment name (used with kubectl)
- `namespace: scenarios` - Logical grouping for resources
- `labels` - Key-value pairs for organization

**Why labels matter:**
- PDB uses labels to select which pods to protect
- Services use labels to route traffic
- Monitoring tools group by labels
- Filter resources: `kubectl get deploy -l app=pdb-demo`

**Best practices:**
- Use consistent label keys: `app`, `version`, `environment`
- Match labels between Deployment, Service, and PDB
- Keep label values alphanumeric

```yaml
spec:
  replicas: 3
```
**What it is:** Number of pod copies to maintain
**Options:** Any integer ≥ 0

**Why 3 replicas for PDB demo?**
- Demonstrates high availability (can lose 1 pod, keep 2 running)
- With `minAvailable: 2`, allows 1 pod to be disrupted
- Shows PDB blocking drain when it would violate budget
- Production: Usually 3-5+ for critical services

**How PDB interacts:**
```
3 replicas + minAvailable: 2 = 1 allowed disruption
5 replicas + minAvailable: 2 = 3 allowed disruptions
2 replicas + minAvailable: 2 = 0 allowed disruptions (blocks drain!)
```

**Scaling impact:**
- More replicas = more disruption budget
- Fewer replicas = stricter availability constraints
- PDB prevents scaling to zero (maintains minAvailable)

```yaml
  selector:
    matchLabels:
      app: pdb-demo
```
**What it is:** How Deployment finds its pods
**Critical:** Must match `template.metadata.labels` exactly

**Why it matters:**
- Deployment creates ReplicaSet, which creates pods
- Selector tells Deployment which pods it manages
- PDB uses same label to protect these pods
- Mismatch = 0/3 pods ready, deployment fails

**Options:**
- `matchLabels` - Simple equality (most common)
- `matchExpressions` - Advanced logic (In, NotIn, Exists)

**Example with matchExpressions:**
```yaml
selector:
  matchExpressions:
  - key: app
    operator: In
    values: [pdb-demo, pdb-demo-v2]
  - key: tier
    operator: NotIn
    values: [test]
```

**⚠️ Common mistake:** Selector doesn't match pod labels → Deployment can't find pods

```yaml
  template:
    metadata:
      labels:
        app: pdb-demo
```
**What it is:** Pod template - blueprint for creating pods
**Critical:** Labels MUST include all selector labels

**Why:**
- This label is what PDB and Service use to select pods
- Deployment uses this to count managed pods
- Changing template labels triggers rolling update

**Best practice:**
- Keep pod labels simple and consistent
- Include at least the app name
- Can add version, tier, component labels

```yaml
    spec:
      containers:
      - name: nginx
        image: nginx:1.21-alpine
```
**What it is:** Container specification

**Fields:**
- `name: nginx` - Container name (for `kubectl logs`, `kubectl exec`)
- `image: nginx:1.21-alpine` - Docker image to run

**Why nginx:1.21-alpine?**
- Lightweight (alpine = small base image)
- Simple web server for demo
- Stable and reliable
- Low resource usage

**Image best practices:**
- ✅ Pin specific version: `nginx:1.21-alpine`
- ❌ Avoid `:latest` tag (not reproducible, risky in production)
- Use official images from trusted registries
- Consider vulnerability scanning

**Alternatives for demos:**
- `nginx:alpine` - Latest alpine
- `httpd:alpine` - Apache web server
- `busybox` - Minimal shell utilities

```yaml
        ports:
        - containerPort: 80
```
**What it is:** Port the container listens on
**Why:** Documentation and discovery (doesn't enforce - container can listen on any port)

**When it matters:**
- NetworkPolicies (restrict traffic to specific ports)
- Service discovery
- Container security scanning
- Other developers reading the config

**Options:**
```yaml
ports:
- containerPort: 80
  name: http          # Named port (Service can reference by name)
  protocol: TCP       # TCP (default) or UDP
```

**Note:** For PDB demo, the port doesn't matter much - we're testing availability, not traffic

```yaml
        resources:
          requests:
            cpu: 100m
            memory: 64Mi
```
**What it is:** Resource requirements and limits

**Requests (guaranteed resources):**
- `cpu: 100m` = 100 millicores = 0.1 CPU cores
- `memory: 64Mi` = 64 mebibytes RAM

**What "requests" means:**
- Kubernetes **guarantees** this much CPU/memory
- Scheduler only places pod on nodes with available resources
- Used for scheduling decisions

**Why these specific values?**
- **100m CPU:** Small for lightweight nginx
- **64Mi memory:** Minimal for nginx without traffic

**CPU units:**
- `1000m` = `1` = 1 full CPU core
- `100m` = 0.1 cores (10% of one core)
- `500m` = 0.5 cores (half a core)

**Memory units:**
- `Mi` = Mebibyte (1024^2 bytes) - **recommended**
- `M` = Megabyte (1000^2 bytes)
- `Gi` = Gibibyte (1024^3 bytes)

**Best practices:**
- Set requests based on actual usage
- Monitor with `kubectl top pod`
- Adjust based on metrics
- Always set both CPU and memory

**For PDB scenarios:**
- Resources ensure pods can be scheduled
- Multiple replicas need node capacity
- Low requests allow running on laptop/Kind cluster

---

## 🛡️ pdb.yaml

### What is a PodDisruptionBudget (PDB)?
A PodDisruptionBudget limits the number of pods that can be **voluntarily** disrupted at once. It protects application availability during:
- Node drains (maintenance)
- Cluster upgrades
- Manual pod deletions
- Evictions

**Does NOT protect against:**
- Hardware failures
- Node crashes
- OOM kills
- Involuntary disruptions

### YAML Structure Breakdown:

```yaml
apiVersion: policy/v1
```
**What it is:** API version for PodDisruptionBudget
**History:**
- `policy/v1beta1` - Deprecated (old Kubernetes)
- `policy/v1` - **Current stable** (Kubernetes 1.21+)

**Why policy group?**
- PDB is a policy resource (sets constraints)
- Not part of core API or apps API
- Part of the policy API group

**Check your cluster version:**
```bash
kubectl version
kubectl api-resources | grep poddisruptionbudget
```

```yaml
kind: PodDisruptionBudget
```
**What it is:** Declares this is a PodDisruptionBudget resource
**Purpose:** Ensures minimum availability during disruptions

**When to use:**
- Production workloads
- Critical services
- High-availability applications
- Services with SLA requirements

**When NOT to use:**
- Single-replica deployments (PDB can't help)
- Batch jobs (no availability requirement)
- Development/test environments (usually)

```yaml
metadata:
  name: pdb-demo
  namespace: scenarios
```
**What it is:** PDB metadata

**Fields:**
- `name: pdb-demo` - PDB identifier (one PDB per app typically)
- `namespace: scenarios` - Must match target pods' namespace

**Naming conventions:**
- Match deployment name: `<app-name>-pdb`
- Descriptive: `frontend-pdb`, `api-pdb`, `database-pdb`
- One PDB per logical application component

**Namespace requirement:**
- PDB and pods MUST be in same namespace
- PDB can't protect pods in other namespaces
- Namespaces provide isolation boundaries

```yaml
spec:
  minAvailable: 2
```
**What it is:** Minimum pods that must remain **available** during disruptions
**This is the MOST IMPORTANT field!**

### 🔑 Understanding minAvailable (Critical!)

**What "available" means:**
- Pod is Running
- Pod has passed readiness probe
- Pod is not terminating

**How it works:**
```
Scenario: Deployment with 3 replicas, PDB with minAvailable: 2

Initial state: 3 pods running
Drain attempt: Would evict 2 pods from Node A
Calculation: 3 current - 2 evicting = 1 remaining
PDB decision: 1 < 2 minAvailable → ❌ BLOCK EVICTION!
Result: "Cannot evict pod as it would violate disruption budget"
```

**Examples:**
```yaml
# Example 1: 3 replicas, minAvailable: 2
replicas: 3
minAvailable: 2
Allowed disruptions: 3 - 2 = 1 pod can be disrupted
Effect: Can drain node with 1 pod, blocks draining node with 2+ pods

# Example 2: 5 replicas, minAvailable: 2
replicas: 5
minAvailable: 2
Allowed disruptions: 5 - 2 = 3 pods can be disrupted simultaneously
Effect: Safer for cluster ops, can drain multiple nodes

# Example 3: 2 replicas, minAvailable: 2
replicas: 2
minAvailable: 2
Allowed disruptions: 2 - 2 = 0
Effect: Blocks ALL disruptions! Must scale up first
```

**Choosing minAvailable:**

**Option 1: Absolute number**
```yaml
minAvailable: 2        # Always keep 2 pods running
```
- ✅ Clear, explicit requirement
- ✅ Good for small, fixed-size deployments
- ❌ Doesn't scale with replica count
- **Use when:** Fixed availability requirement (e.g., "always 2 for HA")

**Option 2: Percentage (alternative)**
```yaml
minAvailable: "50%"    # Keep at least 50% of pods
```
- ✅ Scales with replica count
- ✅ Works with HPA (auto-scaling)
- ❌ Can be confusing with rounding
- **Use when:** Dynamic replica counts, HPA enabled

**Examples with percentages:**
```
3 replicas + 50% minAvailable = 2 pods minimum (ceil(3 * 0.5))
5 replicas + 50% minAvailable = 3 pods minimum (ceil(5 * 0.5))
10 replicas + 50% minAvailable = 5 pods minimum
```

```yaml
  selector:
    matchLabels:
      app: pdb-demo
```
**What it is:** How PDB finds pods to protect
**Critical:** Must match Deployment's pod labels (`template.metadata.labels`)

**How PDB uses selector:**
1. PDB watches for pods with label `app: pdb-demo`
2. Counts how many are available (Running + Ready)
3. When eviction requested, calculates: available - evicting ≥ minAvailable?
4. If yes → allow eviction
5. If no → block eviction

**⚠️ Common mistakes:**

**Mistake 1: Selector doesn't match pod labels**
```yaml
# PDB selector
selector:
  matchLabels:
    app: pdb-demo      # ❌ Wrong!

# Deployment pod labels
template:
  metadata:
    labels:
      app: nginx       # Different label!
```
**Result:** PDB shows "0 Current" → doesn't protect anything

**Mistake 2: Too broad selector (multiple apps)**
```yaml
# PDB selector
selector:
  matchLabels:
    tier: frontend     # Matches BOTH apps!

# Deployment 1 labels: tier=frontend, app=web
# Deployment 2 labels: tier=frontend, app=api
```
**Result:** PDB protects both apps together → unexpected behavior

**Best practice:**
- Use specific label: `app: <app-name>`
- Match exactly one deployment
- Verify with: `kubectl get pods -n scenarios -l app=pdb-demo`

**Advanced selector (multiple labels):**
```yaml
selector:
  matchLabels:
    app: pdb-demo
    tier: frontend
    version: v2
```
**When to use:**
- Protect specific version during rollout
- Separate PDBs for different tiers
- Fine-grained control

---

## 🔄 How PDB and Deployment Work Together

### Complete Flow - Node Drain Scenario:

**Initial State:**
- Deployment: 3 replicas running
- PDB: minAvailable: 2
- Pods distributed: Node A (2 pods), Node B (1 pod)

**Step 1: Admin runs node drain**
```bash
kubectl drain node-a --ignore-daemonsets
```

**Step 2: Drain controller attempts eviction**
- Checks if eviction violates any PDBs
- Queries PDB for `app: pdb-demo` pods
- Counts current available: 3 pods
- Calculates impact: evicting 2 pods → 1 remaining

**Step 3: PDB evaluates**
```
Current available: 3
Pods to evict: 2
Remaining: 3 - 2 = 1
minAvailable: 2
Decision: 1 < 2 → ❌ BLOCK EVICTION!
```

**Step 4: Drain fails**
```
error when evicting pods: Cannot evict pod as it would violate the pod's disruption budget
```

**Step 5: Admin scales up**
```bash
kubectl scale deployment pdb-demo-app --replicas=5 -n scenarios
```
- New state: 5 pods available
- Allowed disruptions: 5 - 2 = 3

**Step 6: Retry drain**
```bash
kubectl drain node-a --ignore-daemonsets
```
- Evicting 2 pods → 3 remaining
- 3 ≥ 2 minAvailable → ✅ ALLOW EVICTION!
- Drain succeeds, pods terminated gracefully
- Remaining 3 pods handle traffic

### Voluntary vs Involuntary Disruptions

**Voluntary (PDB protects):**
- ✅ `kubectl drain` - Node maintenance
- ✅ `kubectl delete pod` - Manual deletion
- ✅ Cluster autoscaler scale-down
- ✅ Deployment rollout (rolling update)

**Involuntary (PDB does NOT protect):**
- ❌ Node hardware failure
- ❌ Node kernel panic / crash
- ❌ Out of memory (OOMKilled)
- ❌ Node power loss
- ❌ `kubectl delete node --force`

**Why the difference?**
- Voluntary: Kubernetes can control timing → check PDB first
- Involuntary: Unplanned, immediate → no time to check PDB
- PDB is about **graceful operations**, not disaster recovery

---

## 🎯 Best Practices & Production Recommendations

### 1. Always Use PDB for Critical Services

✅ **DO set PDB for:**
- API servers
- Databases (with replicas)
- Message queues
- Frontend applications
- Any service with SLA requirements

❌ **DON'T set PDB for:**
- Single-replica deployments (PDB can't help)
- Batch jobs / CronJobs (no availability need)
- Fire-and-forget workers

### 2. Choose minAvailable vs maxUnavailable

**Use minAvailable when:**
- You need absolute minimum (e.g., "always 2 for HA")
- Fixed replica count
- Clear availability requirement

```yaml
spec:
  minAvailable: 2      # At least 2 must stay running
```

**Use maxUnavailable when:**
- You want to express disruption budget
- Dynamic replica counts with HPA
- "Can tolerate 1 pod down"

```yaml
spec:
  maxUnavailable: 1    # Maximum 1 can be down at once
```

**Equivalent configs:**
```yaml
# These are the same with 3 replicas:
minAvailable: 2        # 3 - 2 = 1 allowed disruption
maxUnavailable: 1      # 1 allowed disruption

# With 5 replicas:
minAvailable: 3        # 5 - 3 = 2 allowed disruptions
maxUnavailable: 2      # 2 allowed disruptions
```

**Cannot specify both:**
```yaml
# ❌ INVALID - pick one!
spec:
  minAvailable: 2
  maxUnavailable: 1
```

### 3. Use Percentages for Auto-Scaling Apps

**With HPA (Horizontal Pod Autoscaler):**
```yaml
spec:
  minAvailable: "50%"    # Scales with replica count
```

**Example:**
```
HPA scales: 2 → 4 → 10 replicas
minAvailable: 50% always maintains half
  2 replicas → 1 min (ceil(2 * 0.5))
  4 replicas → 2 min (ceil(4 * 0.5))
  10 replicas → 5 min (ceil(10 * 0.5))
```

**Percentage rounding:**
- Always rounds UP (ceiling)
- `ceil(2.5) = 3`
- Ensures minimum is met

### 4. Test PDB Before Production

**Testing checklist:**
```bash
# 1. Deploy app with PDB
kubectl apply -f deployment.yaml -f pdb.yaml

# 2. Verify PDB is working
kubectl get pdb -n scenarios
# Should show: ALLOWED DISRUPTIONS, CURRENT, DESIRED

# 3. Test drain protection
kubectl drain <node> --ignore-daemonsets --timeout=30s
# Should block if would violate budget

# 4. Scale up and retry
kubectl scale deployment <app> --replicas=5
kubectl drain <node> --ignore-daemonsets
# Should succeed with enough replicas

# 5. Verify pods migrated correctly
kubectl get pods -n scenarios -o wide
```

### 5. Monitor PDB Health

**Check PDB status:**
```bash
# List all PDBs
kubectl get pdb --all-namespaces

# Detailed PDB info
kubectl describe pdb <name> -n <namespace>

# Watch PDB changes
kubectl get pdb -n scenarios -w
```

**Healthy PDB output:**
```
NAME       MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
pdb-demo   2               N/A               1                     5m
```

**Unhealthy PDB indicators:**
- ⚠️ ALLOWED DISRUPTIONS: 0 (too restrictive, blocks all maintenance)
- ⚠️ CURRENT: 0 (selector doesn't match any pods)
- ⚠️ DESIRED: <minAvailable (not enough replicas)

### 6. PDB + Rolling Updates

**During Deployment rollout:**
- Kubernetes respects PDB
- Won't terminate old pods if it would violate budget
- Rollout may be slower but safer

**Example:**
```yaml
# Deployment with 3 replicas
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1    # Deployment's own constraint
      maxSurge: 1          # Can create 1 extra pod

# PDB
spec:
  minAvailable: 2          # PDB's constraint
```

**Rollout behavior:**
1. Creates 1 new pod (maxSurge: 1) → 4 total
2. Waits for new pod to be Ready
3. Terminates 1 old pod → 3 total (respects PDB minAvailable: 2)
4. Repeats until all updated

**Conflict scenario:**
```yaml
# ❌ BAD: Too restrictive
replicas: 3
maxUnavailable: 0    # Deployment can't terminate ANY pods
minAvailable: 3      # PDB requires ALL 3 available

Result: Rollout deadlock! Can't proceed safely
```

**Fix:**
```yaml
# ✅ GOOD: Allows progress
replicas: 3
maxUnavailable: 1    # Can terminate 1 pod
minAvailable: 2      # Keep 2 available

Result: Rollout proceeds smoothly
```

### 7. PDB with Cluster Autoscaler

**Cluster Autoscaler (CA) removes underutilized nodes:**
- CA respects PDB before draining nodes
- Won't drain if would violate PDB
- May leave nodes running to satisfy PDB

**Best practice:**
```yaml
# Set realistic minAvailable
spec:
  minAvailable: 2      # Not too high (wastes nodes)

# Monitor with metrics
kubectl top nodes
kubectl get pdb
```

**Cost optimization:**
- PDB protects availability BUT may prevent cost savings
- Balance: availability vs cluster utilization
- Use `maxUnavailable: 1` instead of `minAvailable: 10` for large deployments

### 8. Common Production Issues

**Issue 1: PDB shows ALLOWED DISRUPTIONS: 0**
```bash
$ kubectl get pdb
NAME       MIN AVAILABLE   ALLOWED DISRUPTIONS
pdb-demo   3               0
```
**Cause:** Not enough replicas (replicas = minAvailable)
**Impact:** Blocks ALL maintenance (can't drain any nodes)
**Fix:** Scale up deployment: `kubectl scale deployment --replicas=5`

**Issue 2: PDB shows CURRENT: 0**
```bash
$ kubectl get pdb
NAME       MIN AVAILABLE   CURRENT   DESIRED
pdb-demo   2               0         2
```
**Cause:** Selector doesn't match any pods
**Debug:**
```bash
# Check pod labels
kubectl get pods -n scenarios --show-labels

# Check PDB selector
kubectl get pdb pdb-demo -n scenarios -o yaml | grep -A5 selector
```
**Fix:** Update PDB selector to match pod labels

**Issue 3: Drain hangs/times out**
```bash
$ kubectl drain node-a --timeout=30s
error: timed out waiting for the condition
```
**Cause:** PDB blocking eviction, insufficient replicas
**Debug:**
```bash
kubectl describe pdb -n scenarios
kubectl get pods -o wide | grep node-a
```
**Fix:** Scale up or temporarily delete PDB (NOT recommended for prod)

**Issue 4: "Forbidden: disruption budget"**
```bash
Error from server (Forbidden): error when evicting pods: Cannot evict pod as it would violate the pod's disruption budget.
```
**Cause:** Working as intended! PDB protecting availability
**Fix:** This is correct behavior. Scale up deployment or wait

---

## 🔍 Advanced Topics

### Multiple PDBs for Same Pods

**Can multiple PDBs select the same pods?**
- ✅ Yes, Kubernetes allows it
- 🔑 ALL PDBs must be satisfied simultaneously
- 🎯 Most restrictive PDB wins

**Example:**
```yaml
# PDB 1: General availability
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: myapp

---
# PDB 2: Zone-specific
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb-zone-a
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: myapp
      zone: zone-a
```

**Result:** Both PDBs must be satisfied for eviction to proceed

**Use case:**
- Multi-zone deployments
- Different availability requirements per tier
- Separate PDBs for blue/green deployments

### PDB with StatefulSets

**StatefulSets + PDB:**
```yaml
# StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: database
spec:
  replicas: 3
  template:
    metadata:
      labels:
        app: database
---
# PDB
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: database-pdb
spec:
  maxUnavailable: 1      # Use maxUnavailable (better for ordered deployments)
  selector:
    matchLabels:
      app: database
```

**Why maxUnavailable for StatefulSets?**
- StatefulSets update sequentially (one pod at a time)
- maxUnavailable: 1 aligns with StatefulSet behavior
- Prevents disrupting multiple pods simultaneously

### PDB with Anti-Affinity

**Combine for ultimate availability:**
```yaml
# Deployment with pod anti-affinity
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 3
  template:
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchLabels:
                app: myapp
            topologyKey: kubernetes.io/hostname    # Spread across nodes
---
# PDB
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: myapp
```

**Benefits:**
- Anti-affinity: Pods spread across different nodes
- PDB: Prevents draining multiple nodes at once
- Combined: Maximum availability during failures and maintenance

---

## 📚 Debugging Commands Reference

```bash
# Check PDB status
kubectl get pdb -n scenarios
kubectl describe pdb pdb-demo -n scenarios

# View PDB events
kubectl get events -n scenarios --field-selector involvedObject.name=pdb-demo

# Check which pods PDB protects
kubectl get pods -n scenarios -l app=pdb-demo

# See PDB YAML
kubectl get pdb pdb-demo -n scenarios -o yaml

# Test if drain would succeed (dry-run)
kubectl drain <node> --dry-run --ignore-daemonsets

# Force drain (DANGEROUS - ignores PDB)
kubectl drain <node> --ignore-daemonsets --disable-eviction --force
# ⚠️ Only use in emergencies!

# Monitor PDB during drain
kubectl get pdb -n scenarios -w

# Check deployment replica count
kubectl get deployment pdb-demo-app -n scenarios

# Scale up to allow disruptions
kubectl scale deployment pdb-demo-app --replicas=5 -n scenarios

# View PDB in JSON (for automation)
kubectl get pdb pdb-demo -n scenarios -o json | jq .status
```

---

## 🎓 Key Takeaways

1. **PDB protects against voluntary disruptions only** - Node failures still happen
2. **minAvailable is absolute minimum** - Choose based on your HA requirements
3. **Use percentages with HPA** - Scales dynamically with replica count
4. **Test before production** - Ensure PDB doesn't block necessary maintenance
5. **Monitor ALLOWED DISRUPTIONS** - Should be > 0 for healthy operations
6. **Combine with anti-affinity** - Spread pods + PDB = maximum availability
7. **PDB != backup/disaster recovery** - Still need backups, monitoring, runbooks
8. **Balance availability vs flexibility** - Too restrictive PDB blocks cluster ops

---

*This explanation provides deep insights into PodDisruptionBudgets and high availability concepts. Start with basic PDB (fixed minAvailable), then explore percentages, maxUnavailable, and advanced multi-PDB scenarios!*
