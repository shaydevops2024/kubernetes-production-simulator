# YAML Files Explanation - High Availability Special Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them for building highly available applications.

---

## 🚀 deployment.yaml

### What is This Deployment?
This Deployment creates a highly available application with pod anti-affinity to spread replicas across different nodes, preventing single-point-of-failure.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
```
**What it is:** The API version for Deployment resources
**Options:** `apps/v1` is the current stable version
**Why:** Deployments are part of the `apps` API group

```yaml
kind: Deployment
```
**What it is:** Declares this is a Deployment resource
**Why for HA:** Deployments provide self-healing, rolling updates, and replica management - essential for high availability

```yaml
metadata:
  name: ha-demo-app
  namespace: scenarios
  labels:
    app: ha-demo
    scenario: "17"
```
**What it is:** Metadata identifying the Deployment
- `name`: Unique name for the deployment
- `namespace`: Logical isolation
- `labels`: Used by Service, HPA, and PDB for selection

**HA Consideration:** Consistent labeling is critical - Service, HPA, and PDB all reference these labels

```yaml
spec:
  replicas: 3
```
**What it is:** Initial number of pod replicas
**Why 3 for HA?**
- Provides redundancy (can tolerate 1-2 pod failures)
- Enables distribution across multiple nodes
- Minimum recommended for production HA
- Works well with PDB minAvailable: 2

**Important:** HPA will override this value during auto-scaling

```yaml
  selector:
    matchLabels:
      app: ha-demo
```
**What it is:** How the Deployment finds its pods
**Critical:** Must match `template.metadata.labels` exactly
**Why:** Without matching selector, Deployment can't manage its pods

```yaml
  template:
    metadata:
      labels:
        app: ha-demo
```
**What it is:** Pod template labels
**Must include:** All labels from `selector.matchLabels`
**Also used by:** Service selector, PDB selector, HPA monitoring

```yaml
    spec:
      containers:
      - name: nginx
        image: nginx:1.21-alpine
```
**What it is:** Container specification
**Why nginx?** Lightweight web server for HA demonstration
**Best practice:** Pin specific version (`1.21-alpine`) not `:latest`

```yaml
        ports:
        - containerPort: 80
```
**What it is:** Port the container exposes
**Why:** Service routes traffic to this port
**For HA:** Ensures consistent port across all replicas

```yaml
        resources:
          requests:
            cpu: 100m
            memory: 64Mi
```
**What it is:** Resource requests - guaranteed allocation

### 🔑 CRITICAL for HA + HPA!

**cpu: 100m (100 millicores = 0.1 CPU cores)**
- HPA **requires** CPU requests to calculate percentage
- Scheduler uses this to decide pod placement
- Too low = poor performance, too high = wasted resources

**Why 100m?**
- Nginx is lightweight
- Allows testing HPA scaling on limited resources
- Production: Base on actual usage (use `kubectl top pod`)

**How HPA uses requests:**
```
Pod using 60m CPU, requests 100m CPU
HPA sees: 60m / 100m = 60% utilization
If target is 50%, HPA scales up
```

**memory: 64Mi**
- Minimal for nginx
- Production: Monitor and adjust based on actual usage

**Important:** Missing requests = HPA shows `<unknown>` and doesn't work!

### Pod Anti-Affinity Section (Most Important for HA!)

```yaml
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
```

**What is Pod Anti-Affinity?**
Rules that tell Kubernetes scheduler to **avoid** placing pods together

**Two types:**
1. **preferredDuringSchedulingIgnoredDuringExecution** (used here - soft constraint)
2. **requiredDuringSchedulingIgnoredDuringExecution** (hard constraint)

**Why "preferred" not "required"?**
- **Preferred:** Scheduler **tries** to spread pods but can still schedule if not possible
  - ✅ Works on single-node clusters (testing)
  - ✅ Gracefully handles node capacity limits
  - ✅ Prevents pods from being stuck in Pending state

- **Required:** Scheduler **must** spread pods or they stay Pending
  - ❌ Fails on single-node clusters
  - ❌ Can block scaling if no suitable nodes
  - ✅ Stronger guarantee for production multi-zone clusters

**"DuringScheduling":** Rule only applies when scheduling new pods
**"IgnoredDuringExecution":** Doesn't move running pods if rule changes

```yaml
          - weight: 100
