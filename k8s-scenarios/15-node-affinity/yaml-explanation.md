# YAML Files Explanation - Node Affinity & Pod Scheduling Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 📦 deployment.yaml (Simple Node Affinity)

### What is Node Affinity?
Node Affinity is a set of rules that constrain which nodes your pods can be scheduled on, based on node labels. It's a more expressive and flexible version of `nodeSelector`.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: affinity-demo-app
  namespace: scenarios
  labels:
    app: affinity-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: affinity-demo
  template:
    metadata:
      labels:
        app: affinity-demo
```
**What it is:** Standard Deployment structure
**Nothing special yet:** Magic happens in `spec.template.spec.affinity`

```yaml
    spec:
      affinity:
        nodeAffinity:
```
**What it is:** **CRITICAL SECTION** - Defines node selection rules
**Why use affinity vs nodeSelector?**
- More expressive (operators like In, NotIn, Exists, Gt, Lt)
- Can specify "preferred" vs "required" rules
- Can combine multiple conditions

**nodeSelector (old, simple way):**
```yaml
# Simple but limited
nodeSelector:
  disktype: ssd
```

**nodeAffinity (new, powerful way):**
```yaml
# Flexible and expressive
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: disktype
          operator: In
          values:
          - ssd
```

```yaml
          requiredDuringSchedulingIgnoredDuringExecution:
```
**What it is:** **HARD** constraint - Pod MUST be scheduled on matching nodes
**Long name explained:**
- `requiredDuringScheduling` - **Required** when placing pod
- `IgnoredDuringExecution` - Doesn't evict pod if node label changes later

**Example:**
```
1. Pod scheduled on node with disktype=ssd ✅
2. Later, admin removes label: kubectl label node node1 disktype-
3. Pod keeps running (IgnoredDuringExecution) ✅
4. If pod restarts, must find node with disktype=ssd again
```

**Alternative: Preferred (soft constraint):**
```yaml
preferredDuringSchedulingIgnoredDuringExecution:
- weight: 100
  preference:
    matchExpressions:
    - key: disktype
      operator: In
      values:
      - ssd
```

**Comparison:**

| Type | Behavior | Use case |
|------|----------|----------|
| **required** | MUST match or pod stays Pending | Hard requirements (GPU, SSD) |
| **preferred** | Prefer but can schedule elsewhere | Soft preferences (zone preference) |

```yaml
            nodeSelectorTerms:
```
**What it is:** List of node selector requirements
**OR logic:** Pod scheduled if **any** term matches

**Example:**
```yaml
nodeSelectorTerms:
- matchExpressions:  # Term 1: disktype=ssd
  - key: disktype
    operator: In
    values:
    - ssd
- matchExpressions:  # Term 2: disktype=nvme
  - key: disktype
    operator: In
    values:
    - nvme

# Pod scheduled on nodes with disktype=ssd OR disktype=nvme
```

**Within a term (AND logic):**
```yaml
nodeSelectorTerms:
- matchExpressions:
  - key: disktype
    operator: In
    values:
    - ssd
  - key: zone
    operator: In
    values:
    - us-east-1a

# Pod scheduled ONLY on nodes with disktype=ssd AND zone=us-east-1a
```

```yaml
            - matchExpressions:
              - key: disktype
                operator: In
                values:
                - ssd
```
**What it is:** Match nodes based on label expressions

**Fields:**
- `key: disktype` - Node label key to check
- `operator: In` - How to evaluate
- `values: [ssd]` - Accepted values

**Operators:**

1. **In** (used here):
   ```yaml
   key: disktype
   operator: In
   values: [ssd, nvme]
   # Matches nodes with disktype=ssd OR disktype=nvme
   ```

2. **NotIn**:
   ```yaml
   key: disktype
   operator: NotIn
   values: [hdd]
   # Matches nodes where disktype != hdd
   ```

3. **Exists**:
   ```yaml
   key: disktype
   operator: Exists
   # Matches nodes that have label "disktype" (any value)
   # No values field needed
   ```

4. **DoesNotExist**:
   ```yaml
   key: disktype
   operator: DoesNotExist
   # Matches nodes that DON'T have label "disktype"
   ```

5. **Gt** (Greater than - numeric):
   ```yaml
   key: cpu-count
   operator: Gt
   values: ["8"]
   # Matches nodes where cpu-count > 8
   ```

6. **Lt** (Less than - numeric):
   ```yaml
   key: cpu-count
   operator: Lt
   values: ["16"]
   # Matches nodes where cpu-count < 16
   ```

**Before scheduling:**
```bash
# Label a node with disktype=ssd
kubectl label node <node-name> disktype=ssd

