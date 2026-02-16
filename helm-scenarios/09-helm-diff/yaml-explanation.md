# Helm Diff Plugin Explanation - Complete Guide

This guide provides a comprehensive explanation of the Helm diff plugin, how it works, and how to use values files to preview changes before applying them. You'll learn to read diff output, understand change impacts, and build confidence in production deployments.

---

## 🎯 What is the Helm Diff Plugin?

**Helm diff** is a plugin that compares a Helm release against a proposed upgrade, showing exactly what Kubernetes resources will change BEFORE any changes are applied to your cluster.

### The Problem It Solves

**Without helm diff:**
```bash
# Hope for the best and apply changes
helm upgrade my-app bitnami/nginx -f new-values.yaml
# ⚠️ What changed? No way to know until it's applied!
# ⚠️ Unexpected changes might break production
# ⚠️ No preview, no rollback until after damage is done
```

**With helm diff:**
```bash
# Preview changes first
helm diff upgrade my-app bitnami/nginx -f new-values.yaml
# ✅ See exactly what will change
# ✅ Review before applying
# ✅ Catch unintended changes
# ✅ Build confidence

# Then apply if everything looks good
helm upgrade my-app bitnami/nginx -f new-values.yaml
```

### Why It Matters

- **Production Safety**: Never deploy blind - see changes first
- **Change Review**: Catch unintended configuration drift
- **Compliance**: Document what changes before approval
- **Learning**: Understand how values affect rendered manifests
- **CI/CD Integration**: Gate deployments on diff approval

### Real-World Use Cases

**1. Preventing Outages:**
```bash
# You think you're updating CPU limits...
helm diff upgrade my-app bitnami/nginx -f values.yaml

# But diff reveals service type changed to NodePort!
# (would expose internal service publicly)
```

**2. Validating Configuration:**
```bash
# Did my value override actually work?
helm diff upgrade my-app bitnami/nginx --set replicaCount=3

# Diff shows replicas: 1 → 3 ✅
```

**3. Drift Detection:**
```bash
# After manual kubectl edits, what's different?
helm diff upgrade my-app bitnami/nginx -f values.yaml

# Shows resources that drifted from Helm's expected state
```

---

## 🔧 How Helm Diff Works

### Under the Hood

1. **Fetch Current Release**: Gets deployed manifests from Helm history
2. **Render Proposed Chart**: Renders chart with new values locally
3. **Compare Manifests**: Diffs current vs proposed YAML
4. **Display Changes**: Shows colorized diff output

**Key Point**: Nothing is applied to the cluster. It's a **read-only preview**.

### Comparison Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Current State (deployed)                                    │
│ - Fetch from Helm release history                          │
│ - helm status my-app shows: revision 1                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Compare
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Proposed State (local render)                               │
│ - Render chart with new values                             │
│ - helm template my-app bitnami/nginx -f new-values.yaml    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Output
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Diff Output                                                 │
│ + Added lines (green)                                       │
│ - Removed lines (red)                                       │
│ ~ Changed lines (yellow)                                    │
│   Context lines (white)                                     │
└─────────────────────────────────────────────────────────────┘
```

### What Gets Compared

**All Kubernetes resources managed by the release:**
- Deployments
- Services
- ConfigMaps
- Secrets
- Ingresses
- StatefulSets
- DaemonSets
- Jobs/CronJobs
- Custom Resources (CRDs)

**Metadata included:**
- Labels
- Annotations
- Resource versions
- Namespaces

---

## 📊 Reading Diff Output

### Diff Syntax Basics

Helm diff uses standard unified diff format (like `git diff`):

```diff
# Context lines (unchanged)
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: my-app

# Removed lines (in current, not in proposed)
- replicas: 1
# Added lines (not in current, will be in proposed)
+ replicas: 3

# Changed lines (old → new)
~ image: nginx:1.21
+ image: nginx:1.25
```

### Color Coding (Terminal Output)

| Color | Symbol | Meaning |
|-------|--------|---------|
| **Green** | `+` | Line will be **added** |
| **Red** | `-` | Line will be **removed** |
| **Yellow** | `~` | Line will be **changed** |
| **White** | ` ` | Context (unchanged) |

### Example Diff Output

```diff
diff-demo, diff-demo-nginx, Deployment (apps) has changed:
  # Source: nginx/templates/deployment.yaml
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    labels:
-     app-version: v1
+     app-version: v2
      app.kubernetes.io/instance: diff-demo
      app.kubernetes.io/name: nginx
    name: diff-demo-nginx
    namespace: helm-scenarios
  spec:
-   replicas: 1
+   replicas: 3
    selector:
      matchLabels:
        app.kubernetes.io/instance: diff-demo
        app.kubernetes.io/name: nginx
    template:
      metadata:
        labels:
-         app-version: v1
+         app-version: v2
          app.kubernetes.io/instance: diff-demo
          app.kubernetes.io/name: nginx
      spec:
        containers:
        - name: nginx
          resources:
            limits:
-             cpu: 100m
+             cpu: 200m
-             memory: 128Mi
+             memory: 256Mi
            requests:
              cpu: 50m
              memory: 64Mi
```

**What this tells you:**
- **Replicas**: 1 → 3 (scaling up)
- **Labels**: app-version v1 → v2
- **CPU limit**: 100m → 200m (doubled)
- **Memory limit**: 128Mi → 256Mi (doubled)

### Interpreting Resource Changes

**Deployment changes:**
- ✅ `replicas`: Safe, scales pods
- ⚠️ `image`: Triggers rolling update
- ⚠️ `strategy`: Changes rollout behavior
- ❌ `selector`: **DANGEROUS** - can't change on existing Deployment

**Service changes:**
- ✅ `port`: Usually safe
- ⚠️ `type`: ClusterIP → NodePort (changes exposure)
- ⚠️ `selector`: Changes which pods receive traffic
- ❌ `type`: LoadBalancer → ClusterIP (removes external IP)

**ConfigMap/Secret changes:**
- ⚠️ Data changes: May require pod restart to take effect
- ✅ Labels/annotations: Safe metadata changes

---

## 📄 values-v1.yaml - Field-by-Field Explanation

### Full File

```yaml
# values-v1.yaml
# Initial deployment values for the nginx release.
# This represents the "current state" of our deployment.