```
**What it is:** Priority weight (1-100)
**Why 100?** Highest priority - strongly prefer spreading
**How it works:** Scheduler scores each node, higher weight = stronger preference

```yaml
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - ha-demo
```
**What it is:** Identifies "which pods to avoid"
**Translation:** "Avoid placing this pod on nodes that already have pods with label app=ha-demo"

**How it works:**
1. New pod needs to be scheduled
2. Scheduler finds all nodes
3. Checks each node for existing pods with `app=ha-demo`
4. Scores nodes: nodes **without** ha-demo pods get higher score
5. Prefers nodes with higher score

```yaml
              topologyKey: kubernetes.io/hostname
```

### 🔑 Most Important Field for Distribution!

**What it is:** Defines the "failure domain" for spreading pods

**Common topology keys:**
1. **kubernetes.io/hostname** (used here)
   - Each node has unique hostname
   - **Effect:** Spreads pods across different **nodes**
   - **Use when:** Protecting against node failures

2. **topology.kubernetes.io/zone**
   - Groups nodes by availability zone
   - **Effect:** Spreads pods across different **zones**
   - **Use when:** Protecting against zone/datacenter failures
   - **Requires:** Multi-zone cluster (AWS, GCP, Azure)

3. **topology.kubernetes.io/region**
   - Groups nodes by region
   - **Effect:** Spreads pods across different **regions**
   - **Use when:** Geo-distributed applications, disaster recovery

**How topologyKey works:**
```
Cluster with 3 nodes:
- node1: kubernetes.io/hostname=node1
- node2: kubernetes.io/hostname=node2
- node3: kubernetes.io/hostname=node3

Pod 1 scheduled → node1
Pod 2 scheduling → Anti-affinity says "avoid nodes with app=ha-demo"
                 → node1 has app=ha-demo, score lowered
                 → Pod 2 prefers node2 or node3

Pod 3 scheduling → node1 and node2 have app=ha-demo
                 → Pod 3 prefers node3

Result: 3 pods spread across 3 nodes ✅
```

**Production multi-zone example:**
```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - ha-demo
        topologyKey: topology.kubernetes.io/zone  # Spread across zones

    # Also prefer different nodes within same zone
    - weight: 50
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - ha-demo
        topologyKey: kubernetes.io/hostname  # Spread across nodes
```

---

## 🌐 service.yaml

### What is This Service?
Provides a stable network endpoint (DNS name + ClusterIP) for accessing the HA application pods.

### YAML Structure Breakdown:

```yaml
apiVersion: v1
```
**What it is:** Core Kubernetes API
**Why v1:** Services are fundamental resources in core API

```yaml
kind: Service
```
**What it is:** Declares this is a Service resource
**For HA:** Provides stable endpoint even as pods are created/destroyed

```yaml
metadata:
  name: ha-demo-service
  namespace: scenarios
```
**What it is:** Service metadata
- `name`: Becomes DNS name (`ha-demo-service.scenarios.svc.cluster.local`)
- Used in load generator: `wget http://ha-demo-service`

**HA Consideration:** Service provides single entry point for all replicas - critical for load distribution

```yaml
spec:
  selector:
    app: ha-demo
```
**What it is:** Selects which pods receive traffic
**Critical for HA:** Automatically includes ALL pods with `app=ha-demo` label
- When HPA scales up → New pods automatically added
- When pods fail → Failed pods automatically removed
- Self-healing + auto-discovery

**How load balancing works:**
```
Service has 3 backend pods:
Request 1 → Pod 1
Request 2 → Pod 2
Request 3 → Pod 3
Request 4 → Pod 1 (round-robin)

HPA scales to 5 pods:
Service automatically discovers new pods
Request distribution now across 5 pods
```

```yaml
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
```
**What it is:** Port mapping
- `port: 80`: Service listens on port 80
- `targetPort: 80`: Forwards to pod port 80

**For HA:** All replicas must listen on same targetPort

