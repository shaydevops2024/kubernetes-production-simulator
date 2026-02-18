# YAML Files Explanation - Rolling Updates Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 🔄 deployment.yaml

### What is a Rolling Update?
A rolling update gradually replaces instances of the previous version of an application with the new version without downtime. Kubernetes orchestrates this process by incrementally creating new pods and terminating old ones while maintaining service availability.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
```
**What it is:** The API version for Deployment resources
**Options:** `apps/v1` is the current stable version
**Why:** Deployments are part of the `apps` API group, which manages application controllers

```yaml
kind: Deployment
```
**What it is:** Declares this is a Deployment resource
**Purpose:** Manages a replicated application with declarative updates
**Why use Deployment?**
- Declarative updates (just change the spec, Kubernetes handles the rest)
- Automatic rollback capabilities
- Revision history tracking
- Rolling updates with zero downtime

**Alternatives:**
- `StatefulSet` - For stateful apps needing persistent identity (databases, Kafka)
- `DaemonSet` - One pod per node (monitoring agents, log collectors)
- `ReplicaSet` - Lower-level controller (Deployments create ReplicaSets)
- `Job/CronJob` - Run-to-completion tasks

```yaml
metadata:
  name: rolling-demo
  namespace: scenarios
  labels:
    app: rolling-demo
    scenario: "05"
```
**What it is:** Metadata identifying the Deployment
- `name`: Unique identifier within the namespace
- `namespace`: Logical isolation boundary for resources
- `labels`: Key-value pairs for organization and selection

**Why labels?**
- Services use labels to select pods
- Filter resources: `kubectl get deploy -l app=rolling-demo`
- Monitoring and alerting queries
- Organizational categorization

**Best practices:**
- Use consistent label keys across your organization
- Common keys: `app`, `version`, `environment`, `component`, `managed-by`
- Keep label values short and meaningful
- Avoid special characters

```yaml
spec:
  replicas: 3
```
**What it is:** Desired number of pod copies
**Options:** Any integer ≥ 0
**Why 3 replicas?**
- High availability (survives 1-2 pod failures)
- Load distribution across multiple instances
- Allows for gradual rolling updates (update 1 pod at a time)
- Good balance for demo purposes

**Production considerations:**
- **Development:** 1-2 replicas (cost-effective)
- **Staging:** 2-3 replicas (similar to production)
- **Production:** 3+ replicas (high availability)
- Consider using HPA (Horizontal Pod Autoscaler) for dynamic scaling

**What happens:**
- Kubernetes ensures exactly 3 pods are running at all times
- If a pod crashes, a new one is automatically created
- If you scale manually (`kubectl scale`), this number is updated
- During rolling updates, pod count may temporarily exceed or be below this number

```yaml
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
```
**What it is:** Update strategy configuration

### 🔑 CRITICAL for Zero-Downtime Updates!

**type: RollingUpdate**
- Gradually replaces old pods with new pods
- Maintains service availability during updates
- **Alternative:** `Recreate` - terminates all old pods before creating new ones (causes downtime)

**When to use Recreate:**
- Development/testing environments where downtime is acceptable
- Apps that can't run multiple versions simultaneously
- Apps with database migration constraints
- Faster updates (but with downtime)

**rollingUpdate.maxSurge: 1**
**What it means:** Maximum number of **extra** pods that can be created above the desired replica count during update

**Calculation:**
```
With replicas: 3, maxSurge: 1
Maximum pods during update: 3 + 1 = 4 pods
```

**Values:**
- `1` (integer) - Exactly 1 extra pod
- `25%` (percentage) - 25% of desired replicas (rounded up)
- `0` - No surge allowed (conservative updates)

**Why use maxSurge?**
- **Faster rollouts:** New pods can start before old ones terminate
- **Better availability:** More capacity during transition
- **Smoother updates:** Reduces risk of capacity issues

**Trade-offs:**
- ✅ **High maxSurge (e.g., 50%):** Fast updates, more temporary resource usage
- ✅ **Low maxSurge (e.g., 0-1):** Conservative, less resource spike
- ✅ **maxSurge: 100%:** "Blue-Green" style - double capacity temporarily

**rollingUpdate.maxUnavailable: 1**
**What it means:** Maximum number of pods that can be **unavailable** during update

**Calculation:**
```
With replicas: 3, maxUnavailable: 1
Minimum pods during update: 3 - 1 = 2 pods must stay healthy
```

**Values:**
- `1` (integer) - Exactly 1 pod can be unavailable
- `25%` (percentage) - 25% of desired replicas can be unavailable
- `0` - All pods must be available (safest, slowest)

**Why use maxUnavailable?**
- Controls risk during updates
- Ensures minimum service capacity
- Balances speed vs. safety

**Important:** maxSurge and maxUnavailable **cannot both be 0**!

**Common patterns:**

```yaml
# Pattern 1: Fast updates (aggressive)
maxSurge: 100%
maxUnavailable: 50%
# Creates all new pods, then terminates old ones
# Very fast, but uses 2x resources temporarily