# Verify
kubectl get nodes --show-labels | grep disktype
```

```yaml
      containers:
      - name: nginx
        image: nginx:1.21-alpine
        ports:
        - containerPort: 80
```
**What it is:** Standard container spec
**Nothing special:** Affinity doesn't affect container configuration

---

## 🎯 node-affinity.yaml (Comprehensive Examples)

This file contains multiple deployment examples demonstrating different scheduling strategies.

### Example 1: NodeSelector (Simplest)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-with-node-selector
  namespace: k8s-multi-demo
spec:
  template:
    spec:
      nodeSelector:
        workload: frontend
```

**What it is:** Legacy way to select nodes (still works)
**Behavior:** Pod ONLY runs on nodes with label `workload=frontend`

**When to use:**
- ✅ Simple exact-match requirements
- ✅ Easy to read and understand
- ❌ Limited (no OR, no operators)

**Equivalent nodeAffinity:**
```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: workload
          operator: In
          values:
          - frontend
```

---

### Example 2: Preferred Node Affinity (Soft Constraint)

```yaml
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      preference:
        matchExpressions:
        - key: disktype
          operator: In
          values:
          - ssd
    - weight: 50
      preference:
        matchExpressions:
        - key: zone
          operator: In
          values:
          - us-east-1a
```

**What it is:** **SOFT** constraints with weighted preferences
**Behavior:** Scheduler **prefers** these nodes but can place pod elsewhere

### 🔑 Understanding Weights

**weight: 100** and **weight: 50**
- Higher weight = stronger preference
- Range: 1-100
- Scheduler calculates scores for each node

**Scoring example:**
```
Node A: disktype=ssd, zone=us-east-1a
Score: 100 (disktype match) + 50 (zone match) = 150 ✅ Best!

Node B: disktype=ssd, zone=us-east-1b
Score: 100 (disktype match) + 0 (no zone match) = 100

Node C: disktype=hdd, zone=us-east-1a
Score: 0 (no disktype match) + 50 (zone match) = 50

Node D: disktype=hdd, zone=us-east-1b
Score: 0 + 0 = 0

Scheduler picks Node A (highest score)
If Node A is full, picks Node B (second highest)
```

**Multiple preferences:**
```yaml
preferredDuringSchedulingIgnoredDuringExecution:
- weight: 100    # Strongest preference
  preference:
    matchExpressions:
    - key: instance-type
      operator: In
      values:
      - m5.xlarge
- weight: 75     # Medium preference
  preference:
    matchExpressions:
    - key: zone
      operator: In
      values:
      - us-east-1a
- weight: 25     # Weakest preference
  preference:
    matchExpressions:
    - key: spot-instance
      operator: DoesNotExist
```

**When to use preferred:**
- Cost optimization (prefer cheaper nodes, but can use expensive)
- Zone preference (prefer one zone, but can use others)
- Resource optimization (prefer high-memory nodes for caching)

---

### Example 3: Required Node Affinity (Hard Constraint)

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - k8s-demo-control-plane
```

**What it is:** **HARD** constraint - Pod MUST run on specific node
**Use case:** Pin pod to specific node by hostname

**kubernetes.io/hostname:**
- Built-in label on every node
- Value = node's hostname
- Useful for debugging, testing

**Other built-in node labels:**
```yaml
# Operating system
kubernetes.io/os: linux

# Architecture
kubernetes.io/arch: amd64

# Instance type (cloud providers)
node.kubernetes.io/instance-type: m5.xlarge

# Availability zone
topology.kubernetes.io/zone: us-east-1a

# Region
topology.kubernetes.io/region: us-east-1
```

**Production example (GPU nodes):**
```yaml
requiredDuringSchedulingIgnoredDuringExecution:
  nodeSelectorTerms:
  - matchExpressions:
    - key: accelerator
      operator: In
      values:
      - nvidia-tesla-v100
      - nvidia-tesla-p100