**No type specified = ClusterIP (default)**
- Internal-only access
- Perfect for this demo (load generator runs inside cluster)

---

## 🛡️ pdb.yaml

### What is a PodDisruptionBudget (PDB)?
Protects application availability during **voluntary disruptions** (node drains, rolling updates, cluster scaling).

### Why PDB is Critical for HA:

**Without PDB:**
```
3 pods running on 3 nodes
Admin drains node1 → Pod 1 evicted
Admin drains node2 → Pod 2 evicted
Admin drains node3 → Pod 3 evicted
Result: 0 pods running = DOWNTIME ❌
```

**With PDB (minAvailable: 2):**
```
3 pods running on 3 nodes
Admin drains node1 → Pod 1 evicted (2 pods remain ✅)
Admin drains node2 → PDB BLOCKS eviction (would violate minAvailable: 2)
Admin must wait for Pod 1 to be rescheduled
Once Pod 1 is running → node2 drain can proceed
Result: Always ≥2 pods running = NO DOWNTIME ✅
```

### YAML Structure Breakdown:

```yaml
apiVersion: policy/v1
```
**What it is:** Policy API version
**History:**
- `policy/v1beta1` - Old, deprecated
- `policy/v1` - Current stable (Kubernetes 1.21+)

```yaml
kind: PodDisruptionBudget
```
**What it is:** Declares this is a PDB resource

```yaml
metadata:
  name: ha-demo-pdb
  namespace: scenarios
```
**What it is:** PDB metadata
**Must match:** Namespace of protected pods

```yaml
spec:
  minAvailable: 2
```
**What it is:** Minimum pods that must remain available during disruptions

### 🔑 Choosing minAvailable Value:

**Formula:** `minAvailable = replicas - 1` (most common)

**Examples:**
```yaml
# 3 replicas → minAvailable: 2
# Allows 1 pod to be disrupted at a time
# Maintains 67% capacity during disruptions

# 5 replicas → minAvailable: 4
# Allows 1 pod disruption
# Maintains 80% capacity

# 5 replicas → minAvailable: 3
# Allows 2 pods disruption (more aggressive)
# Maintains 60% capacity
```

**Alternative: maxUnavailable**
```yaml
spec:
  maxUnavailable: 1  # At most 1 pod can be unavailable
  # Equivalent to minAvailable: replicas - 1
```

**Percentage-based:**
```yaml
spec:
  minAvailable: 75%  # At least 75% of pods must be available
  # Works with dynamic replica counts from HPA
```

**Why minAvailable: 2 for this scenario?**
- 3 replicas baseline (from Deployment)
- Allows 1 disruption at a time
- Ensures service remains available
- Works with HPA (protects during scale-down too)

```yaml
  selector:
    matchLabels:
      app: ha-demo
```
**What it is:** Selects which pods to protect
**Critical:** Must match pod labels from Deployment

**⚠️ Common mistake:** Selector doesn't match any pods → PDB has no effect

### What PDB Protects Against:

✅ **Protects:**
- Node drains (`kubectl drain`)
- Voluntary evictions
- Cluster autoscaler scale-down
- Rolling updates (prevents too many pods updating at once)

❌ **Does NOT protect:**
- Node crashes (involuntary)
- Pod crashes (involuntary)
- Manual `kubectl delete pod` (can override with `--grace-period=0 --force`)
- Out of memory kills

### Monitoring PDB:

```bash
# Check PDB status
kubectl get pdb ha-demo-pdb -n scenarios

# Output example:
# NAME           MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
# ha-demo-pdb    2               N/A               1                     5m

# ALLOWED DISRUPTIONS = Current healthy pods - minAvailable
# 3 healthy pods - 2 minAvailable = 1 allowed disruption
```

**ALLOWED DISRUPTIONS = 0:** Cannot disrupt any pods (already at minimum)
**ALLOWED DISRUPTIONS > 0:** Can safely disrupt that many pods

---

## 📊 hpa.yaml

### What is HPA (HorizontalPodAutoscaler)?
Automatically adjusts the number of pod replicas based on observed metrics (CPU utilization in this case).