# Pattern 2: Conservative (default-ish)
maxSurge: 25%
maxUnavailable: 25%
# Balanced approach for most use cases

# Pattern 3: Resource-constrained
maxSurge: 0
maxUnavailable: 1
# One-at-a-time replacement, minimal resource spike
# Slower but uses less extra resources

# Pattern 4: Maximum availability (used in this scenario)
maxSurge: 1
maxUnavailable: 1
# Updates 2 pods at a time (1 down, 1 extra up)
# Good balance of speed and safety
```

**Update flow with maxSurge:1, maxUnavailable:1 (3 replicas):**
```
Step 1: Create 1 new pod (v2)
  Old: Pod1(v1), Pod2(v1), Pod3(v1)
  New: Pod4(v2)
  Total: 4 pods (maxSurge allows +1)

Step 2: Terminate 1 old pod once new pod is Ready
  Old: Pod2(v1), Pod3(v1)
  New: Pod4(v2)
  Total: 3 pods

Step 3: Create another new pod (v2)
  Old: Pod2(v1), Pod3(v1)
  New: Pod4(v2), Pod5(v2)
  Total: 4 pods

Step 4: Terminate another old pod
  Old: Pod3(v1)
  New: Pod4(v2), Pod5(v2)
  Total: 3 pods

Step 5: Create final new pod (v2)
  Old: Pod3(v1)
  New: Pod4(v2), Pod5(v2), Pod6(v2)
  Total: 4 pods

Step 6: Terminate last old pod
  New: Pod4(v2), Pod5(v2), Pod6(v2)
  Total: 3 pods

Update complete! Zero downtime.
```

```yaml
  selector:
    matchLabels:
      app: rolling-demo
```
**What it is:** How the Deployment finds its pods
**Critical:** Must match `template.metadata.labels` exactly
**Why:** Deployments don't create pods directly - they create ReplicaSets, which create pods

**How it works:**
1. Deployment creates a ReplicaSet with this selector
2. ReplicaSet creates pods with matching labels
3. ReplicaSet continuously monitors for pods with these labels
4. If pods are deleted, ReplicaSet creates new ones

**Options:**
- `matchLabels`: Simple key-value equality (most common)
- `matchExpressions`: Advanced selection logic

**Example with matchExpressions:**
```yaml
selector:
  matchExpressions:
  - key: app
    operator: In
    values: [rolling-demo, rolling-demo-v2]
  - key: environment
    operator: NotIn
    values: [test]
```

**⚠️ Common mistake:** Selector and template labels don't match → Deployment can't find pods → 0/3 pods ready

**⚠️ Important:** Once a Deployment is created, the selector is **immutable** - you can't change it!

```yaml
  template:
    metadata:
      labels:
        app: rolling-demo
        version: v1
```
**What it is:** Pod template - blueprint for creating pods
**Why:** Defines what each replica will look like
**Labels:**
- **Must** include all selector labels (`app: rolling-demo`)
- **Can** include additional labels (`version: v1`)

**Why add extra labels like `version`?**
- Track which version of the app is running
- Enable canary deployments (route traffic to specific versions)
- Debugging and monitoring
- Pod-level filtering

**Important:** Changing the template triggers a **rolling update**!
- Changing image → Rolling update
- Changing labels → Rolling update
- Changing env vars → Rolling update
- Changing resources → Rolling update

```yaml
    spec:
      containers:
      - name: app
        image: nginx:1.20-alpine
