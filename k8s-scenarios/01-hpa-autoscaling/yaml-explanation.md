# YAML Files Explanation - HPA Autoscaling Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 🚀 deployment.yaml

### What is a Deployment?
A Deployment manages a set of identical pods, ensuring desired replicas are running. It's the most common way to run stateless applications in Kubernetes, providing declarative updates and self-healing capabilities.

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
- `StatefulSet` - For stateful apps needing stable identities (databases)
- `DaemonSet` - One pod per node (monitoring agents, log collectors)
- `Job` - Run-to-completion tasks
- `ReplicaSet` - Lower-level, prefer Deployment

```yaml
metadata:
  name: hpa-demo-app
  namespace: scenarios
  labels:
    app: hpa-demo
    scenario: "01"
```
**What it is:** Metadata identifying the Deployment
- `name`: Unique name within namespace (used in kubectl commands)
- `namespace`: Logical grouping for resources
- `labels`: Key-value pairs for organization and selection

**Why labels?**
- Filter resources: `kubectl get deploy -l app=hpa-demo`
- Services use labels to select pods
- HPA uses labels to target deployments
- Monitoring tools use labels for grouping

**Best practices:**
- Use consistent label keys: `app`, `version`, `environment`, `component`
- Avoid special characters in label values
- Keep labels short and meaningful

```yaml
spec:
  replicas: 2
```
**What it is:** Initial desired number of pod copies
**Options:** Any integer ≥ 0
**Why start with 2?**
- High availability (if one pod fails, traffic routes to others)
- HPA needs a baseline to scale from
- Minimum for testing scale-up behavior

**Important:** When HPA is active, it **overrides** this value! HPA becomes the source of truth for replica count.

**When to use 1:** Development, testing, or when using StatefulSet for stateful apps
**Production:** Usually 2-3+ for critical services

```yaml
  selector:
    matchLabels:
      app: hpa-demo
```
**What it is:** How the Deployment finds its pods
**Critical:** Must match `template.metadata.labels` exactly
**Why:** Deployments don't create pods directly - they create ReplicaSets, which create pods. The selector tells the Deployment which pods it manages.

**Options:**
- `matchLabels`: Simple equality-based selection (most common)
- `matchExpressions`: Advanced logic (In, NotIn, Exists, DoesNotExist)

**Example with matchExpressions:**
```yaml
selector:
  matchExpressions:
  - key: app
    operator: In
    values: [hpa-demo, hpa-demo-v2]
  - key: environment
    operator: NotIn
    values: [test]
```

**⚠️ Common mistake:** Selector and template labels don't match → Deployment can't find pods → 0/2 pods ready

```yaml
  template:
    metadata:
      labels:
        app: hpa-demo
```
**What it is:** Pod template - blueprint for creating pods
**Why:** This defines what each pod will look like
**Labels:** Must include all selector labels (can have additional labels)

**Note:** Changing template triggers a **rolling update** (gradual replacement of old pods with new ones)

```yaml
    spec:
      containers:
      - name: php-apache
        image: k8s.gcr.io/hpa-example
```
**What it is:** Container specification
- `name`: Container name within pod (for `kubectl exec`, `kubectl logs`)
- `image`: Docker image to run

**About this image:**
- `k8s.gcr.io/hpa-example` is a demo PHP-Apache server
- Designed specifically for HPA testing
- Performs CPU-intensive calculations when hit with requests
- Perfect for demonstrating autoscaling

**Image best practices:**
- Pin specific versions: `nginx:1.21.6` ✅
- Avoid `:latest` tag ❌ (not reproducible, can break deployments)
- Use official images from trusted registries
- Consider using private registry for production