### Why HPA for HA:

**Traffic patterns:**
```
Normal load: 3 pods handle traffic fine
Traffic spike: 3 pods overwhelmed → Response time ↑
HPA detects high CPU → Scales to 6 pods
6 pods handle spike → Response time back to normal ✅
```

**HA benefit:** Application automatically adapts to load without manual intervention

### YAML Structure Breakdown:

```yaml
apiVersion: autoscaling/v2
```
**What it is:** HPA API version
**Why v2?** Supports multiple metrics (CPU, memory, custom)
**Previous:** `autoscaling/v1` (CPU only, deprecated)

```yaml
kind: HorizontalPodAutoscaler
```
**What it is:** Declares this is an HPA resource

```yaml
metadata:
  name: ha-demo-hpa
  namespace: scenarios
```
**What it is:** HPA metadata

```yaml
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ha-demo-app
```
**What it is:** Specifies **what to scale**
**How it works:** HPA modifies `ha-demo-app` Deployment's `spec.replicas` field

**Important:** HPA takes ownership of replica count - don't manually edit Deployment replicas!

```yaml
  minReplicas: 3
```
**What it is:** Minimum pod count
**Why 3 for HA?**
- Maintains availability even during low traffic
- Can tolerate 1-2 pod failures
- Works with PDB minAvailable: 2
- Never scales below this (prevents service outage)

```yaml
  maxReplicas: 10
```
**What it is:** Maximum pod count - safety limit

**Why set max?**
- Prevents runaway scaling (cost control)
- Protects cluster resources
- Prevents overwhelming backend systems (databases, APIs)

**Choosing maxReplicas:**
- **Too low:** Can't handle legitimate traffic spikes
- **Too high:** Wastes money, may exceed downstream capacity
- **Right value:** Based on realistic max load + 20-30% buffer

```yaml
  metrics:
  - type: Resource
    resource:
      name: cpu
```
**What it is:** Metric to scale on
**type: Resource:** Built-in Kubernetes resource (CPU or memory)
**name: cpu:** Scale based on CPU utilization

**Alternatives:**
```yaml
# Memory-based scaling
- type: Resource
  resource:
    name: memory
    target:
      type: Utilization
      averageUtilization: 80

# Custom metrics (requires metrics adapter)
- type: Pods
  pods:
    metric:
      name: http_requests_per_second
    target:
      type: AverageValue
      averageValue: "1000"
```

```yaml
      target:
        type: Utilization
        averageUtilization: 50
```

### 🔑 Most Important HPA Setting!

**type: Utilization**
- Percentage of **requested** resources
- Requires `resources.requests.cpu` in Deployment

**averageUtilization: 50**
- Target: Keep average CPU at 50% of requests

**How percentage is calculated:**
```
Example:
- 4 pods, each requests 100m CPU
- Pod 1: 60m actual, Pod 2: 50m, Pod 3: 55m, Pod 4: 45m
- Total actual: 210m
- Total requested: 400m (4 × 100m)
- Utilization: 210m / 400m = 52.5%

Target is 50%, current is 52.5%
52.5% > 50% → SCALE UP
Desired replicas = ceil(4 × 52.5 / 50) = ceil(4.2) = 5 pods
```

**Why 50% target?**
- 🔴 Too low (20%): Wastes resources, over-provisioned
- 🟢 **50-70%: RECOMMENDED** - efficient with headroom for spikes
- 🟡 Too high (90%): Risky, no buffer for sudden load increases

**50% means:**
- Pods running at half capacity on average
- 50% headroom for traffic bursts
- HPA has time to scale before overload
- Balance between cost and reliability

### How HPA Scaling Works:

**Scaling Algorithm:**
```
Desired Replicas = ceil(Current Replicas × Current Metric / Target Metric)
```

**Scale Up Example:**
```
Current: 3 pods at 80% CPU (target: 50%)
Desired = ceil(3 × 80 / 50) = ceil(4.8) = 5 pods
HPA scales: 3 → 5 pods
```

**Scale Down Example:**
```
Current: 5 pods at 20% CPU (target: 50%)
Desired = ceil(5 × 20 / 50) = ceil(2) = 2 pods
But minReplicas: 3!
HPA scales: 5 → 3 pods (stops at minimum)
```