```
**What it is:** Container specification
- `name`: Container name within pod (for `kubectl logs`, `kubectl exec`)
- `image`: Docker image to run

**About nginx:1.20-alpine:**
- `nginx` - Web server
- `1.20` - Specific version (pinned for reproducibility)
- `alpine` - Lightweight Linux distribution (~5MB vs ~133MB)

**Image tagging best practices:**
- ✅ **Pin specific versions:** `nginx:1.21.6-alpine` (reproducible, safe)
- ❌ **Avoid `:latest`:** `nginx:latest` (breaks reproducibility, risky)
- ✅ **Use alpine for smaller images:** `nginx:alpine` (faster pulls, less storage)
- ✅ **Use official images:** `nginx` from Docker Hub (trusted, maintained)
- ✅ **Use SHA256 digests for max reproducibility:** `nginx@sha256:abc123...` (immutable)

**Why version matters in rolling updates:**
- Rolling updates are triggered by image changes
- Different versions allow gradual migration
- Version pinning prevents unexpected updates
- Enables easy rollback to previous versions

```yaml
        ports:
        - containerPort: 80
```
**What it is:** Port the container listens on
**Purpose:** Documentation and discovery
**Note:** Doesn't actually open the port - containers can listen on any port

**When it matters:**
- Network policies (firewall rules)
- Service discovery
- Documentation for developers
- Some service meshes use this info

**Advanced usage:**
```yaml
ports:
- name: http        # Named port (can reference in Service)
  containerPort: 80
  protocol: TCP     # TCP (default) or UDP
  hostPort: 8080    # Expose on host (rarely used)
```

```yaml
        resources:
          requests:
            cpu: 100m
            memory: 64Mi
          limits:
            cpu: 200m
            memory: 128Mi
```
**What it is:** Resource requirements and constraints

**Requests (guaranteed resources):**
- `cpu: 100m` = 100 millicores = 0.1 CPU cores
- `memory: 64Mi` = 64 mebibytes RAM

**What "requests" means:**
- Kubernetes **guarantees** this much CPU/memory
- Scheduler only places pod on nodes with available resources
- Used for pod placement decisions
- Billing/accounting in cloud environments

**Limits (maximum resources):**
- `cpu: 200m` = 200 millicores = 0.2 CPU cores (can burst up to this)
- `memory: 128Mi` = 128 mebibytes RAM (hard limit)

**What "limits" means:**
- Container **cannot exceed** memory limit (killed if it tries - OOMKilled)
- Container can burst to CPU limit (throttled if exceeds)
- Protects cluster from resource hogging

**Why these specific values for nginx?**
- **100m CPU request:** Nginx is lightweight, doesn't need much
- **200m CPU limit:** Allows 2x burst for traffic spikes
- **64Mi memory request:** Minimal for serving static content
- **128Mi memory limit:** Prevents memory leaks from affecting cluster

**CPU units:**
- `1000m` = `1` = 1 full CPU core
- `100m` = 0.1 cores (10% of one core)
- `2000m` = `2` = 2 full CPU cores

**Memory units:**
- `Mi` = Mebibyte (1024^2 bytes) - **binary** (preferred)
- `M` = Megabyte (1000^2 bytes) - decimal
- `Gi` = Gibibyte (1024^3 bytes)
- `G` = Gigabyte (1000^3 bytes)

**Why set both requests and limits?**
- ✅ **Requests:** Ensure pod gets minimum resources
- ✅ **Limits:** Prevent runaway processes
- ✅ **Both:** QoS class "Burstable" (good balance)
- ❌ **Only limits:** QoS "BestEffort" (can be evicted easily)
- ✅ **Requests = Limits:** QoS "Guaranteed" (highest priority, no burst)

**Resource impact on rolling updates:**
```
With replicas: 3, maxSurge: 1
Temporary resource usage during update:
- CPU: 4 pods × 100m request = 400m (vs 300m normally)
- Memory: 4 pods × 64Mi request = 256Mi (vs 192Mi normally)

Ensure your cluster has spare capacity!
```

**Best practices:**
- Set requests based on **average** usage
- Set limits 1.5-3x higher than requests (allows bursting)
- Always set both CPU and memory
- Monitor actual usage with `kubectl top pod`
- Adjust over time based on real metrics

---

## 🌐 service.yaml

### What is a Service?
A Service provides a stable network endpoint (ClusterIP and DNS name) for accessing a set of pods. Since pods are ephemeral and can be replaced during rolling updates, Services provide a consistent way to reach your application.

### YAML Structure Breakdown:

```yaml
apiVersion: v1
```
**What it is:** Core Kubernetes API (v1)
**Why:** Services are fundamental networking primitives, part of the core API

```yaml
kind: Service
```
**What it is:** Declares this is a Service resource
**Purpose:** Load balances traffic across a set of pods

**Why Services are critical for rolling updates:**
- Pods are replaced during updates (new IPs each time)
- Service IP remains constant
- Service DNS name remains constant
- Automatically routes traffic only to healthy pods
- Removes pods from rotation during termination

```yaml
metadata:
  name: rolling-demo-service
  namespace: scenarios