# Single replica for initial deployment
replicaCount: 1

# Resource limits suitable for a Kind cluster
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 100m
    memory: 128Mi

# ClusterIP service (internal only)
service:
  type: ClusterIP
  port: 80

# Simple server block returning version info
serverBlock: |-
  server {
    listen 0.0.0.0:8080;
    location /version {
      return 200 "v1.0.0\n";
    }
    location /healthz {
      return 200 "healthy\n";
    }
    location / {
      return 200 "Hello from diff-demo v1!\n";
    }
  }

# Common labels applied to all resources
commonLabels:
  app-version: "v1"
  scenario: helm-diff
```

### replicaCount: 1

**What it is:** Number of pod replicas to run

**Default (Bitnami nginx):** `1`

**Our value:** `1` (using default)

**Why 1 for v1:**
- ✅ **Minimal resources**: Single pod for initial deployment
- ✅ **Fast startup**: Quick to deploy and test
- ✅ **Development-friendly**: Low overhead on Kind cluster
- ⚠️ **No high availability**: Single point of failure

**Production considerations:**
```yaml
# Development
replicaCount: 1

# Staging
replicaCount: 2

# Production
replicaCount: 3  # Minimum for HA across availability zones
```

**How it affects the cluster:**
```bash
# Deployment spec.replicas = 1
kubectl get deployment diff-demo-nginx -n helm-scenarios
# READY: 1/1

kubectl get pods -n helm-scenarios
# 1 pod running
```

---

### resources

```yaml
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 100m
    memory: 128Mi
```

**What it is:** CPU and memory allocation for each pod

#### requests.cpu: 50m

**Meaning:** 50 millicores = 0.05 CPU cores = 5% of one CPU

**Purpose:** **Guaranteed** CPU allocation
- Kubernetes scheduler only places pod on nodes with 50m available
- Pod is **guaranteed** to get at least 50m CPU
- Can use more if available (up to limit)

**Kind cluster context:**
- Kind nodes typically have access to host CPU
- 50m is minimal, suitable for nginx serving static content
- Won't interfere with other workloads

#### requests.memory: 64Mi

**Meaning:** 64 Mebibytes = 67,108,864 bytes ≈ 64 MB

**Purpose:** **Guaranteed** memory allocation
- Kubernetes guarantees 64Mi of memory
- Pod won't be scheduled without this much available
- If exceeded, pod may be evicted (if exceeds limit)

**nginx memory usage:**
- Base nginx: ~10-20 MB
- 64Mi leaves room for configuration, connections, buffers
- Conservative for Kind cluster

#### limits.cpu: 100m

**Meaning:** 100 millicores = 0.1 CPU cores = 10% of one CPU

**Purpose:** **Maximum** CPU allowed
- Pod can burst up to 100m CPU
- If tries to use more, CPU is **throttled** (not killed)
- Prevents runaway processes from starving other pods

**Burst capacity:**
- Requests: 50m
- Limits: 100m
- **Burst ratio: 2x** (can double CPU during spikes)

**CPU throttling behavior:**
```
Normal load: 30m → No throttling
Spike: 80m → No throttling (under limit)
Heavy spike: 150m → Throttled to 100m
```

#### limits.memory: 128Mi

**Meaning:** 128 Mebibytes = 134,217,728 bytes ≈ 128 MB

**Purpose:** **Maximum** memory allowed
- Pod can use up to 128Mi
- If exceeds, pod is **killed** with OOMKilled (Out Of Memory)
- Prevents memory leaks from affecting cluster

**Burst capacity:**
- Requests: 64Mi
- Limits: 128Mi
- **Burst ratio: 2x** (can double memory during spikes)

**Memory limit behavior:**
```
Normal: 40Mi → Running fine
Spike: 100Mi → Running fine (under limit)
Memory leak: 130Mi → Pod killed (OOMKilled), restarted
```

#### Quality of Service (QoS) Class

With these settings, the pod gets **Burstable** QoS:

**QoS Classes:**

| Class | Condition | Priority | Eviction Order |
|-------|-----------|----------|----------------|
| **Guaranteed** | requests = limits | Highest | Last |
| **Burstable** | requests < limits | Medium | Middle |
| **BestEffort** | No requests/limits | Lowest | First |

**Our pod: Burstable**
- Not evicted unless exceeds memory limit
- Medium priority during node resource pressure
- Can burst beyond requests for performance

**Check pod QoS:**
```bash
kubectl get pod <pod-name> -n helm-scenarios -o jsonpath='{.status.qosClass}'
# Output: Burstable
```

---

### service

```yaml
service:
  type: ClusterIP
  port: 80
```

**What it is:** Kubernetes Service configuration for accessing nginx

#### service.type: ClusterIP

**What it is:** Service type that controls how the service is exposed

**Default (Bitnami nginx):** `LoadBalancer` (cloud provider LB)

**Our override:** `ClusterIP` (internal only)

**Service Types Comparison:**

| Type | Accessibility | IP Assignment | Use Case |
|------|---------------|---------------|----------|
| **ClusterIP** | Internal only | Cluster-internal IP | Microservices, databases |
| **NodePort** | External via Node IP:Port | Cluster IP + Node port | Development, testing |
| **LoadBalancer** | External via cloud LB | Cluster IP + External IP | Production (AWS, GCP, Azure) |
| **ExternalName** | DNS CNAME | None | External service proxy |

**ClusterIP behavior:**
```bash
# Service gets internal IP
kubectl get svc diff-demo-nginx -n helm-scenarios
# TYPE: ClusterIP
# CLUSTER-IP: 10.96.100.50 (example)