**Timing:**
- **Scale-up:** Fast (1-3 minutes) - handle traffic quickly
- **Scale-down:** Slow (5+ minutes) - prevent flapping
- **Metric collection:** Every 15 seconds
- **Cooldown:** 3-5 minutes between scaling actions

---

## 🔄 How All Components Work Together for HA

### Complete HA Flow:

**1. Initial Deployment:**
```
Deployment creates 3 pods with anti-affinity
→ Pod 1 on node1, Pod 2 on node2, Pod 3 on node3
→ Service discovers all 3 pods
→ PDB protects with minAvailable: 2
→ HPA monitors CPU (baseline: 10-20%)
```

**2. Traffic Spike:**
```
Load increases → Pods CPU rises to 80%
→ HPA detects: 80% > target 50%
→ HPA scales Deployment: 3 → 5 replicas
→ New pods scheduled (anti-affinity spreads them)
→ Service automatically includes new pods
→ Load distributed across 5 pods
→ CPU drops back to ~50%
```

**3. Node Maintenance:**
```
Admin runs: kubectl drain node2
→ Tries to evict Pod 2
→ PDB checks: 5 pods running, minAvailable: 2
→ 5 - 1 = 4 remaining (> 2 ✅)
→ PDB allows eviction
→ Pod 2 evicted
→ Deployment controller creates new Pod 2
→ Anti-affinity schedules to available node
→ Service updates endpoints
→ No downtime - traffic continues to 4 pods during migration
```

**4. Load Decreases:**
```
Traffic returns to normal
→ CPU drops to 15% across all pods
→ HPA waits 5 minutes (stabilization)
→ HPA scales down gradually: 5 → 4 → 3
→ Stops at minReplicas: 3
→ PDB ensures minAvailable maintained during scale-down
```

**5. Pod Failure:**
```
Pod 1 crashes (involuntary)
→ Service removes Pod 1 from endpoints immediately
→ Traffic routes to remaining 2 pods (PDB minAvailable met)
→ Deployment controller detects missing pod
→ Creates replacement Pod 1
→ Anti-affinity schedules replacement
→ New Pod 1 becomes Ready
→ Service adds back to endpoints
→ Self-healing complete - back to 3 pods
```

### Multi-Layer Protection:

1. **Anti-Affinity:** Spreads pods across nodes (prevents cascading failures)
2. **Multiple Replicas:** Can tolerate pod failures (redundancy)
3. **PDB:** Protects during voluntary disruptions (maintenance windows)
4. **HPA:** Adapts to load automatically (handles traffic spikes)
5. **Service:** Provides stable endpoint and load balancing (abstraction)
6. **Self-Healing:** Deployment recreates failed pods (automatic recovery)

**Result:** Highly resilient application that:
- Survives node failures ✅
- Survives pod crashes ✅
- Handles traffic spikes ✅
- Allows safe maintenance ✅
- Auto-recovers from failures ✅

---

## 🎯 Production Best Practices

### 1. Pod Anti-Affinity Strategy

✅ **Recommended for production:**
```yaml
# Multi-zone clusters: Required zone spread + Preferred node spread
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchExpressions:
        - key: app
          operator: In
          values: [ha-demo]
      topologyKey: topology.kubernetes.io/zone  # MUST spread across zones
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values: [ha-demo]
        topologyKey: kubernetes.io/hostname  # Prefer different nodes
```

### 2. PDB Configuration

✅ **Production recommendations:**
```yaml
# Option 1: Percentage (works with HPA)
spec:
  minAvailable: 75%  # Always maintain 75% capacity

# Option 2: Specific count
spec:
  minAvailable: 2  # For small deployments (3-4 replicas)

# Option 3: Max unavailable (more flexible)
spec:
  maxUnavailable: 25%  # Allow up to 25% disruption
```

**Critical services:** Use `minAvailable: 100%` during high-traffic periods

### 3. HPA Tuning