```
**What it is:** Service metadata
- `name`: DNS name for the service
- `namespace`: Must match the pods it selects

**DNS resolution:**
Services automatically get DNS entries:
- Same namespace: `rolling-demo-service` or `rolling-demo-service.scenarios`
- Different namespace: `rolling-demo-service.scenarios.svc.cluster.local`
- Fully qualified: `rolling-demo-service.scenarios.svc.cluster.local`

**Example usage in another pod:**
```bash
# Short form (same namespace)
curl http://rolling-demo-service

# Cross-namespace
curl http://rolling-demo-service.scenarios

# Fully qualified (works from anywhere)
curl http://rolling-demo-service.scenarios.svc.cluster.local
```

```yaml
spec:
  type: ClusterIP
```
**What it is:** Service type - how the service is exposed

**Options:**

1. **ClusterIP** (default, used here):
   - Internal-only IP address
   - Accessible only within the cluster
   - **Use case:** Internal microservices, this rolling update demo
   - **Why for rolling updates:** Demonstrates zero-downtime - internal traffic continues

2. **NodePort**:
   - Exposes service on each node's IP at a static port (30000-32767)
   - Accessible from outside: `http://<node-ip>:<node-port>`
   - **Use case:** Development, testing, legacy apps
   - **During updates:** External clients see no interruption

3. **LoadBalancer**:
   - Provisions external cloud load balancer (AWS ELB, GCP LB, etc.)
   - Gets external IP address
   - **Use case:** Production services needing external access
   - **During updates:** Cloud LB continues routing to healthy pods
   - **Cost:** Cloud providers charge for load balancers

4. **ExternalName**:
   - Maps service to external DNS name (CNAME)
   - **Use case:** Accessing external services via Kubernetes DNS

**Why ClusterIP for rolling updates demo?**
- Don't need external access for demo
- Simpler setup (works on Kind/Minikube)
- Focus on update mechanics, not external networking
- More secure (no external exposure)

```yaml
  selector:
    app: rolling-demo
```
**What it is:** How Service finds pods to route traffic to
**Critical:** Must match pod labels from Deployment's `template.metadata.labels`

### 🔑 How Services Enable Zero-Downtime Updates

**How it works during rolling updates:**

1. **Initial state (v1 pods):**
   ```
   Service watches for pods with label app: rolling-demo
   Finds: Pod1(v1), Pod2(v1), Pod3(v1)
   Endpoints: 3 pods
   Traffic routes to all 3
   ```

2. **During update (mixed v1/v2):**
   ```
   Deployment creates Pod4(v2)
   Pod4 becomes Ready
   Service automatically adds Pod4 to endpoints
   Endpoints: Pod1(v1), Pod2(v1), Pod3(v1), Pod4(v2)
   Traffic now routes to all 4 pods (including new v2)

   Deployment terminates Pod1(v1)
   Pod1 enters Terminating state
   Service removes Pod1 from endpoints
   Endpoints: Pod2(v1), Pod3(v1), Pod4(v2)
   No traffic sent to terminating pod
   ```

3. **Final state (all v2):**
   ```
   All old pods terminated, all new pods created
   Service finds: Pod4(v2), Pod5(v2), Pod6(v2)
   Endpoints: 3 pods (all v2)
   Traffic routes to new version
   ```

**Key points:**
- Service selector doesn't change during updates
- Both old and new pods match the selector
- Service automatically manages endpoints
- Only Ready pods receive traffic
- Terminating pods are removed from rotation
- **Result:** Zero downtime!

**Check endpoints in real-time:**
```bash
# Watch endpoints during update
kubectl get endpoints rolling-demo-service -n scenarios -w

# See which pod IPs are in rotation
kubectl describe endpoints rolling-demo-service -n scenarios
```

**⚠️ Common issue:** No endpoints (0 pods selected)
- **Cause:** Selector doesn't match pod labels
- **Fix:** Ensure Deployment's `template.metadata.labels` includes `app: rolling-demo`