# Accessible from inside cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://diff-demo-nginx.helm-scenarios.svc.cluster.local

# NOT accessible from outside cluster
curl http://localhost:80  # ❌ Won't work
```

**Why ClusterIP for v1:**
- ✅ **Internal testing**: Can test from inside cluster
- ✅ **Secure**: Not exposed to external network
- ✅ **Standard microservice pattern**: Services communicate internally

**DNS resolution:**
```
Short name: diff-demo-nginx
Namespace-qualified: diff-demo-nginx.helm-scenarios
FQDN: diff-demo-nginx.helm-scenarios.svc.cluster.local
```

#### service.port: 80

**What it is:** Port the Service listens on (cluster-internal)

**How it maps:**
```
Client → Service Port 80 → Container Port 8080
```

**Port configuration explained:**
- **service.port: 80** - What clients connect to
- **targetPort: 8080** - Where container listens (nginx default from Bitnami chart)
- Bitnami chart automatically sets targetPort

**Why port 80:**
- Standard HTTP port
- Easy to remember
- Follows convention (even though container uses 8080)

**Testing from inside cluster:**
```bash
# From another pod
curl http://diff-demo-nginx:80

# From outside pod (port-forward)
kubectl port-forward svc/diff-demo-nginx 8080:80 -n helm-scenarios
curl http://localhost:8080
```

---

### serverBlock

```yaml
serverBlock: |-
  server {
    listen 0.0.0.0:8080;
    location /version {
      return 200 "v1.0.0\n";
    }
    location /healthz {
      return 200 "healthy\n";
    }
    location / {
      return 200 "Hello from diff-demo v1!\n";
    }
  }
```

**What it is:** Custom nginx configuration block injected into nginx.conf

**YAML syntax: `|-`**
- `|` = Literal block scalar (preserves newlines)
- `-` = Strip final trailing newlines
- Preserves indentation and formatting of nginx config

#### How It Gets Used

**Bitnami nginx chart:**
1. Reads `serverBlock` value
2. Creates ConfigMap with nginx configuration
3. Mounts ConfigMap into pod at `/opt/bitnami/nginx/conf/server_blocks/`
4. nginx includes this in main configuration

**Resulting ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: diff-demo-nginx-server-block
data:
  server-block.conf: |
    server {
      listen 0.0.0.0:8080;
      ...
    }
```

#### listen 0.0.0.0:8080

**Syntax:** `listen <address>:<port>;`

**What it does:**
- nginx binds to all network interfaces (`0.0.0.0`)
- Listens on TCP port 8080