```

---

### Example 4: Pod Anti-Affinity (Spread Across Nodes)

```yaml
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchExpressions:
        - key: app
          operator: In
          values:
          - anti-affinity-demo
      topologyKey: kubernetes.io/hostname
```

**What it is:** **DON'T** schedule pod on same node as pods matching selector
**Purpose:** High availability - spread replicas across nodes

### 🔑 Understanding Pod Anti-Affinity

**How it works:**
```
Deployment with 3 replicas, podAntiAffinity

Pod 1: Scheduled on Node A ✅
Pod 2: Cannot go on Node A (Pod 1 already there) → Goes to Node B ✅
Pod 3: Cannot go on Node A or Node B → Goes to Node C ✅

Result: Each pod on different node (high availability)
```

**topologyKey: kubernetes.io/hostname**
- Defines the "domain" for anti-affinity
- `hostname` = node-level separation
- Each pod on different node

**Other topologyKey options:**

```yaml
# Spread across availability zones
topologyKey: topology.kubernetes.io/zone

# Spread across regions
topologyKey: topology.kubernetes.io/region

# Spread across racks (if labeled)
topologyKey: rack
```

**Example: Zone-level anti-affinity:**
```yaml
podAntiAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
  - labelSelector:
      matchExpressions:
      - key: app
        operator: In
        values:
        - my-app
    topologyKey: topology.kubernetes.io/zone

# Result: Each pod in different availability zone
# Pod 1: us-east-1a
# Pod 2: us-east-1b
# Pod 3: us-east-1c
```

**When to use:**
- ✅ Critical applications (high availability)
- ✅ Avoid single point of failure
- ✅ Distribute load across nodes/zones

**⚠️ Warning:** If replicas > nodes, pods stay Pending!
```
3 nodes, 5 replicas with anti-affinity
→ 3 pods schedule
→ 2 pods stay Pending (no available nodes)
```

**Solution: Use preferred anti-affinity:**
```yaml
podAntiAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 100
    podAffinityTerm:
      labelSelector:
        matchExpressions:
        - key: app
          operator: In
          values:
          - my-app
      topologyKey: kubernetes.io/hostname

# Prefers different nodes, but can co-locate if needed
```

---

### Example 5: Pod Affinity (Schedule Near Other Pods)

```yaml
affinity:
  podAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchExpressions:
        - key: app
          operator: In
          values:
          - k8s-demo-app
      topologyKey: kubernetes.io/hostname
```

**What it is:** **DO** schedule pod on same node as pods matching selector
**Purpose:** Co-locate related pods (reduce network latency)

**Use cases:**

1. **Cache near app:**
   ```yaml
   # Redis cache scheduled on same node as web app
   podAffinity:
     requiredDuringSchedulingIgnoredDuringExecution:
     - labelSelector:
         matchExpressions:
         - key: app
           operator: In
           values:
           - web-app
       topologyKey: kubernetes.io/hostname
   ```

2. **Data locality:**
   ```yaml
   # Data processing pod near data storage pod
   podAffinity:
     requiredDuringSchedulingIgnoredDuringExecution:
     - labelSelector:
         matchExpressions:
         - key: component
           operator: In
           values:
           - database
       topologyKey: kubernetes.io/hostname
   ```

3. **Zone-level affinity:**
   ```yaml
   # Schedule in same zone as main app (not same node)
   podAffinity:
     preferredDuringSchedulingIgnoredDuringExecution:
     - weight: 100
       podAffinityTerm:
         labelSelector:
           matchExpressions:
           - key: tier
             operator: In
             values:
             - frontend
         topologyKey: topology.kubernetes.io/zone
   ```

---

### Example 6: Tolerations (Run on Tainted Nodes)

```yaml
tolerations:
- key: "workload"
  operator: "Equal"
  value: "special"
  effect: "NoSchedule"
- key: "node-role.kubernetes.io/control-plane"
  operator: "Exists"
  effect: "NoSchedule"