```yaml
        ports:
        - containerPort: 80
```
**What it is:** Port the container exposes
**Why:** Documentation and discovery (doesn't actually open the port - containers can listen on any port)
**When it matters:**
- Network policies (restrict traffic)
- Service discovery
- Documentation for other developers

**Options:**
```yaml
ports:
- containerPort: 80
  name: http        # Named port (can reference in Service)
  protocol: TCP     # TCP (default) or UDP
```

```yaml
        resources:
          requests:
            cpu: 200m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
```
**What it is:** Resource requirements and limits

### 🔑 CRITICAL for HPA! HPA REQUIRES `resources.requests.cpu`

**Requests (guaranteed resources):**
- `cpu: 200m` = 200 millicores = 0.2 CPU cores
- `memory: 128Mi` = 128 mebibytes RAM

**What "requests" means:**
- Kubernetes **guarantees** this much CPU/memory to the pod
- Scheduler only places pod on nodes with available requested resources
- HPA uses CPU requests to calculate percentage: `actual CPU / requested CPU * 100`

**Limits (maximum resources):**
- `cpu: 500m` = 500 millicores = 0.5 CPU cores (can burst up to this)
- `memory: 256Mi` = 256 mebibytes RAM (hard limit)

**What "limits" means:**
- Container cannot exceed memory limit (killed if it tries - OOMKilled)
- Container can burst to CPU limit (throttled if exceeds)

**Why these specific values?**
- **200m CPU request:** Small enough for testing on laptop/Kind cluster
- **500m CPU limit:** Allows 2.5x burst for handling load spikes
- **128Mi memory request:** Minimal for PHP-Apache
- **256Mi memory limit:** Prevents runaway memory leaks

**CPU units:**
- `1000m` = `1` = 1 full CPU core
- `100m` = 0.1 cores (10% of one core)
- `2000m` = `2` = 2 full CPU cores

**Memory units:**
- `Mi` = Mebibyte (1024^2 bytes) - binary
- `M` = Megabyte (1000^2 bytes) - decimal
- `Gi` = Gibibyte (1024^3 bytes)
- `G` = Gigabyte (1000^3 bytes)
- Prefer `Mi`/`Gi` for consistency

**How HPA uses requests:**
```
Example: Pod using 100m CPU, requests 200m CPU
HPA sees: 100m / 200m = 50% CPU utilization
If target is 50%, HPA won't scale
If target is 40%, HPA scales up
```

**Best practices:**
- Set requests based on **average** usage
- Set limits 1.5-3x higher than requests
- Always set both CPU and memory
- Missing requests = HPA can't calculate percentage!
- Missing limits = pod can consume entire node (risky)

**Debugging resource issues:**
```bash
# See actual resource usage
kubectl top pod <pod-name> -n scenarios

# See resource requests/limits
kubectl describe pod <pod-name> -n scenarios

# See node capacity
kubectl describe node
```

---

## 🌐 service.yaml

### What is a Service?
A Service provides a stable network endpoint for a set of pods. Pods are ephemeral (can be killed/recreated), but Services provide a consistent DNS name and IP.

### YAML Structure Breakdown:

```yaml
apiVersion: v1
```
**What it is:** Core Kubernetes API (v1)
**Why:** Services are fundamental, part of core API (not apps/v1 like Deployments)

```yaml
kind: Service
```
**What it is:** Declares this is a Service resource
**Purpose:** Load balance traffic across multiple pods

```yaml
metadata:
  name: hpa-demo-service
  namespace: scenarios
  labels:
    app: hpa-demo
```
**What it is:** Service metadata
- `name`: DNS name for the service (`hpa-demo-service.scenarios.svc.cluster.local`)
- `namespace`: Must match the pods it selects
- `labels`: Organize services (not used for selection)

**DNS resolution:**
- Same namespace: `http://hpa-demo-service`
- Different namespace: `http://hpa-demo-service.scenarios`
- Fully qualified: `http://hpa-demo-service.scenarios.svc.cluster.local`

```yaml
spec:
  type: ClusterIP
```
**What it is:** Service type - how the service is exposed

**Options:**
1. **ClusterIP** (default, used here):
   - Internal-only IP address
   - Accessible only within the cluster
   - **Use case:** Internal microservices, databases, this HPA demo

2. **NodePort**:
   - Exposes service on each node's IP at a static port (30000-32767)
   - Accessible from outside cluster: `http://<node-ip>:<node-port>`
   - **Use case:** Development, testing, legacy apps

3. **LoadBalancer**:
   - Provisions external cloud load balancer (AWS ELB, GCP LB, etc.)
   - Gets external IP address
   - **Use case:** Production services that need external access
   - **Cost:** Cloud providers charge for load balancers

4. **ExternalName**:
   - Maps service to external DNS name (CNAME record)
   - **Use case:** Accessing external services via Kubernetes DNS

**Why ClusterIP for HPA demo?**
- Don't need external access
- Load generator runs inside cluster
- More secure (no external exposure)
- Works on Kind/Minikube without cloud provider

```yaml
  selector:
    app: hpa-demo
```
**What it is:** How Service finds pods to route traffic to
**Critical:** Must match pod labels (from `deployment.yaml` → `template.metadata.labels`)

**How it works:**
1. Service continuously watches for pods with label `app: hpa-demo`
2. Adds matching pods to **endpoints** list
3. Distributes traffic across all healthy endpoints
4. Automatically removes failed pods from rotation
5. Load balances using round-robin (default)

**Check endpoints:**
```bash
kubectl get endpoints hpa-demo-service -n scenarios
```

**⚠️ Common issue:** No endpoints (0 pods selected)
- **Cause:** Selector doesn't match pod labels
- **Fix:** Ensure deployment's `template.metadata.labels` includes `app: hpa-demo`

```yaml
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
```
**What it is:** Port mapping configuration

**Fields:**
- `protocol`: TCP (default) or UDP
- `port`: Port the **Service** listens on (what clients connect to)
- `targetPort`: Port the **pod containers** listen on

**Example traffic flow:**
```
Client → Service:80 → Pod:80 → Container:80
```

**Advanced options:**
```yaml
ports:
- name: http           # Named port (useful with multiple ports)
  protocol: TCP
  port: 8080           # Service listens on 8080
  targetPort: http     # References named container port
  nodePort: 30080      # Only for NodePort/LoadBalancer type
```

**Named ports in deployment:**
```yaml
containers:
- name: php-apache
  ports:
  - name: http
    containerPort: 80
```

**Why use named ports?**
- Change container port without updating Service
- More readable configuration
- Consistent across multiple services

**Common patterns:**
```yaml
# Pattern 1: Simple (ports match)
port: 80
targetPort: 80

# Pattern 2: Port translation
port: 8080         # External facing
targetPort: 80     # Internal container

# Pattern 3: Named ports
port: 80
targetPort: http   # References container port name
```

### How Service Load Balancing Works:

1. **Service gets ClusterIP** (e.g., 10.96.45.123)
2. **DNS entry created:** `hpa-demo-service` → `10.96.45.123`
3. **kube-proxy** on each node watches Service
4. **iptables/IPVS rules** created to route traffic to pod IPs
5. **Traffic flow:**
   ```
   Client sends request to hpa-demo-service:80
   → DNS resolves to ClusterIP 10.96.45.123
   → kube-proxy routes to random pod IP (e.g., 10.244.1.5:80)
   → Pod receives request
   → Response sent back
   ```

**Load balancing algorithms:**
- **Round-robin** (default): Distributes evenly
- **Session affinity** (optional): Sticky sessions based on client IP

**Enable session affinity:**
```yaml
spec:
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800  # 3 hours
```

---

## 📊 hpa.yaml

### What is HPA (Horizontal Pod Autoscaler)?
HPA automatically scales the number of pods in a deployment based on observed metrics (CPU, memory, custom metrics). It's "horizontal" because it adds more pods (not "vertical" = bigger pods).

### YAML Structure Breakdown:

```yaml
apiVersion: autoscaling/v2
```
**What it is:** HPA API version
**History:**
- `autoscaling/v1` - Only CPU metrics (deprecated)
- `autoscaling/v2beta2` - Multiple metrics (beta)
- `autoscaling/v2` - **Current stable version** (multiple metrics, advanced features)

**Why v2?**
- Supports CPU, memory, and custom metrics
- Allows multiple metrics simultaneously
- Better scaling behavior configuration

```yaml
kind: HorizontalPodAutoscaler
```
**What it is:** Declares this is an HPA resource
**Purpose:** Watches metrics and adjusts replica count

```yaml
metadata:
  name: hpa-demo
  namespace: scenarios
```
**What it is:** HPA metadata
- `name`: Unique HPA name (one HPA per Deployment typically)
- `namespace`: Must match target Deployment namespace

```yaml
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hpa-demo-app
```
**What it is:** Specifies **what to scale**
**How it works:**
- HPA modifies `hpa-demo-app` Deployment's `spec.replicas` field
- Deployment controller creates/deletes pods to match new replica count

**scaleTargetRef fields:**
- `apiVersion`: Must match target resource (apps/v1 for Deployment)
- `kind`: Deployment (most common), StatefulSet, or ReplicaSet
- `name`: Exact name of the Deployment

**Why target Deployment (not pods directly)?**
- Deployments manage pods (create/delete)
- HPA only changes replica count
- Deployment handles the actual scaling work

**Can HPA target other resources?**
Yes! Examples:
```yaml
# Scale a StatefulSet
scaleTargetRef:
  apiVersion: apps/v1
  kind: StatefulSet
  name: my-stateful-app

# Scale a custom resource (if it implements /scale subresource)
scaleTargetRef:
  apiVersion: custom.io/v1
  kind: MyCustomResource
  name: my-app
```

```yaml
  minReplicas: 2
  maxReplicas: 10
```
**What it is:** Replica count boundaries

**minReplicas: 2**
- HPA will **never** scale below 2 pods
- Even if CPU is 0%, maintains 2 pods
- Ensures high availability
- Prevents scaling to zero (which would break the service)

**maxReplicas: 10**
- HPA will **never** scale above 10 pods
- Safety limit to prevent runaway scaling
- Protects cluster resources
- Prevents cost explosion in cloud environments

**Why these values?**
- **Min 2:** High availability, one pod can fail without downtime
- **Max 10:** Reasonable for demo, allows seeing significant scaling
- **Production example:** min: 3, max: 50 (depends on traffic patterns)

**Choosing min/max:**
- **Min:** Set to handle baseline traffic with one pod failure
- **Max:** Based on:
  - Cluster capacity
  - Budget constraints
  - Database/backend connection limits
  - Realistic maximum traffic expectations

```yaml
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
```
**What it is:** Metrics that trigger scaling

### 🔑 Understanding CPU Utilization (Most Important Part!)

**type: Resource**
- Built-in Kubernetes resource metrics (CPU, memory)
- **Alternatives:**
  - `Pods` - Custom pod metrics (e.g., requests per second)
  - `Object` - Metrics from other objects (e.g., Ingress requests)
  - `External` - External metrics (e.g., queue length, cloud metrics)

**resource.name: cpu**
- Monitor CPU usage
- **Alternative:** `memory` (for memory-based scaling)

**target.type: Utilization**
- Percentage of **requested** resources
- **Alternative:** `AverageValue` (absolute value, e.g., "200m")

**target.averageUtilization: 50**
- **Target: Keep average CPU at 50% of requested amount**

### How CPU Percentage is Calculated:

```
Example scenario:
- Deployment has 4 pods
- Each pod requests 200m CPU (from deployment.yaml)
- Pod 1 using: 120m
- Pod 2 using: 90m
- Pod 3 using: 110m
- Pod 4 using: 100m

Calculation:
Total usage: 120 + 90 + 110 + 100 = 420m
Total requested: 4 pods × 200m = 800m
Average utilization: 420m / 800m = 52.5%

HPA decision:
Target is 50%, current is 52.5%
52.5% > 50% → SCALE UP
Desired replicas = ceil(4 × 52.5 / 50) = ceil(4.2) = 5 pods
```

**Why 50% target?**
- 🔴 Too low (e.g., 10%): Wastes resources, over-provisioned
- 🟢 **50-70%:** **Recommended range** - efficient utilization with headroom
- 🟡 Too high (e.g., 90%): Risky, can't handle traffic spikes, scaling lags
- **50%:** Good balance - leaves 50% headroom for bursts while being efficient

### HPA Scaling Algorithm:

```
Desired Replicas = ceil(Current Replicas × Current Metric / Target Metric)
```

**Example 1: Scale Up**
```
Current: 2 pods, 80% CPU (target: 50%)
Desired = ceil(2 × 80 / 50) = ceil(3.2) = 4 pods
HPA scales from 2 → 4 pods
```

**Example 2: Scale Down**
```
Current: 6 pods, 20% CPU (target: 50%)
Desired = ceil(6 × 20 / 50) = ceil(2.4) = 3 pods
HPA scales from 6 → 3 pods (slowly!)
```

### Scaling Behavior & Timing:

**Scale-Up:**
- ✅ **Fast** - typically 1-3 minutes
- Triggered when: `current metric > target` (e.g., 80% > 50%)
- Can scale up multiple pods at once
- **Why fast?** Handle traffic spikes quickly

**Scale-Down:**
- 🐌 **Slow** - default 5 minutes stabilization window
- Triggered when: `current metric < target` (e.g., 20% < 50%)
- Conservative, gradual reduction
- **Why slow?** Prevent "flapping" (rapid up/down cycles)

**Default cooldown periods:**
- Scale-up cooldown: **3 minutes** (won't scale up again for 3 min after last scale-up)
- Scale-down cooldown: **5 minutes** (won't scale down for 5 min after last scale-down)

**Metric collection:**
- HPA checks metrics every **15 seconds** (default)
- Uses **Metrics Server** to get CPU/memory data
- Averages data over a window to smooth out spikes

### Advanced HPA Configuration (v2 features):

**Multiple metrics (scale on either CPU OR memory):**
```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 50
- type: Resource
  resource:
    name: memory
    target:
      type: Utilization
      averageUtilization: 70
```
**Behavior:** Scales based on whichever metric is higher

**Custom scaling behavior (v2 beta):**
```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 300    # Wait 5 min before scale down
    policies:
    - type: Percent
      value: 50                        # Max 50% of pods removed at once
      periodSeconds: 60                # Per minute
    - type: Pods
      value: 2                         # Max 2 pods removed at once
      periodSeconds: 60
    selectPolicy: Min                  # Use most conservative policy
  scaleUp:
    stabilizationWindowSeconds: 0      # Scale up immediately
    policies:
    - type: Percent
      value: 100                       # Max 100% increase (double)
      periodSeconds: 15                # Every 15 seconds
    - type: Pods
      value: 4                         # Max 4 pods added at once
      periodSeconds: 15
    selectPolicy: Max                  # Use most aggressive policy
```

**Custom metrics (Prometheus example):**
```yaml
metrics:
- type: Pods
  pods:
    metric:
      name: http_requests_per_second
    target:
      type: AverageValue
      averageValue: "1000"             # 1000 requests/sec per pod
```

**External metrics (AWS SQS queue example):**
```yaml
metrics:
- type: External
  external:
    metric:
      name: sqs_queue_length
      selector:
        matchLabels:
          queue: my-queue
    target:
      type: AverageValue
      averageValue: "30"               # 30 messages per pod
```

---

## 🔄 How Everything Works Together

### Complete Flow - Initialization:

1. **Apply deployment.yaml:**
   ```bash
   kubectl apply -f deployment.yaml
   ```
   - Deployment controller creates ReplicaSet
   - ReplicaSet creates 2 pods (spec.replicas: 2)
   - Scheduler assigns pods to nodes
   - Kubelet pulls `k8s.gcr.io/hpa-example` image
   - Containers start with 200m CPU request, 500m CPU limit
   - Pods enter Running state

2. **Apply service.yaml:**
   ```bash
   kubectl apply -f service.yaml
   ```
   - Service controller assigns ClusterIP (e.g., 10.96.45.123)
   - CoreDNS creates DNS entry: `hpa-demo-service` → ClusterIP
   - kube-proxy creates iptables rules on every node
   - Service watches for pods with label `app: hpa-demo`
   - Finds 2 pods, adds to endpoints list
   - Traffic to Service:80 routes to pods:80

3. **Apply hpa.yaml:**
   ```bash
   kubectl apply -f hpa.yaml
   ```
   - HPA controller starts monitoring `hpa-demo-app` deployment
   - Queries Metrics Server every 15 seconds for CPU usage
   - Calculates: `current CPU / requested CPU = X%`
   - Compares X% to target (50%)
   - Initially: Low traffic → 5-10% CPU → No scaling needed
   - HPA status shows: `TARGETS: 8%/50%`, `REPLICAS: 2`

### Complete Flow - Under Load:

4. **Generate load:**
   ```bash
   kubectl run load-generator --image=busybox -n scenarios \
     -- /bin/sh -c "while true; do wget -q -O- http://hpa-demo-service; done"
   ```
   - Load generator pod starts
   - Infinite loop sends HTTP requests to Service
   - Service load balances requests across 2 pods
   - Pods perform CPU-intensive PHP calculations
   - CPU usage climbs: 50m → 100m → 150m → 180m per pod

5. **HPA detects high CPU (after ~30 seconds):**
   ```
   Pod 1: 180m / 200m = 90% utilization
   Pod 2: 170m / 200m = 85% utilization
   Average: (90% + 85%) / 2 = 87.5%

   Target: 50%
   Decision: 87.5% > 50% → SCALE UP!

   Desired replicas = ceil(2 × 87.5 / 50) = ceil(3.5) = 4 pods
   ```

6. **HPA scales up:**
   - HPA updates Deployment: `spec.replicas: 2 → 4`
   - Deployment controller updates ReplicaSet
   - ReplicaSet creates 2 new pods
   - Scheduler assigns new pods to nodes
   - Kubelet starts new containers
   - New pods enter Running state (~30 seconds)
   - Service automatically adds new pods to endpoints
   - Load now distributed across 4 pods instead of 2

7. **Continued monitoring (CPU drops):**
   ```
   4 pods now handling same load:
   Each pod: ~90m CPU
   Utilization per pod: 90m / 200m = 45%
   Average across 4 pods: 45%

   Target: 50%
   Decision: 45% < 50% → STABLE (close enough)
   ```

8. **More load added → Scale up again:**
   ```
   Load doubles:
   Each of 4 pods: 160m CPU → 80% utilization
   Desired = ceil(4 × 80 / 50) = ceil(6.4) = 7 pods
   HPA scales: 4 → 7 pods
   ```

9. **Stop load generator:**
   ```bash
   # Press Ctrl+C to stop load generator
   ```
   - Load generator pod terminates
   - No more requests hitting Service
   - Pod CPU drops rapidly: 160m → 50m → 10m
   - Utilization: 10m / 200m = 5% per pod

10. **HPA scales down (after 5 min stabilization):**
    ```
    7 pods, 5% CPU average
    Desired = ceil(7 × 5 / 50) = ceil(0.7) = 1 pod

    But minReplicas: 2!
    HPA scales: 7 → 6 → 5 → 4 → 3 → 2 (stops at min)
    Scale-down is gradual (one or two pods at a time, over several minutes)
    ```

11. **Final state:**
    - 2 pods running (minReplicas enforced)
    - CPU: 5-10% (idle)
    - HPA status: `TARGETS: 8%/50%`, `REPLICAS: 2`
    - Ready for next load spike!

---

## 🎯 Best Practices & Production Recommendations

### 1. Resource Requests (CRITICAL!)
✅ **ALWAYS set CPU requests** when using HPA
- HPA cannot work without `resources.requests.cpu`
- Set requests based on **average** load, not peak
- Monitor actual usage with `kubectl top pod` and adjust

❌ **Common mistakes:**
```yaml
# WRONG - No requests (HPA won't work!)
resources:
  limits:
    cpu: 500m

# WRONG - Requests = limits (no burst capacity)
resources:
  requests:
    cpu: 500m
  limits:
    cpu: 500m

# RIGHT - Requests lower than limits
resources:
  requests:
    cpu: 200m      # Average usage
  limits:
    cpu: 500m      # Peak burst capacity
```

### 2. HPA Target Utilization
✅ **Recommended range: 50-70%**
- **50%:** Safe, good headroom for spikes
- **70%:** More efficient, less headroom
- **80%+:** Risky, can't handle sudden load

**Why not 90%?**
- Scaling takes 1-3 minutes
- By the time new pods are ready, existing pods may be overwhelmed
- Better to scale proactively than reactively

### 3. Min/Max Replicas
✅ **Set realistic bounds**
```yaml
minReplicas: 3        # Minimum for high availability (one can fail)
maxReplicas: 50       # Based on cluster capacity, budget
```

**Considerations:**
- **minReplicas:** High enough to handle baseline + one pod failure
- **maxReplicas:**
  - Cluster node capacity
  - Database connection pool limits
  - Budget constraints
  - Realistic maximum traffic (don't set to 1000 if you never get that much traffic)

### 4. Multiple Metrics
✅ **Use both CPU and memory for critical apps**
```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70
- type: Resource
  resource:
    name: memory
    target:
      type: Utilization
      averageUtilization: 80
```
HPA scales based on whichever metric is **higher** (most conservative)

### 5. Custom Metrics for Better Scaling
✅ **Scale on application-level metrics, not just CPU**

**Examples:**
- HTTP requests per second
- Queue length (Kafka, RabbitMQ, SQS)
- Active connections
- Response time / latency

**Why?**
- More accurate reflection of load
- CPU can be misleading (I/O-bound apps may have low CPU but high load)

**Example with custom metrics:**
```yaml
metrics:
- type: Pods
  pods:
    metric:
      name: http_requests_per_second
    target:
      type: AverageValue
      averageValue: "1000"    # Scale when > 1000 req/s per pod
```

### 6. Prevent Flapping (Rapid Scaling)
✅ **Use stabilization windows** (HPA v2)
```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 300    # Wait 5 min before scaling down
  scaleUp:
    stabilizationWindowSeconds: 60     # Wait 1 min before scaling up again
```

**Why?**
- Prevents rapid scale up → down → up cycles
- Saves resources (pod creation is expensive)
- Reduces noise in logs/monitoring

### 7. Testing HPA
✅ **Before production:**
```bash
# 1. Deploy and verify HPA is working
kubectl get hpa -n scenarios -w

# 2. Generate realistic load (not infinite loop)
kubectl run load-test --image=fortio/fortio \
  -- load -t 5m -qps 1000 http://hpa-demo-service

# 3. Monitor scaling
kubectl get hpa -n scenarios -w
kubectl get pods -n scenarios -w

# 4. Check pod resource usage
kubectl top pods -n scenarios

# 5. Verify scale-down after load stops
```

### 8. Monitoring & Alerts
✅ **Monitor HPA health**
- Alert if HPA shows `<unknown>` metrics (Metrics Server issue)
- Alert if HPA is at max replicas for extended time (may need higher max)
- Alert if HPA fails to scale (misconfigured selector, resource limits)

**Useful metrics:**
- `kube_hpa_status_current_replicas`
- `kube_hpa_status_desired_replicas`
- `kube_hpa_spec_max_replicas`
- `kube_hpa_spec_min_replicas`

### 9. Common Production Issues

**Issue 1: HPA shows `<unknown>` for CPU**
```bash
$ kubectl get hpa
NAME       REFERENCE               TARGETS         MINPODS   MAXPODS   REPLICAS
hpa-demo   Deployment/hpa-demo-app <unknown>/50%   2         10        0
```
**Causes:**
- Metrics Server not installed: `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml`
- Pods have no CPU requests
- Pods not yet running

**Issue 2: HPA doesn't scale despite high CPU**
**Causes:**
- Wrong selector (HPA targeting wrong deployment)
- Deployment at maxReplicas already
- Cluster out of resources (nodes full)

**Debug:**
```bash
kubectl describe hpa hpa-demo -n scenarios
kubectl top pods -n scenarios
kubectl get events -n scenarios --sort-by='.lastTimestamp'
```

**Issue 3: Pods get OOMKilled during scale-up**
**Cause:** Memory limits too low
**Fix:** Increase memory limits, or add memory-based HPA metric

### 10. Cost Optimization
✅ **Balance cost vs performance**
- Don't set minReplicas too high (wastes money when idle)
- Don't set target utilization too low (over-provisioned)
- Use cluster autoscaler to scale nodes based on pod demands
- Consider Vertical Pod Autoscaler (VPA) for right-sizing requests/limits

---

## 📚 Advanced Topics

### Vertical vs Horizontal Scaling

**Horizontal Scaling (HPA):**
- ✅ Adds more pods
- ✅ Works great for stateless apps
- ✅ Provides high availability
- ❌ Doesn't help if single pod is resource-constrained
- **Use when:** Load can be distributed (web servers, APIs)

**Vertical Scaling (VPA):**
- ✅ Increases pod size (more CPU/memory)
- ✅ Works for stateful apps
- ❌ Requires pod restart
- ❌ Limited by node size
- **Use when:** Single-threaded apps, databases

**Can use both together?**
- ⚠️ Experimental, can conflict
- VPA adjusts requests/limits → affects HPA calculations

### Cluster Autoscaler (CA)
- Scales **cluster nodes**, not pods
- Works alongside HPA:
  1. HPA scales pods up
  2. Pods can't be scheduled (no node capacity)
  3. CA adds new nodes
  4. Pods scheduled on new nodes
- Also scales down nodes when underutilized

**Flow:**
```
Traffic spike → HPA adds pods → Pods pending (no resources) →
CA adds nodes → Pods scheduled → Traffic handled
```

### HPA + PodDisruptionBudget (PDB)
- PDB prevents too many pods being terminated at once
- Important during:
  - HPA scale-down
  - Node maintenance
  - Cluster autoscaler scale-down

**Example PDB:**
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: hpa-demo-pdb
spec:
  minAvailable: 1        # At least 1 pod must be running
  selector:
    matchLabels:
      app: hpa-demo
```

**Why?**
- Prevents HPA + node drain from killing all pods simultaneously
- Ensures availability during scaling operations

---

## 🔍 Debugging Commands Reference

```bash
# Check HPA status
kubectl get hpa hpa-demo -n scenarios
kubectl describe hpa hpa-demo -n scenarios

# Watch HPA real-time
kubectl get hpa -n scenarios -w

# Check pod CPU/memory usage
kubectl top pods -n scenarios

# Check Metrics Server is working
kubectl top nodes
kubectl get apiservices v1beta1.metrics.k8s.io -o yaml

# View HPA events
kubectl get events -n scenarios --field-selector involvedObject.name=hpa-demo

# Check deployment replica count
kubectl get deployment hpa-demo-app -n scenarios

# View HPA metrics in JSON (detailed)
kubectl get hpa hpa-demo -n scenarios -o json | jq .status

# Check if pods have resource requests
kubectl get pods -n scenarios -o json | jq '.items[].spec.containers[].resources'

# Force HPA to recalculate (edit something trivial)
kubectl annotate hpa hpa-demo force-sync=$(date +%s) -n scenarios
```

---

## 🎓 Key Takeaways

1. **HPA requires CPU requests** - Without them, HPA shows `<unknown>` and doesn't work
2. **Target 50-70% utilization** - Balance efficiency and headroom
3. **Set realistic min/max** - Protect cluster and budget
4. **Scale-up is fast, scale-down is slow** - By design, prevents flapping
5. **Monitor with `kubectl get hpa -w`** - Real-time scaling visibility
6. **Metrics Server is required** - Install before using HPA
7. **Custom metrics > CPU** - For production, scale on application metrics
8. **Test under load** - Ensure HPA works before production traffic

---

*This explanation provides deep insights into HPA and Kubernetes resource management. Start with the basics (deployment with requests, simple HPA), then progressively explore advanced topics like multiple metrics, custom scaling behavior, and production monitoring!*