**How Service load balances:**
- Round-robin distribution (default)
- Distributes across all healthy endpoints
- No awareness of pod version (treats v1 and v2 equally)
- Client connects to Service IP, Service routes to random pod

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

**Traffic flow:**
```
Client → Service:80 → Pod:80 → Container:80
```

**Example with different ports:**
```yaml
ports:
- port: 8080           # Service listens on 8080
  targetPort: 80       # Forwards to pod port 80

# Client connects to service:8080
# Service forwards to pod:80
```

**Named ports (advanced):**
```yaml
# In deployment.yaml
containers:
- name: app
  ports:
  - name: http
    containerPort: 80

# In service.yaml
ports:
- port: 80
  targetPort: http     # References named port (not number)
```

**Why use named ports?**
- Change container port without updating Service
- More readable configuration
- Consistent across services

**Port during rolling updates:**
- Service port never changes
- New pods must listen on same targetPort as old pods
- Incompatible port changes require new Service (or multi-port setup)

---

## 🔄 How Everything Works Together During Rolling Updates

### Complete Update Flow:

1. **Initial deployment (v1):**
   ```bash
   kubectl apply -f deployment.yaml -f service.yaml
   ```
   - Deployment controller creates ReplicaSet (revision 1)
   - ReplicaSet creates 3 pods with nginx:1.20
   - Pods start, pass readiness checks, enter Running state
   - Service finds 3 pods with label `app: rolling-demo`
   - Service creates 3 endpoints (pod IPs)
   - Service gets ClusterIP (e.g., 10.96.100.50)
   - DNS entry created: `rolling-demo-service` → ClusterIP
   - Traffic can now reach pods via Service

2. **Trigger update (v1 → v2):**
   ```bash
   kubectl set image deployment/rolling-demo app=nginx:1.21-alpine
   ```
   - Deployment spec is updated (image changed)
   - Deployment controller creates new ReplicaSet (revision 2)
   - Old ReplicaSet (revision 1) still exists but will be scaled down

3. **Rolling update begins:**

   **Time T+0s:**
   ```
   Old ReplicaSet (v1): 3 pods (Pod1, Pod2, Pod3)
   New ReplicaSet (v2): 0 pods
   Service endpoints: 3 (all v1)
   ```

   **Time T+5s:**
   ```
   maxSurge allows +1 pod
   New ReplicaSet creates Pod4(v2)
   Pod4 starts, pulls nginx:1.21 image

   Old ReplicaSet: 3 pods (Pod1, Pod2, Pod3)
   New ReplicaSet: 1 pod (Pod4) - Starting
   Service endpoints: 3 (all v1)
   ```

   **Time T+15s:**
   ```
   Pod4 passes readiness probe
   Service adds Pod4 to endpoints

   Old ReplicaSet: 3 pods (Pod1, Pod2, Pod3)
   New ReplicaSet: 1 pod (Pod4) - Ready
   Service endpoints: 4 (3×v1 + 1×v2)

   Traffic now goes to both v1 and v2 pods!
   ```

   **Time T+20s:**
   ```
   maxUnavailable allows -1 pod
   Old ReplicaSet terminates Pod1
   Pod1 receives SIGTERM, enters Terminating state
   Service removes Pod1 from endpoints

   Old ReplicaSet: 2 pods (Pod2, Pod3) + 1 Terminating (Pod1)
   New ReplicaSet: 1 pod (Pod4)
   Service endpoints: 3 (2×v1 + 1×v2)
   ```

   **Time T+25s:**
   ```
   Pod1 fully terminated
   maxSurge allows creating another new pod
   New ReplicaSet creates Pod5(v2)

   Old ReplicaSet: 2 pods (Pod2, Pod3)
   New ReplicaSet: 2 pods (Pod4, Pod5-Starting)
   Service endpoints: 3 (2×v1 + 1×v2)
   ```

   **Time T+35s:**
   ```
   Pod5 ready
   Service adds Pod5 to endpoints
   Old ReplicaSet terminates Pod2

   Old ReplicaSet: 1 pod (Pod3) + 1 Terminating (Pod2)
   New ReplicaSet: 2 pods (Pod4, Pod5)
   Service endpoints: 3 (1×v1 + 2×v2)
   ```

   **Time T+40s:**
   ```
   Pod2 terminated
   New ReplicaSet creates Pod6(v2)

   Old ReplicaSet: 1 pod (Pod3)
   New ReplicaSet: 3 pods (Pod4, Pod5, Pod6-Starting)
   Service endpoints: 3 (1×v1 + 2×v2)
   ```

   **Time T+50s:**
   ```
   Pod6 ready
   Service adds Pod6 to endpoints
   Old ReplicaSet terminates Pod3

   Old ReplicaSet: 1 Terminating (Pod3)
   New ReplicaSet: 3 pods (Pod4, Pod5, Pod6)
   Service endpoints: 4 (1×v1 + 3×v2)
   ```

   **Time T+55s:**
   ```
   Pod3 terminated
   Old ReplicaSet scaled to 0

   Old ReplicaSet: 0 pods (kept for rollback)
   New ReplicaSet: 3 pods (Pod4, Pod5, Pod6)
   Service endpoints: 3 (all v2)
   ```