```

**What are Taints and Tolerations?**
- **Taint:** Mark on node that repels pods (like "NO ENTRY" sign)
- **Toleration:** Permission for pod to ignore taint (like "VIP pass")

### 🔑 Understanding Taints and Tolerations

**Taint on node:**
```bash
kubectl taint nodes node1 workload=special:NoSchedule
```

**Effect:**
- Regular pods: Cannot schedule on node1
- Pods with matching toleration: CAN schedule on node1

**Toleration fields:**

1. **key:** Taint key to tolerate
2. **operator:** `Equal` (exact match) or `Exists` (any value)
3. **value:** Taint value (omit for `Exists` operator)
4. **effect:** Taint effect to tolerate

**Taint effects:**

1. **NoSchedule:**
   - New pods cannot schedule on node (unless they tolerate)
   - Existing pods keep running

   ```yaml
   tolerations:
   - key: "dedicated"
     operator: "Equal"
     value: "database"
     effect: "NoSchedule"
   ```

2. **PreferNoSchedule:**
   - Soft version of NoSchedule
   - Scheduler tries to avoid, but can place pod if needed

   ```yaml
   tolerations:
   - key: "workload"
     operator: "Equal"
     value: "batch"
     effect: "PreferNoSchedule"
   ```

3. **NoExecute:**
   - New pods cannot schedule
   - **EXISTING PODS ARE EVICTED** (unless they tolerate)

   ```yaml
   tolerations:
   - key: "maintenance"
     operator: "Exists"
     effect: "NoExecute"
     tolerationSeconds: 3600  # Evict after 1 hour
   ```

**Common use cases:**

1. **Dedicated nodes for specific workloads:**
   ```bash
   # Taint GPU nodes
   kubectl taint nodes gpu-node1 nvidia.com/gpu=true:NoSchedule
   ```

   ```yaml
   # GPU pods tolerate
   tolerations:
   - key: "nvidia.com/gpu"
     operator: "Exists"
     effect: "NoSchedule"
   ```

2. **Control plane nodes:**
   ```yaml
   # Allow pods on control plane (usually not recommended)
   tolerations:
   - key: "node-role.kubernetes.io/control-plane"
     operator: "Exists"
     effect: "NoSchedule"
   ```

3. **Node maintenance:**
   ```bash
   # Drain node for maintenance
   kubectl taint nodes node1 maintenance=true:NoExecute
   # Pods without toleration get evicted immediately
   ```

**Toleration operators:**

```yaml
# Equal - Exact match
tolerations:
- key: "workload"
  operator: "Equal"
  value: "special"
  effect: "NoSchedule"

# Exists - Any value (no value field)
tolerations:
- key: "workload"
  operator: "Exists"
  effect: "NoSchedule"
```

---

### Example 7: Complex Scheduling (All Combined)

```yaml
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
          - key: zone
            operator: In
            values:
            - zone-a
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values:
              - complex-demo
          topologyKey: kubernetes.io/hostname
  tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "backend"
    effect: "NoSchedule"
```

**What it is:** Production-grade scheduling with multiple constraints

**Breakdown:**

1. **Node Affinity (preferred):**
   - Prefer zone-a
   - But can schedule in other zones if needed

2. **Pod Anti-Affinity (preferred):**
   - Prefer different nodes from other replicas
   - But can co-locate if necessary (no available nodes)

3. **Tolerations:**
   - Can run on nodes tainted with dedicated=backend
   - Other pods (without this toleration) cannot

**Real-world production example:**
```yaml
affinity:
  nodeAffinity:
    # REQUIRED: Only GPU nodes
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: accelerator
          operator: Exists
    # PREFERRED: Prefer newer GPUs
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      preference:
        matchExpressions:
        - key: accelerator
          operator: In
          values:
          - nvidia-tesla-v100
  podAntiAffinity:
    # REQUIRED: Spread across nodes (HA)
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchExpressions:
        - key: app
          operator: In
          values:
          - ml-training
      topologyKey: kubernetes.io/hostname
tolerations:
# Tolerate GPU node taint
- key: "nvidia.com/gpu"
  operator: "Exists"
  effect: "NoSchedule"
```

---

## 📊 Scheduling Decision Flow

```
1. Filter Phase (Hard Constraints):
   ├─ Does node meet required nodeAffinity? ✅/❌
   ├─ Does pod tolerate node taints? ✅/❌
   ├─ Does node have required resources? ✅/❌
   ├─ Does required podAffinity/antiAffinity allow? ✅/❌
   └─ [If ❌, node eliminated]

2. Score Phase (Soft Constraints):
   ├─ Preferred nodeAffinity weights
   ├─ Preferred podAffinity/antiAffinity weights
   ├─ Resource balancing
   └─ [Calculate total score per node]

3. Select Node:
   └─ Pick node with highest score