✅ **Production HPA configuration:**
```yaml
spec:
  minReplicas: 3  # Minimum for HA
  maxReplicas: 50  # Based on realistic max load
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # More efficient than 50%

  # Optional: Advanced scaling behavior (HPA v2)
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5min before scale-down
      policies:
      - type: Percent
        value: 50  # Max 50% reduction at once
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0  # Scale up immediately
      policies:
      - type: Percent
        value: 100  # Can double pods at once
        periodSeconds: 15
```

### 4. Resource Requests/Limits

✅ **Set realistic values:**
```yaml
resources:
  requests:
    cpu: 100m      # Based on actual average usage
    memory: 128Mi
  limits:
    cpu: 200m      # 2x requests (burst capacity)
    memory: 256Mi  # 2x requests
```

**Monitor and adjust:**
```bash
kubectl top pods -n scenarios  # Check actual usage
```

### 5. Health Probes (Add for production!)

✅ **Critical for HA:**
```yaml
containers:
- name: nginx
  image: nginx:1.21-alpine
  livenessProbe:
    httpGet:
      path: /
      port: 80
    initialDelaySeconds: 10
    periodSeconds: 10
    failureThreshold: 3
  readinessProbe:
    httpGet:
      path: /
      port: 80
    initialDelaySeconds: 5
    periodSeconds: 5
    failureThreshold: 2
```

**Why?**
- **Liveness:** Kills unhealthy pods (enables self-healing)
- **Readiness:** Removes pods from Service endpoints (prevents traffic to broken pods)

---

## 🔍 Troubleshooting Guide

### HPA shows `<unknown>` for CPU

**Symptoms:**
```bash
$ kubectl get hpa
NAME          REFERENCE             TARGETS         MINPODS   MAXPODS   REPLICAS
ha-demo-hpa   Deployment/ha-demo-app <unknown>/50%  3         10        0
```

**Causes:**
1. Metrics Server not installed
2. Pods have no `resources.requests.cpu`
3. Pods not yet Running

**Fixes:**
```bash
# Install Metrics Server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify Metrics Server
kubectl top nodes
kubectl top pods -n scenarios

# Check pod resources
kubectl get pod <pod> -n scenarios -o json | jq '.spec.containers[].resources'
```

### Pods Not Spreading Across Nodes

**Check:**
```bash
# View pod distribution
kubectl get pods -n scenarios -l app=ha-demo -o wide

# All on same node? Anti-affinity not working
```

**Causes:**
1. Single-node cluster (use `preferred` not `required`)
2. Wrong `topologyKey`
3. Labels don't match

**Debug:**
```bash
# Check node labels
kubectl get nodes --show-labels

# Verify pod anti-affinity
kubectl get deployment ha-demo-app -n scenarios -o yaml | grep -A 20 affinity
```

### PDB Not Blocking Drain

**Symptoms:** Node drains successfully despite violating minAvailable

**Check PDB status:**
```bash
kubectl get pdb ha-demo-pdb -n scenarios
kubectl describe pdb ha-demo-pdb -n scenarios
```

**Common issues:**
1. PDB selector doesn't match pods
2. Not enough healthy pods
3. Using `--force --grace-period=0` (bypasses PDB)

### HPA Not Scaling

**Debug steps:**
```bash
# Check HPA status
kubectl describe hpa ha-demo-hpa -n scenarios

# Check recent events
kubectl get events -n scenarios --sort-by='.lastTimestamp'

# Verify CPU usage
kubectl top pods -n scenarios

# Check if at max replicas
kubectl get hpa -n scenarios
```

---

## 📚 Key Takeaways

1. **Pod Anti-Affinity** with `topologyKey: kubernetes.io/hostname` spreads pods across nodes
2. **PodDisruptionBudget** with `minAvailable: 2` protects availability during disruptions
3. **HPA** with `averageUtilization: 50` provides automatic scaling based on load
4. **Service** provides stable endpoint and automatic load balancing across all replicas
5. **All components work together** for defense-in-depth HA strategy
6. **Production requires** health probes, realistic resource requests, and multi-zone configuration

---

*This comprehensive guide provides deep understanding of building highly available Kubernetes applications. Master these concepts for production-ready deployments!*