4. **Update complete:**
   - All pods running nginx:1.21
   - Service still using same ClusterIP
   - DNS name unchanged
   - Clients experienced no downtime
   - Old ReplicaSet kept in history for rollback

5. **Rollback (if needed):**
   ```bash
   kubectl rollout undo deployment/rolling-demo
   ```
   - Reverses the process
   - Old ReplicaSet (revision 1) scaled up
   - New ReplicaSet (revision 2) scaled down
   - Same rolling update strategy applies
   - Zero downtime on rollback too!

---

## 🎯 Best Practices for Rolling Updates

### 1. Always Set Resource Limits
✅ **DO:**
```yaml
resources:
  requests:
    cpu: 100m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 128Mi
```

❌ **DON'T:**
```yaml
# No resources defined
# Can cause resource exhaustion during updates
```

**Why:** Without limits, rolling updates can consume all cluster resources

### 2. Use Readiness Probes
✅ **DO:**
```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 5
```

**Why:**
- New pods only receive traffic when Ready
- Prevents sending traffic to pods still starting up
- Crucial for zero-downtime updates

### 3. Use Liveness Probes (with care)
✅ **DO:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 80
  initialDelaySeconds: 30  # Higher than readiness
  periodSeconds: 10
```

**Why:**
- Restarts unhealthy pods
- Prevents stuck pods during updates
- **Important:** initialDelaySeconds should be higher than readiness to avoid restart loops

### 4. Choose the Right Update Strategy
**Conservative (production):**
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```
- Slowest updates
- Maximum availability
- No capacity reduction during updates

**Balanced (recommended):**
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 1
```
- Good balance of speed and safety
- Used in this scenario

**Aggressive (development):**
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 100%
    maxUnavailable: 50%
```
- Fastest updates
- Requires 2x temporary resources
- Higher risk

### 5. Use PodDisruptionBudgets (Production)
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: rolling-demo-pdb
spec:
  minAvailable: 2      # At least 2 pods must be available
  selector:
    matchLabels:
      app: rolling-demo
```

**Why:**
- Prevents rolling updates from terminating too many pods at once
- Ensures minimum capacity during updates
- Protects against cascading failures

### 6. Track Changes with Annotations
✅ **DO:**
```bash
kubectl annotate deployment/rolling-demo \
  kubernetes.io/change-cause="Updated to nginx:1.21" \
  --overwrite
```

**Why:**
- Shows up in `kubectl rollout history`
- Helps track what changed in each revision
- Critical for debugging and auditing

### 7. Monitor Rollouts
```bash
# Watch rollout progress
kubectl rollout status deployment/rolling-demo -n scenarios

# Check rollout history
kubectl rollout history deployment/rolling-demo -n scenarios

# Watch pods during update
kubectl get pods -n scenarios -w

# Check service endpoints during update
kubectl get endpoints rolling-demo-service -n scenarios -w
```

### 8. Test Rollbacks Before Production
```bash
# Rollback to previous revision
kubectl rollout undo deployment/rolling-demo

# Rollback to specific revision
kubectl rollout undo deployment/rolling-demo --to-revision=2

# Check rollout history shows all revisions
kubectl rollout history deployment/rolling-demo
```

### 9. Set revisionHistoryLimit
```yaml
spec:
  revisionHistoryLimit: 10  # Keep last 10 revisions (default)