4. Bind Pod:
   └─ Assign pod to selected node
```

---

## 🎯 Best Practices

### 1. Use Preferred for Most Cases

```yaml
# GOOD - Flexible
preferredDuringSchedulingIgnoredDuringExecution:
- weight: 100
  preference:
    matchExpressions:
    - key: disktype
      operator: In
      values:
      - ssd

# BAD - Too strict (pods may stay Pending)
requiredDuringSchedulingIgnoredDuringExecution:
  nodeSelectorTerms:
  - matchExpressions:
    - key: disktype
      operator: In
      values:
      - ssd
```

**Why?**
- Required can cause pods to stay Pending forever
- Preferred gives scheduler flexibility
- Use required only for hard requirements (GPUs, compliance)

### 2. Combine Node and Pod Affinity

```yaml
affinity:
  # Select GPU nodes
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: accelerator
          operator: Exists
  # Spread across nodes
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchLabels:
            app: my-app
        topologyKey: kubernetes.io/hostname
```

### 3. Label Nodes Consistently

```bash
# GOOD - Consistent naming
kubectl label node node1 disktype=ssd
kubectl label node node2 disktype=ssd
kubectl label node node3 disktype=hdd

# BAD - Inconsistent
kubectl label node node1 disk=ssd
kubectl label node node2 disktype=solid-state
kubectl label node node3 storage=hdd
```

### 4. Use Built-in Labels

```yaml
# Use Kubernetes built-in labels
nodeAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    nodeSelectorTerms:
    - matchExpressions:
      - key: topology.kubernetes.io/zone
        operator: In
        values:
        - us-east-1a
      - key: node.kubernetes.io/instance-type
        operator: In
        values:
        - m5.xlarge
```

### 5. Test Affinity Rules

```bash
# Check where pods scheduled
kubectl get pods -o wide

# Verify node labels
kubectl get nodes --show-labels

# Describe pod to see scheduling events
kubectl describe pod <pod-name>
```

---

## 🔍 Debugging Commands

```bash
# Label a node
kubectl label nodes node1 disktype=ssd

# Remove label
kubectl label nodes node1 disktype-

# View node labels
kubectl get nodes --show-labels

# Taint a node
kubectl taint nodes node1 workload=special:NoSchedule

# Remove taint
kubectl taint nodes node1 workload:NoSchedule-

# View node taints
kubectl describe node node1 | grep Taints

# See why pod is Pending
kubectl describe pod <pod-name>

# Get pods with node placement
kubectl get pods -o wide

# Check scheduler decisions
kubectl get events --sort-by='.lastTimestamp'
```

---

## 🚨 Common Issues

### Issue 1: Pods stuck in Pending

```bash
$ kubectl get pods
NAME                READY   STATUS    RESTARTS   AGE
my-app-xyz          0/1     Pending   0          5m
```

**Cause:** No nodes match required affinity rules

**Debug:**
```bash
kubectl describe pod my-app-xyz
# Look for: "0/3 nodes are available: 3 node(s) didn't match pod affinity rules"
```

**Solution:**
- Change `required` to `preferred`
- Label more nodes
- Remove overly restrictive rules

### Issue 2: All pods on same node

**Cause:** No anti-affinity configured

**Solution:**
```yaml
podAntiAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 100
    podAffinityTerm:
      labelSelector:
        matchLabels:
          app: my-app
      topologyKey: kubernetes.io/hostname
```

### Issue 3: Pods not tolerating control plane

**Cause:** Missing toleration for control plane taint

**Solution:**
```yaml
tolerations:
- key: "node-role.kubernetes.io/control-plane"
  operator: "Exists"
  effect: "NoSchedule"
```

---

## 🎓 Key Takeaways

1. **Node Affinity** - Select nodes based on labels
2. **Pod Affinity** - Schedule near specific pods
3. **Pod Anti-Affinity** - Spread pods across topology
4. **Tolerations** - Allow scheduling on tainted nodes
5. **Required vs Preferred** - Hard vs soft constraints
6. **topologyKey** - Defines scope (hostname, zone, region)
7. **Weights** - Priority for preferred rules (1-100)
8. **Operators** - In, NotIn, Exists, DoesNotExist, Gt, Lt

---

*This explanation provides deep insights into advanced pod scheduling with affinity, anti-affinity, taints, and tolerations for optimal workload placement!*