**Why 0.0.0.0:**
- ✅ Accepts connections from any network interface
- Required for Service to route traffic to pod
- Alternative: `127.0.0.1` would only accept localhost (doesn't work in pods)

**Why port 8080:**
- ✅ **Non-privileged port**: Ports < 1024 require root access
- ✅ **Security**: Container runs as non-root user (UID 1001)
- ✅ **Best practice**: Never run nginx as root in containers

**Security context (from Bitnami chart):**
```yaml
securityContext:
  runAsUser: 1001  # Non-root user
  runAsNonRoot: true
```

#### location /version

```nginx
location /version {
  return 200 "v1.0.0\n";
}
```

**What it does:** Returns version string for this deployment

**nginx directive breakdown:**
- `location /version` - Matches requests to `/version` path
- `return 200` - HTTP status code 200 (OK)
- `"v1.0.0\n"` - Response body (version string + newline)

**Testing:**
```bash
# Inside cluster
curl http://diff-demo-nginx/version
# Output: v1.0.0

# Outside cluster (after port-forward)
kubectl port-forward svc/diff-demo-nginx 8080:80 -n helm-scenarios
curl http://localhost:8080/version
# Output: v1.0.0
```

**Why include version endpoint:**
- ✅ **Deployment verification**: Confirms correct version deployed
- ✅ **Troubleshooting**: Identify which version is running
- ✅ **Monitoring**: Health checks can verify version
- ✅ **Diff demonstration**: Clearly shows v1 → v2 change

**Production pattern:**
```nginx
location /version {
  return 200 '{"version":"v1.0.0","build":"abc123","date":"2024-01-15"}\n';
  add_header Content-Type application/json;
}
```

#### location /healthz

```nginx
location /healthz {
  return 200 "healthy\n";
}
```

**What it does:** Health check endpoint for Kubernetes probes

**Purpose:**
- **Liveness probe**: Kubernetes checks if container is alive
- **Readiness probe**: Kubernetes checks if pod can receive traffic
- **Load balancer**: Only routes traffic to healthy pods

**Kubernetes probe configuration (typically in chart templates):**
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

**Health check behavior:**
```bash
# Kubernetes continuously polls
curl http://<pod-ip>:8080/healthz
# Response 200 "healthy" → Pod marked Ready
# Response 500 or timeout → Pod marked NotReady, no traffic routed
```

**Why simple health check for nginx:**
- nginx rarely fails in a way /healthz would catch
- More sophisticated checks for app servers:
  ```nginx
  location /healthz {
    access_log off;
    proxy_pass http://localhost:9000/health;  # App health endpoint
  }
  ```

#### location /

```nginx
location / {
  return 200 "Hello from diff-demo v1!\n";
}
```

**What it does:** Catch-all route for all other paths

**nginx location matching:**
```
Request: /version → Matches /version (exact)
Request: /healthz → Matches /healthz (exact)
Request: /anything → Matches / (catch-all)
Request: /static/file.jpg → Matches / (catch-all)
```

**Testing:**
```bash
curl http://diff-demo-nginx/
# Output: Hello from diff-demo v1!

curl http://diff-demo-nginx/anything
# Output: Hello from diff-demo v1!
```

**Production alternative (serve static files):**
```nginx
location / {
  root /usr/share/nginx/html;
  index index.html index.htm;
  try_files $uri $uri/ /index.html;
}
```

**Production alternative (reverse proxy):**
```nginx
location / {
  proxy_pass http://backend-service:8000;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
}
```

---

### commonLabels

```yaml
commonLabels:
  app-version: "v1"
  scenario: helm-diff
```

**What it is:** Key-value pairs added to **all resources** created by the chart

**Applied to:**
- Deployment (metadata and template)
- Service
- ConfigMap
- Any other resources in the chart

**Why labels matter:**

**1. Organization:**
```bash
# Get all resources for this scenario
kubectl get all -n helm-scenarios -l scenario=helm-diff
```

**2. Filtering:**
```bash
# Get only v1 resources
kubectl get all -n helm-scenarios -l app-version=v1

# Get v2 resources
kubectl get all -n helm-scenarios -l app-version=v2
```

**3. Diff visibility:**
- Labels appear in diff output
- Easy to see version changes: `app-version: v1` → `app-version: v2`

**4. Service selector (important!):**
```yaml
# Service uses labels to find pods
selector:
  app-version: v1  # Only routes traffic to v1 pods
```

**Label best practices:**

✅ **Good labels:**
```yaml
commonLabels:
  app.kubernetes.io/name: nginx
  app.kubernetes.io/instance: diff-demo
  app.kubernetes.io/version: "v1.0.0"
  app.kubernetes.io/component: webserver
  app.kubernetes.io/part-of: demo-app
  environment: learning
  owner: platform-team
```

❌ **Bad labels:**
```yaml
commonLabels:
  "my label": "value"  # Spaces not allowed
  version: 1.0.0  # Should be string: "1.0.0"
  Env: Production  # Inconsistent casing
```

**Label constraints:**
- Max key length: 253 characters (prefix) + 63 characters (name)
- Max value length: 63 characters
- Valid characters: alphanumeric, `-`, `_`, `.`
- Must start and end with alphanumeric

---

## 📄 values-v2.yaml - What Changed

### Full File with Changes Annotated

```yaml
# values-v2.yaml
# Updated deployment values for the nginx release.
# Changes from v1:
#   - replicaCount: 1 -> 3 (scale up for high availability)
#   - service.type: ClusterIP -> NodePort (expose externally)
#   - resources.limits.cpu: 100m -> 200m (increased CPU limit)
#   - resources.limits.memory: 128Mi -> 256Mi (increased memory limit)
#   - serverBlock: updated version endpoint to v2.0.0
#   - commonLabels.app-version: v1 -> v2

# Scale up to 3 replicas for high availability
replicaCount: 3  # ← CHANGED from 1

# Increase resource limits for production-like workload
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m     # ← CHANGED from 100m
    memory: 256Mi # ← CHANGED from 128Mi

# Switch to NodePort to expose externally
service:
  type: NodePort  # ← CHANGED from ClusterIP
  port: 80
  nodePorts:
    http: "30090"  # ← NEW: NodePort assignment

# Updated server block with new version
serverBlock: |-
  server {
    listen 0.0.0.0:8080;
    location /version {
      return 200 "v2.0.0\n";  # ← CHANGED from v1.0.0
    }
    location /healthz {
      return 200 "healthy\n";
    }
    location / {
      return 200 "Hello from diff-demo v2!\n";  # ← CHANGED from v1
    }
  }

# Updated labels
commonLabels:
  app-version: "v2"  # ← CHANGED from v1
  scenario: helm-diff
```

### Change Analysis

#### Change 1: replicaCount: 1 → 3

**Impact:**
- ✅ **High Availability**: 3 pods across (potentially) 3 nodes
- ✅ **Load Distribution**: Requests distributed across 3 pods
- ✅ **Resilience**: Can lose 2 pods and still serve traffic
- ⚠️ **Resource Usage**: 3× pod resources (CPU, memory, storage)

**Diff output:**
```diff
  spec:
-   replicas: 1
+   replicas: 3
```

**Kubernetes behavior:**
1. Deployment creates 2 additional pods
2. Waits for pods to be Ready
3. Service automatically load-balances across all 3 pods

**Rollout timeline:**
```bash
# Before
kubectl get pods -n helm-scenarios
# diff-demo-nginx-abc123 1/1 Running

# During upgrade
# diff-demo-nginx-abc123 1/1 Running
# diff-demo-nginx-def456 1/1 Running
# diff-demo-nginx-ghi789 0/1 ContainerCreating

# After
# diff-demo-nginx-abc123 1/1 Running
# diff-demo-nginx-def456 1/1 Running
# diff-demo-nginx-ghi789 1/1 Running
```

#### Change 2: resources.limits.cpu: 100m → 200m

**Impact:**
- ✅ **Better Performance**: Can burst to 200m during traffic spikes
- ✅ **Less Throttling**: Reduced CPU throttling events
- ⚠️ **More Resources**: Requires nodes with more available CPU

**Diff output:**
```diff
          resources:
            limits:
-             cpu: 100m
+             cpu: 200m
```

**CPU burst capacity:**
```
v1: 50m request → 100m limit (2x burst)
v2: 50m request → 200m limit (4x burst)
```

**When this matters:**
- High traffic bursts (e.g., marketing campaign)
- Computationally expensive nginx configs (Lua scripts, SSI)
- Many concurrent connections

#### Change 3: resources.limits.memory: 128Mi → 256Mi

**Impact:**
- ✅ **More Headroom**: Less likely to hit OOMKilled
- ✅ **Better Caching**: More memory for nginx buffers
- ⚠️ **More Resources**: Requires nodes with more available memory

**Diff output:**
```diff
          resources:
            limits:
-             memory: 128Mi
+             memory: 256Mi
```

**Memory burst capacity:**
```
v1: 64Mi request → 128Mi limit (2x burst)
v2: 64Mi request → 256Mi limit (4x burst)
```

**Why double memory:**
- nginx can cache more files
- More connection buffers
- Room for configuration/modules

#### Change 4: service.type: ClusterIP → NodePort

**Impact:**
- ✅ **External Access**: Can access from outside cluster
- ⚠️ **Security**: Exposed on all nodes (use firewall rules)
- ⚠️ **Port Range**: NodePort must be 30000-32767

**Diff output:**
```diff
  spec:
    ports:
-   - port: 80
+   - nodePort: 30090
+     port: 80
      protocol: TCP
      targetPort: 8080
-   type: ClusterIP
+   type: NodePort
```

**Access patterns:**

**v1 (ClusterIP):**
```bash
# Only from inside cluster
curl http://diff-demo-nginx.helm-scenarios.svc.cluster.local
```

**v2 (NodePort):**
```bash
# From inside cluster
curl http://diff-demo-nginx.helm-scenarios.svc.cluster.local

# From outside cluster
curl http://<node-ip>:30090

# Get node IP
kubectl get nodes -o wide
```

**Kind cluster access:**
```bash
# Map node port to localhost (if Kind doesn't expose automatically)
kubectl port-forward svc/diff-demo-nginx 30090:80 -n helm-scenarios

# Access via localhost
curl http://localhost:30090
```

**Production consideration:**
- ✅ **Development**: NodePort is fine
- ⚠️ **Production**: Use LoadBalancer or Ingress instead

```yaml
# Production alternative
service:
  type: LoadBalancer  # Cloud provider creates external LB
  # or
  type: ClusterIP  # Use with Ingress controller
```

#### Change 5: nodePorts.http: "30090"

**Impact:**
- ✅ **Predictable Port**: Always 30090 (not random)
- ✅ **Documentation**: Easy to document and share
- ⚠️ **Conflicts**: Port must be available on all nodes

**Diff output:**
```diff
+   nodePorts:
+     http: "30090"
```

**Why specify NodePort:**
```yaml
# Without nodePorts (random assignment)
service:
  type: NodePort
  # Kubernetes assigns random port: 30000-32767

# With nodePorts (deterministic)
service:
  type: NodePort
  nodePorts:
    http: "30090"  # Always this port
```

**NodePort selection tips:**
- Choose from range: 30000-32767
- Avoid common ports: 30000, 30080 (often used)
- Document in README
- Check availability: `kubectl get svc --all-namespaces | grep NodePort`

#### Change 6: serverBlock version: v1.0.0 → v2.0.0

**Impact:**
- ✅ **Deployment Verification**: Confirms new version deployed
- ✅ **Diff Visibility**: Easy to see configuration changes

**Diff output:**
```diff
  serverBlock: |
    server {
      listen 0.0.0.0:8080;
      location /version {
-       return 200 "v1.0.0\n";
+       return 200 "v2.0.0\n";
      }
```

**Verification:**
```bash
# After upgrade
curl http://<service>/version
# Output: v2.0.0 ✅

# If still showing v1.0.0:
# - Check pod age (might be old pod)
# - Check ConfigMap (might not be updated)
# - Restart pods to pick up new config
```

**ConfigMap update behavior:**
- Chart creates/updates ConfigMap with new serverBlock
- **Existing pods** may still use old ConfigMap (cached)
- **New pods** (from replica change) get new ConfigMap
- To force update: `kubectl rollout restart deployment diff-demo-nginx -n helm-scenarios`

#### Change 7: location / message: v1 → v2

**Impact:**
- ✅ **User-visible change**: Different response message
- ✅ **Diff demonstration**: Clear visual change

**Diff output:**
```diff
      location / {
-       return 200 "Hello from diff-demo v1!\n";
+       return 200 "Hello from diff-demo v2!\n";
      }
```

**Testing:**
```bash
curl http://<service>/
# v1: Hello from diff-demo v1!
# v2: Hello from diff-demo v2!
```

#### Change 8: commonLabels.app-version: v1 → v2

**Impact:**
- ✅ **Resource Tracking**: Easy to identify v2 resources
- ⚠️ **Service Selector**: May affect traffic routing (if selector uses this label)
- ⚠️ **Rolling Update**: Deployment selector immutable, label change triggers recreation

**Diff output:**
```diff
  metadata:
    labels:
-     app-version: v1
+     app-version: v2
```

**Applied to:**
- Deployment metadata
- Pod template metadata
- Service metadata
- ConfigMap metadata

**Important note about selectors:**

**If Service selector includes app-version:**
```yaml
# Service selector
selector:
  app-version: v2  # ← Only routes to v2 pods!
```

**This could cause issues:**
- During rolling update, v1 pods exist
- Service selector changed to `app-version: v2`
- v1 pods receive no traffic (even though Running)
- Potential downtime until v2 pods ready

**Best practice:**
- Don't use version labels in selectors
- Use immutable labels: `app.kubernetes.io/name`, `app.kubernetes.io/instance`

---

## 🔄 How Components Work Together

### Deployment Flow

```
1. Initial Install (v1)
   ├─ helm install diff-demo bitnami/nginx -f values-v1.yaml
   ├─ Helm renders templates with v1 values
   ├─ Creates:
   │  ├─ Deployment (1 replica)
   │  ├─ Service (ClusterIP)
   │  ├─ ConfigMap (serverBlock v1)
   │  └─ Pods (1 pod)
   └─ Release: diff-demo revision 1

2. Preview Changes (v2)
   ├─ helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml
   ├─ Helm renders templates with v2 values (locally)
   ├─ Compares:
   │  ├─ Deployment: replicas 1→3, resources changed
   │  ├─ Service: ClusterIP→NodePort
   │  ├─ ConfigMap: serverBlock v1→v2
   │  └─ Labels: app-version v1→v2
   └─ Shows diff (NO changes applied)

3. Apply Upgrade (v2)
   ├─ helm upgrade diff-demo bitnami/nginx -f values-v2.yaml
   ├─ Helm applies changes to cluster
   ├─ Rolling update:
   │  ├─ ConfigMap updated (v2 serverBlock)
   │  ├─ Service updated (NodePort, port 30090)
   │  ├─ Deployment updated (replicas, resources)
   │  ├─ Creates 2 new pods (v2)
   │  ├─ Waits for new pods Ready
   │  └─ Terminates old pod (v1)
   └─ Release: diff-demo revision 2

4. Verify No Drift
   ├─ helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml
   ├─ Compares deployed state vs proposed state
   └─ No diff = No drift ✅
```

### Resource Relationships

```
Release: diff-demo
├─ Deployment: diff-demo-nginx
│  ├─ ReplicaSet: diff-demo-nginx-abc123 (v1, old)
│  │  └─ Pod: diff-demo-nginx-abc123-xyz (terminated)
│  └─ ReplicaSet: diff-demo-nginx-def456 (v2, current)
│     ├─ Pod: diff-demo-nginx-def456-aaa (Running)
│     ├─ Pod: diff-demo-nginx-def456-bbb (Running)
│     └─ Pod: diff-demo-nginx-def456-ccc (Running)
├─ Service: diff-demo-nginx
│  ├─ Type: NodePort
│  ├─ ClusterIP: 10.96.100.50
│  ├─ Port: 80 → TargetPort 8080
│  ├─ NodePort: 30090
│  └─ Selector: app.kubernetes.io/instance=diff-demo
│     └─ Routes to all 3 v2 pods
└─ ConfigMap: diff-demo-nginx-server-block
   └─ Data: server-block.conf (v2 configuration)
      └─ Mounted in pods at /opt/bitnami/nginx/conf/server_blocks/
```

### Traffic Flow

**v1 (ClusterIP):**
```
Internal Client
  → Service (ClusterIP 10.96.100.50:80)
    → Pod (8080)
      → nginx /version → "v1.0.0"
```

**v2 (NodePort):**
```
External Client
  → Node (any node IP:30090)
    → Service (forwards to 10.96.100.50:80)
      → Pod 1, 2, or 3 (round-robin, 8080)
        → nginx /version → "v2.0.0"

Internal Client
  → Service (ClusterIP 10.96.100.50:80)
    → Pod 1, 2, or 3 (round-robin, 8080)
      → nginx /version → "v2.0.0"
```

---

## 🎓 Practical Examples

### Example 1: Preview a Single Value Change

```bash
# Preview changing just replicas
helm diff upgrade diff-demo bitnami/nginx \
  --set replicaCount=5 \
  -n helm-scenarios

# Diff shows:
# - replicas: 3
# + replicas: 5
```

### Example 2: Preview Multiple Files

```bash
# Layer values: base → environment
helm diff upgrade diff-demo bitnami/nginx \
  -f values-base.yaml \
  -f values-prod.yaml \
  -n helm-scenarios

# prod-values.yaml overrides base-values.yaml
```

### Example 3: Compare to Specific Revision

```bash
# Show changes since revision 1
helm diff revision diff-demo 1 2 -n helm-scenarios

# Shows diff between revision 1 and 2
```

### Example 4: Suppress Irrelevant Changes

```bash
# Hide secrets (sensitive data)
helm diff upgrade diff-demo bitnami/nginx \
  -f values-v2.yaml \
  --suppress-secrets \
  -n helm-scenarios

# Hide hooks (pre-install, post-upgrade jobs)
helm diff upgrade diff-demo bitnami/nginx \
  -f values-v2.yaml \
  --suppress-hooks \
  -n helm-scenarios
```

### Example 5: Output Formats

```bash
# Default: colorized diff
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml

# JSON output (for CI/CD parsing)
helm diff upgrade diff-demo bitnami/nginx \
  -f values-v2.yaml \
  --output json

# Simple format (less verbose)
helm diff upgrade diff-demo bitnami/nginx \
  -f values-v2.yaml \
  --output simple
```

### Example 6: Diff in CI/CD Pipeline

```yaml
# .gitlab-ci.yml example
preview-changes:
  stage: review
  script:
    - helm plugin install https://github.com/databus23/helm-diff
    - |
      helm diff upgrade my-app ./chart -f values-prod.yaml \
        -n production > diff-output.txt
    - cat diff-output.txt
    - |
      if [ -s diff-output.txt ]; then
        echo "Changes detected - review required"
        exit 1  # Fail to require manual approval
      fi
  artifacts:
    paths:
      - diff-output.txt
```

### Example 7: Detect Configuration Drift

```bash
# Compare deployed state vs desired state
helm diff upgrade diff-demo bitnami/nginx \
  -f values-v2.yaml \
  -n helm-scenarios

# No output = No drift (cluster matches values file)
# Output = Drift detected (manual changes or stale values)

# Common causes of drift:
# - kubectl edit deployment (manual change)
# - kubectl scale (manual scaling)
# - kubectl set image (manual image update)
# - Forgotten values file changes
```

### Example 8: Preview Chart Upgrade

```bash
# Check what changes in new chart version
helm diff upgrade diff-demo bitnami/nginx \
  --version 16.0.0 \
  -f values-v2.yaml \
  -n helm-scenarios

# Shows:
# - Changes from chart update (new features, bug fixes)
# - Template changes
# - Default value changes
```

---

## 🐛 Troubleshooting

### Issue: No diff output when expected

**Problem:**
```bash
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml
# (no output)
```

**Possible causes:**

**1. Release not installed:**
```bash
helm list -n helm-scenarios
# If diff-demo not listed, install first:
helm install diff-demo bitnami/nginx -f values-v1.yaml -n helm-scenarios
```

**2. Values file identical to deployed state:**
```bash
# Check deployed values
helm get values diff-demo -n helm-scenarios

# Compare to your values file
diff <(helm get values diff-demo -n helm-scenarios) values-v2.yaml
```

**3. Wrong namespace:**
```bash
# Specify namespace explicitly
helm diff upgrade diff-demo bitnami/nginx \
  -f values-v2.yaml \
  -n helm-scenarios  # ← Don't forget!
```

### Issue: Plugin not installed

**Error:**
```
Error: unknown command "diff" for "helm"
```

**Solution:**
```bash
# Install plugin
helm plugin install https://github.com/databus23/helm-diff

# Verify installation
helm plugin list
# NAME    VERSION    DESCRIPTION
# diff    3.9.4      Preview helm upgrade changes as a diff
```

**Update plugin:**
```bash
helm plugin update diff
```

**Uninstall plugin:**
```bash
helm plugin uninstall diff
```

### Issue: Diff shows unexpected changes

**Problem:**
```bash
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml
# Shows changes you didn't make in values-v2.yaml
```

**Possible causes:**

**1. Chart version changed:**
```bash
# Check current chart version
helm list -n helm-scenarios -o yaml | grep chart:

# Lock to specific version
helm diff upgrade diff-demo bitnami/nginx \
  --version 15.9.0 \
  -f values-v2.yaml
```

**2. Chart repository updated:**
```bash
# Repository has new chart version
helm repo update

# Use --version to lock version
helm diff upgrade diff-demo bitnami/nginx \
  --version 15.9.0 \
  -f values-v2.yaml
```

**3. Chart defaults changed:**
```bash
# New chart version has different defaults
helm show values bitnami/nginx --version 15.9.0 > old-defaults.yaml
helm show values bitnami/nginx --version 16.0.0 > new-defaults.yaml
diff old-defaults.yaml new-defaults.yaml
```

### Issue: Cannot read diff output (too large)

**Problem:**
```bash
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml
# Hundreds of lines scroll by too fast
```

**Solutions:**

**1. Use pager:**
```bash
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml | less
# Navigate with arrow keys, 'q' to quit
```

**2. Save to file:**
```bash
helm diff upgrade diff-demo bitnami/nginx \
  -f values-v2.yaml > diff.txt
code diff.txt  # Open in editor
```

**3. Filter output:**
```bash
# Only show added lines
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml | grep '^+'

# Only show removed lines
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml | grep '^-'

# Search for specific resource
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml | grep -A 20 'kind: Deployment'
```

**4. Suppress less important changes:**
```bash
# Hide hooks and secrets
helm diff upgrade diff-demo bitnami/nginx \
  -f values-v2.yaml \
  --suppress-hooks \
  --suppress-secrets
```

### Issue: Diff shows changes but upgrade fails

**Problem:**
```bash
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml
# Shows changes

helm upgrade diff-demo bitnami/nginx -f values-v2.yaml
# Error: UPGRADE FAILED
```

**Possible causes:**

**1. Immutable field changes:**
```
Error: Deployment.apps "diff-demo-nginx" is invalid:
spec.selector: Invalid value: ...: field is immutable
```

**Solution:**
- Recreate resource (uninstall/reinstall)
- Or remove immutable field from diff

**2. Resource conflicts:**
```
Error: rendered manifests contain a resource that already exists
```

**Solution:**
- Check for duplicate resources
- Remove conflicting resources

**3. Insufficient permissions:**
```
Error: failed to create resource: forbidden
```

**Solution:**
```bash
# Check RBAC permissions
kubectl auth can-i create deployments -n helm-scenarios
kubectl auth can-i update services -n helm-scenarios
```

### Issue: Diff after upgrade shows changes

**Problem:**
```bash
# Upgrade completed successfully
helm upgrade diff-demo bitnami/nginx -f values-v2.yaml

# But diff still shows changes
helm diff upgrade diff-demo bitnami/nginx -f values-v2.yaml
# (shows unexpected diff)
```

**Possible causes:**

**1. Manual kubectl changes:**
```bash
# Someone ran kubectl commands
kubectl get events -n helm-scenarios --sort-by='.lastTimestamp'
# Check for manual scaling, edits, etc.
```

**2. Autoscaling (HPA):**
```bash
# HPA changed replicas
kubectl get hpa -n helm-scenarios

# Diff shows:
# - replicas: 3 (values file)
# + replicas: 5 (HPA scaled up)
```

**3. Mutating webhooks:**
```bash
# Admission controllers modified resources
kubectl get mutatingwebhookconfigurations
```

**4. Older Helm version:**
```bash
# Helm version mismatch can cause diff
helm version
# Upgrade: helm plugin update diff
```

---

## 📚 Best Practices

### 1. Always Diff Before Upgrade

✅ **Make it a habit:**
```bash
# Step 1: Diff first
helm diff upgrade my-app ./chart -f values.yaml

# Step 2: Review output carefully

# Step 3: Only then upgrade
helm upgrade my-app ./chart -f values.yaml
```

❌ **Don't skip diff:**
```bash
# Dangerous - no preview
helm upgrade my-app ./chart -f values.yaml --force
```

### 2. Version Control Values Files

✅ **Track changes:**
```bash
git add values-v1.yaml values-v2.yaml
git commit -m "Update nginx config: v1 → v2

Changes:
- Scale to 3 replicas for HA
- Increase resource limits
- Expose via NodePort
- Update version to v2.0.0"
git push
```

✅ **Use semantic commit messages:**
```
feat: add NodePort exposure for nginx
fix: increase memory limits to prevent OOMKilled
chore: update version labels v1 → v2
```

### 3. Environment-Specific Values

✅ **Organize by environment:**
```
values/
├── values-base.yaml       # Common to all environments
├── values-dev.yaml        # Development overrides
├── values-staging.yaml    # Staging overrides
└── values-prod.yaml       # Production overrides
```

**Deploy to environments:**
```bash
# Development
helm upgrade my-app ./chart \
  -f values/values-base.yaml \
  -f values/values-dev.yaml \
  -n dev

# Production
helm diff upgrade my-app ./chart \
  -f values/values-base.yaml \
  -f values/values-prod.yaml \
  -n production

# Review, then apply
helm upgrade my-app ./chart \
  -f values/values-base.yaml \
  -f values/values-prod.yaml \
  -n production
```

### 4. Use Diff in CI/CD Pipelines

✅ **GitLab CI example:**
```yaml
stages:
  - preview
  - deploy

preview:
  stage: preview
  script:
    - helm plugin install https://github.com/databus23/helm-diff
    - helm diff upgrade my-app ./chart -f values-prod.yaml -n production
  only:
    - merge_requests

deploy:
  stage: deploy
  script:
    - helm upgrade my-app ./chart -f values-prod.yaml -n production --wait
  only:
    - main
  when: manual  # Require approval after review
```

✅ **GitHub Actions example:**
```yaml
name: Helm Diff
on: pull_request

jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: azure/setup-helm@v1
      - name: Install helm-diff
        run: helm plugin install https://github.com/databus23/helm-diff
      - name: Diff
        run: |
          helm diff upgrade my-app ./chart \
            -f values-prod.yaml \
            -n production > diff.txt
      - name: Comment PR
        uses: actions/github-script@v5
        with:
          script: |
            const fs = require('fs');
            const diff = fs.readFileSync('diff.txt', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '## Helm Diff\n```diff\n' + diff + '\n```'
            });
```

### 5. Document Changes in Values Files

✅ **Add comments:**
```yaml
# values-v2.yaml

# Scale up for high availability (increased from 1)
# Rationale: Prevent downtime during node failures
replicaCount: 3

# Resource limits doubled to handle traffic spikes
# Benchmark: 95th percentile CPU usage was 120m
resources:
  limits:
    cpu: 200m  # Increased from 100m
    memory: 256Mi  # Increased from 128Mi
```

### 6. Test Changes in Lower Environments

✅ **Promotion workflow:**
```
1. Development
   helm diff upgrade my-app ./chart -f values-dev.yaml -n dev
   helm upgrade my-app ./chart -f values-dev.yaml -n dev

2. Staging
   helm diff upgrade my-app ./chart -f values-staging.yaml -n staging
   helm upgrade my-app ./chart -f values-staging.yaml -n staging
   # Run integration tests

3. Production
   helm diff upgrade my-app ./chart -f values-prod.yaml -n production
   # Review diff carefully
   # Get approval from team
   helm upgrade my-app ./chart -f values-prod.yaml -n production
```

### 7. Save Diff Output for Auditing

✅ **Audit trail:**
```bash
# Create audit directory
mkdir -p audits/$(date +%Y-%m-%d)

# Save diff before upgrade
helm diff upgrade my-app ./chart -f values-prod.yaml -n production \
  > audits/$(date +%Y-%m-%d)/diff-$(date +%H%M%S).txt

# Save upgrade command
echo "helm upgrade my-app ./chart -f values-prod.yaml -n production" \
  > audits/$(date +%Y-%m-%d)/command-$(date +%H%M%S).sh

# Commit to Git
git add audits/
git commit -m "Audit: my-app upgrade $(date +%Y-%m-%d)"
```

### 8. Combine with Other Tools

✅ **With helm template:**
```bash
# Render full manifests with your values
helm template my-app ./chart -f values-v2.yaml > rendered.yaml

# Review full YAML
less rendered.yaml

# Then diff against deployed
helm diff upgrade my-app ./chart -f values-v2.yaml
```

✅ **With kubeval (validate Kubernetes schemas):**
```bash
# Render and validate
helm template my-app ./chart -f values-v2.yaml | kubeval

# If valid, then diff
helm diff upgrade my-app ./chart -f values-v2.yaml
```

✅ **With conftest (policy testing):**
```bash
# Test against OPA policies
helm template my-app ./chart -f values-v2.yaml | conftest test -

# Example policy: ensure non-root
# rules/security.rego
package main
deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.securityContext.runAsNonRoot
  msg = "Containers must run as non-root"
}
```

---

## 🔗 Further Reading

### Official Documentation
- **Helm Diff Plugin**: https://github.com/databus23/helm-diff
- **Helm Upgrade Command**: https://helm.sh/docs/helm/helm_upgrade/
- **Helm Values Files**: https://helm.sh/docs/chart_template_guide/values_files/
- **Bitnami nginx Chart**: https://github.com/bitnami/charts/tree/main/bitnami/nginx

### Best Practices
- **Helm Best Practices**: https://helm.sh/docs/chart_best_practices/
- **Kubernetes Resource Management**: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- **Service Types**: https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types

### Related Tools
- **helm-secrets**: https://github.com/jkroepke/helm-secrets (encrypt sensitive values)
- **helmfile**: https://github.com/helmfile/helmfile (declarative Helm releases)
- **Argo CD**: https://argoproj.github.io/cd/ (GitOps with Helm)
- **Flux**: https://fluxcd.io/ (GitOps toolkit)

### CI/CD Integration
- **GitLab CI with Helm**: https://docs.gitlab.com/ee/topics/autodevops/customize.html#helm
- **GitHub Actions for Kubernetes**: https://github.com/Azure/k8s-deploy
- **Jenkins X**: https://jenkins-x.io/ (Kubernetes-native CI/CD)

---

## 🎯 Key Takeaways

1. **Never upgrade blind** - Always preview changes with `helm diff` first
2. **Understand the diff** - Review every line, understand implications
3. **Version control values** - Track changes, document rationale
4. **Test in lower environments** - Dev → Staging → Production
5. **Automate in CI/CD** - Make diff a required step before merge
6. **Verify after upgrade** - Run diff again to confirm no drift
7. **Document changes** - Save diff output for audit trails
8. **Combine with validation** - Use kubeval, conftest, policy engines

**The helm-diff plugin is your safety net for production deployments. Use it religiously, and you'll prevent countless production incidents.**

---

*This comprehensive guide covers everything you need to know about using the Helm diff plugin effectively. Master these concepts, and you'll deploy with confidence every time!*