```

**Options:**
- `10` - Default, good for most cases
- `5` - Minimal storage, still allows rollback
- `3` - Very conservative storage
- `0` - Disables rollback (not recommended)

**Why:**
- Limits storage of old ReplicaSets
- Enables rollback to previous versions
- Balance history vs. cluster storage

### 10. Avoid Breaking Changes
**Compatible updates (safe):**
- Image version changes (nginx:1.20 → nginx:1.21)
- Resource limit adjustments
- Non-breaking env variable changes
- Label additions

**Incompatible updates (risky):**
- Port changes (requires Service update)
- Breaking API changes
- Database schema migrations
- Volume mount path changes

**For breaking changes:**
- Use blue-green deployments
- Create new Deployment + Service
- Gradually migrate traffic
- Delete old deployment when done

---

## 🔍 Debugging Rolling Updates

### Update Stuck or Slow

**Check rollout status:**
```bash
kubectl rollout status deployment/rolling-demo -n scenarios
```

**Check pod status:**
```bash
kubectl get pods -n scenarios -l app=rolling-demo
```

**Common issues:**
- New pods stuck in `ImagePullBackOff` - Wrong image name/tag
- New pods stuck in `Pending` - Insufficient cluster resources
- New pods stuck in `CrashLoopBackOff` - Application error
- Readiness probe failing - App not ready or probe misconfigured

**Describe deployment:**
```bash
kubectl describe deployment rolling-demo -n scenarios
```
Look for events showing errors or warnings

**Check ReplicaSets:**
```bash
kubectl get replicasets -n scenarios -l app=rolling-demo
```
Should see old RS (scaled to 0) and new RS (scaled to desired replicas)

### Rollback if Update Fails

**Immediate rollback:**
```bash
kubectl rollout undo deployment/rolling-demo -n scenarios
```

**Check available revisions:**
```bash
kubectl rollout history deployment/rolling-demo -n scenarios
```

**Rollback to specific revision:**
```bash
kubectl rollout undo deployment/rolling-demo -n scenarios --to-revision=2
```

**Pause a stuck rollout:**
```bash
kubectl rollout pause deployment/rolling-demo -n scenarios
# Fix issues
kubectl rollout resume deployment/rolling-demo -n scenarios
```

### Service Not Routing to New Pods

**Check endpoints:**
```bash
kubectl get endpoints rolling-demo-service -n scenarios
kubectl describe endpoints rolling-demo-service -n scenarios
```

**Common issues:**
- No endpoints - Selector doesn't match pod labels
- Wrong pod IPs - Pods not Ready (failing readiness probe)
- Endpoints not updating - Service controller issue (rare)

**Verify selector matches:**
```bash
# Check Service selector
kubectl get service rolling-demo-service -n scenarios -o yaml | grep -A 5 selector

# Check pod labels
kubectl get pods -n scenarios -l app=rolling-demo --show-labels
```

---

## 📚 Advanced Topics

### Canary Deployments
Run old and new versions simultaneously, gradually shift traffic:
```yaml
# Old deployment (90% of pods)
replicas: 9

# New deployment (10% of pods)
replicas: 1

# Same Service selector routes to both
```

### Blue-Green Deployments
Two separate deployments, switch Service selector:
```yaml
# Blue (old)
metadata:
  labels:
    app: myapp
    version: blue

# Green (new)
metadata:
  labels:
    app: myapp
    version: green

# Service selector
selector:
  app: myapp
  version: blue  # Switch to 'green' when ready
```

### Progressive Delivery (Advanced)
Use tools like Flagger or Argo Rollouts for:
- Automated canary analysis
- Metrics-based rollback
- A/B testing
- Gradual traffic shifting

---

## 🎓 Key Takeaways

1. **Rolling updates enable zero-downtime deployments** by gradually replacing old pods with new ones
2. **maxSurge and maxUnavailable control update speed** and resource usage
3. **Services automatically manage endpoints** during updates, routing only to Ready pods
4. **Readiness probes are critical** - new pods don't receive traffic until Ready
5. **Kubernetes keeps revision history** enabling easy rollback with `kubectl rollout undo`
6. **Annotations track change-cause** for better visibility in rollout history
7. **Both updates and rollbacks use the same rolling strategy** - both are zero-downtime
8. **Resource limits prevent update failures** by ensuring cluster has capacity for extra pods
9. **PodDisruptionBudgets protect availability** during updates in production
10. **Always test rollbacks** before deploying to production

---

*This explanation provides comprehensive insights into rolling updates and how Kubernetes orchestrates zero-downtime deployments. Start with the basics (deployment strategy, maxSurge/maxUnavailable), then explore advanced topics like canary deployments and progressive delivery!*
