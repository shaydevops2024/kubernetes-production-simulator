# Helm YAML Explanation - Failed Release Recovery Scenario

This guide provides a comprehensive explanation of how Helm handles failed releases, including the YAML configurations used to simulate failures and the recovery strategies available. You'll learn about release states, timeout mechanisms, and how to diagnose and recover from various failure scenarios.

---

## 🎯 What is Failed Release Recovery?

**Failed release recovery** refers to the process of diagnosing and fixing Helm releases that have entered a failed, stuck, or unhealthy state. In production environments, releases can fail for numerous reasons:

- **Image pull failures** - Non-existent tags, wrong registry, missing credentials
- **Resource constraints** - Insufficient CPU/memory on cluster nodes
- **Configuration errors** - Invalid YAML, wrong environment variables
- **Timeout issues** - Pods taking too long to start, health checks failing
- **Dependency failures** - Databases unavailable, external services down

### Why Recovery Matters

In production:
- **Downtime costs money** - Every minute of downtime impacts revenue
- **User experience** - Failed deployments can break customer-facing features
- **Team velocity** - Stuck releases block further deployments
- **Confidence** - Knowing how to recover reduces deployment anxiety

This scenario teaches you the tools and techniques to quickly diagnose and recover from these situations.

---

## 📊 Helm Release States

Helm tracks each release through various states. Understanding these states is critical for choosing the right recovery strategy.

### Release State Reference

| State | Meaning | Common Causes | Recovery Strategy |
|-------|---------|---------------|-------------------|
| **deployed** | Release is live and healthy | N/A - this is the goal state | No action needed |
| **failed** | Last operation failed | Image pull errors, timeout, pod crashes | `helm rollback` or fix and `helm upgrade` |
| **pending-install** | Install in progress or timed out | Long startup times, insufficient resources | Wait, or `helm uninstall` and retry |
| **pending-upgrade** | Upgrade in progress or timed out | Long startup times, health check failures | `helm rollback` to previous revision |
| **pending-rollback** | Rollback in progress | Rolling back from failed state | Wait for completion |
| **superseded** | Replaced by newer revision | Normal - previous revisions show this | No action needed (historical record) |
| **uninstalling** | Being removed | In-progress uninstall | Wait for completion |
| **uninstalled** | Successfully removed | Release was deleted | Reinstall if needed |

### State Transition Diagram

```
                    ┌─────────────┐
                    │   INSTALL   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
            ┌───────┤   deployed  ├────────┐
            │       └──────┬──────┘        │
            │              │               │
     ┌──────▼──────┐       │        ┌─────▼──────┐
     │   UPGRADE   │       │        │  ROLLBACK  │
     └──────┬──────┘       │        └─────┬──────┘
            │              │               │
     ┌──────▼──────┐       │        ┌─────▼──────┐
     │   failed    │───────┼────────▶ superseded │
     └─────────────┘       │        └────────────┘
                           │
                    ┌──────▼──────┐
                    │  UNINSTALL  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ uninstalled │
                    └─────────────┘
```

### Checking Release State

```bash
# View current state
helm status recovery-demo -n helm-scenarios

# View state history
helm history recovery-demo -n helm-scenarios

# List all releases with their states
helm list -n helm-scenarios --all-namespaces
```

---

## 📄 Chart.yaml - Chart Metadata

```yaml
apiVersion: v2
name: recovery-demo
description: A simple chart for demonstrating Helm release failure and recovery
type: application
version: 1.0.0
appVersion: "1.0.0"
maintainers:
  - name: k8s-simulator
```

### Field Breakdown

#### apiVersion: v2

**What it is:** Helm Chart API version

**v2 vs v1:**
- **v2** (Helm 3): No Tiller, improved dependency management
- **v1** (Helm 2): Legacy, requires Tiller server

**Always use v2** for new charts (Helm 3+ requirement)

#### name: recovery-demo

**What it is:** Chart name (must match directory name)

**Naming rules:**
- Lowercase letters, numbers, hyphens only
- No underscores or special characters
- Should be descriptive and unique

**Used in:**
- Release names: `helm install [release-name] [chart-name]`
- Labels: `app.kubernetes.io/name: recovery-demo`
- Template helpers: `{{ .Chart.Name }}`

#### description

**What it is:** Human-readable chart description

**Purpose:**
- Documentation for `helm search` output
- Helps users understand chart purpose
- Shown in Helm Hub / Artifact Hub listings

#### type: application

**Chart types:**

| Type | Purpose | Example |
|------|---------|---------|
| **application** | Deployable application | This chart, nginx, wordpress |
| **library** | Reusable template library | Common helpers, shared functions |

**Library charts:**
- Cannot be installed directly
- Used as dependencies by other charts
- Provide shared templates and helpers

#### version: 1.0.0

**What it is:** Chart version (SemVer format)

**Versioning strategy:**
- **Major** (1.0.0 → 2.0.0): Breaking changes
- **Minor** (1.0.0 → 1.1.0): New features, backward compatible
- **Patch** (1.0.0 → 1.0.1): Bug fixes only

**Best practices:**
- Increment version with every chart change
- Use SemVer strictly for predictable upgrades
- Don't confuse with appVersion (different purposes)

#### appVersion: "1.0.0"

**What it is:** Version of the application being deployed

**Difference from version:**
- `version`: Chart version (Helm packaging)
- `appVersion`: Application version (nginx, postgres, etc.)

**Example:**
```yaml
version: 2.5.0      # Chart has been updated 2.5.0 times
appVersion: "1.24"  # Deploys nginx 1.24
```

**Best practices:**
- Quote appVersion to preserve exact formatting
- Update when changing image tags
- Use for tracking deployed application versions

#### maintainers

**What it is:** List of people/teams responsible for the chart

**Full format:**
```yaml
maintainers:
  - name: John Doe
    email: john@example.com
    url: https://github.com/johndoe
  - name: Platform Team
```

**Purpose:**
- Contact information for chart issues
- Shows up in `helm show chart` output
- Useful in chart repositories

---

## 📄 values.yaml - Working Configuration

```yaml
# values.yaml
# Default values for recovery-demo chart.
# These values produce a healthy, working deployment.

replicaCount: 2

image:
  repository: nginx
  tag: "1.24-alpine"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 80

resources:
  requests:
    cpu: 25m
    memory: 32Mi
  limits:
    cpu: 100m
    memory: 128Mi

labels:
  version: "v1"
```

### Field-by-Field Explanation

#### replicaCount: 2

**What it is:** Number of pod replicas to run

**Why 2:**
- ✅ **High availability** - Survives single pod failure
- ✅ **Load distribution** - Traffic shared across 2 pods
- ✅ **Resource efficient** - Not excessive for demo
- ✅ **Rolling updates** - Can update one at a time

**Alternatives:**
- **1 replica**: Development, minimal resources
- **3+ replicas**: Production, better HA guarantee
- **Odd numbers (3, 5)**: Useful with quorum-based systems

**Impact on rollout:**
```
During upgrade with 2 replicas:
- 1 old pod keeps running
- 1 new pod starts
- Once new pod ready, old pod terminated
- 2nd new pod starts
- Result: minimal disruption
```

#### image.repository: nginx

**What it is:** Container image repository

**Format:** `[registry/]repository`

**Examples:**
```yaml
# Docker Hub (default registry)
repository: nginx

# Custom registry
repository: gcr.io/my-project/nginx

# Private registry
repository: my-registry.com:5000/nginx
```

**Best practices:**
- Use stable, well-maintained images
- Prefer official images when available
- Use private registries for proprietary apps

#### image.tag: "1.24-alpine"

**What it is:** Container image tag

**Why quoted:** YAML interprets `1.24` as float, quoting preserves string

**Tag strategies:**

| Strategy | Example | Pros | Cons |
|----------|---------|------|------|
| **Specific version** | `"1.24-alpine"` | Reproducible, safe | Manual updates needed |
| **Minor version** | `"1.24"` | Auto patch updates | Less predictable |
| **Major version** | `"1"` | Always latest 1.x | Breaking changes risk |
| **latest** | `"latest"` | Always newest | Unpredictable, breaks reproducibility |

**This scenario uses "1.24-alpine":**
- ✅ **Specific version** - Predictable behavior
- ✅ **Alpine variant** - Smaller image (~23 MB vs ~140 MB)
- ✅ **Known-good** - Widely tested, stable nginx version

**Alpine vs Debian:**
```yaml
nginx:1.24-alpine   # 23 MB, musl libc, fewer packages
nginx:1.24          # 140 MB, glibc, more compatible
```

#### image.pullPolicy: IfNotPresent

**What it is:** When to pull the container image

**Pull policies:**

| Policy | Behavior | Use Case |
|--------|----------|----------|
| **IfNotPresent** | Pull if not cached locally | Immutable tags (v1.24) |
| **Always** | Always pull from registry | Testing, mutable tags (latest) |
| **Never** | Only use local cache | Air-gapped, preloaded images |

**Default behavior:**
- Tag `:latest` → pullPolicy: Always (implicit)
- Specific tag → pullPolicy: IfNotPresent

**Why IfNotPresent for this scenario:**
- ✅ **Faster pod startup** - Uses cached image
- ✅ **Reduced registry load** - Fewer pull requests
- ✅ **Works offline** - Once cached, no internet needed
- ✅ **Immutable tag** - `1.24-alpine` won't change

**When to use Always:**
- Development with frequent image updates
- Testing with `:latest` tag
- Security requirement to always verify image

#### service.type: ClusterIP

**What it is:** Kubernetes Service type

**Service types comparison:**

| Type | Access | IP Assignment | Use Case |
|------|--------|---------------|----------|
| **ClusterIP** | Internal only | Virtual IP (cluster-wide) | Microservices, databases |
| **NodePort** | External via node:port | ClusterIP + node port | Development, testing |
| **LoadBalancer** | External via LB | ClusterIP + cloud LB IP | Production (cloud) |
| **ExternalName** | DNS alias | None | External service proxying |

**Why ClusterIP for values.yaml (default):**
- ✅ **Secure by default** - No external exposure
- ✅ **Standard practice** - Most services are internal
- ✅ **Production-like** - Matches microservice patterns
- ✅ **No port conflicts** - NodePort ranges can be limited

**Accessing ClusterIP services:**
```bash
# From inside cluster
curl http://recovery-demo.helm-scenarios.svc.cluster.local

# From outside cluster (port-forward)
kubectl port-forward svc/recovery-demo 8080:80 -n helm-scenarios
curl http://localhost:8080
```

#### service.port: 80

**What it is:** Port the Service listens on (inside cluster)

**Common ports:**
- **80**: HTTP (standard web traffic)
- **443**: HTTPS (secure web traffic)
- **8080**: HTTP alternate (non-privileged)
- **3000**: App server (Node.js, Rails)
- **5432**: PostgreSQL
- **6379**: Redis

**Port vs TargetPort:**
```yaml
service:
  port: 80          # Service port (client connects here)
  targetPort: 8080  # Container port (nginx listens here)
```

**Flow:**
```
Client → Service:80 → Pod:8080 (container)
```

#### service.targetPort: 80

**What it is:** Port where the container actually listens

**This scenario:** nginx listens on port 80 (in container)

**Why separate port and targetPort:**
```yaml
# Service standardizes access
service:
  port: 80          # Everyone connects to :80
  targetPort: 8080  # App actually listens on :8080

# Benefits:
# - Consistent client interface (always :80)
# - Apps can run on non-standard ports (8080, 3000, etc.)
# - No port conflicts between containers
```

**Named ports:**
```yaml
# In Deployment
containerPort: 8080
name: http

# In Service
targetPort: http  # References named port
```

#### resources.requests

**What it is:** Minimum guaranteed resources per pod

```yaml
resources:
  requests:
    cpu: 25m      # 25 millicores = 0.025 CPU cores
    memory: 32Mi  # 32 Mebibytes = 33.5 MB
```

**Why these values:**
- ✅ **Minimal footprint** - nginx is lightweight
- ✅ **Kind-friendly** - Works on laptop clusters
- ✅ **Scheduler efficiency** - Easy to place on nodes
- ✅ **Multiple pods fit** - 2 replicas won't exhaust resources

**CPU units:**
- `1000m` = `1` = 1 full CPU core
- `100m` = 0.1 CPU cores (10%)
- `25m` = 0.025 CPU cores (2.5%)

**Memory units:**
- `Mi` = Mebibyte (1024² bytes = 1,048,576 bytes)
- `Gi` = Gibibyte (1024³ bytes)
- `Ki` = Kibibyte (1024 bytes)

**Impact on scheduling:**
```
Node has 4 CPU cores (4000m) available:
- Can schedule 160 pods with 25m requests each
- Scheduler ONLY places pod if node has enough requested resources
```

#### resources.limits

**What it is:** Maximum allowed resources per pod

```yaml
resources:
  limits:
    cpu: 100m     # 0.1 CPU cores max
    memory: 128Mi # 134 MB max
```

**Limits vs Requests:**

| Resource | Request (25m) | Limit (100m) | Burst Capacity |
|----------|---------------|--------------|----------------|
| CPU | Guaranteed | Max allowed | 4× (25m → 100m) |
| Memory | Guaranteed | Max allowed | 4× (32Mi → 128Mi) |

**What happens when limits are exceeded:**

**CPU:**
- **Throttled** - Process slowed down, not killed
- **CFS quota** - Gets CPU proportional to request
- **No OOM** - CPU starvation doesn't crash pod

**Memory:**
- **OOMKilled** - Pod terminated if exceeds limit
- **Pod restarts** - Kubernetes restarts the pod
- **Crash loop** - If consistently exceeds, CrashLoopBackOff

**Quality of Service (QoS):**

This configuration creates **Burstable** QoS:
```yaml
resources:
  requests: { cpu: 25m, memory: 32Mi }   # Set
  limits:   { cpu: 100m, memory: 128Mi }  # Set and > requests
# Result: Burstable QoS class
```

**QoS Classes:**

| Class | Criteria | Priority | Use Case |
|-------|----------|----------|----------|
| **Guaranteed** | requests = limits | Highest | Critical production services |
| **Burstable** | requests < limits | Medium | Most applications (this scenario) |
| **BestEffort** | No requests/limits | Lowest | Batch jobs, non-critical workloads |

**Best practices:**
```yaml
# Good: Allows bursting (Burstable)
requests: { cpu: 50m, memory: 64Mi }
limits:   { cpu: 200m, memory: 256Mi }  # 4× burst capacity

# Good: Strict limits (Guaranteed)
requests: { cpu: 100m, memory: 128Mi }
limits:   { cpu: 100m, memory: 128Mi }  # Same as requests

# Bad: No requests (BestEffort - can be evicted easily)
limits: { cpu: 200m, memory: 256Mi }
# No requests set - pod has no guarantee

# Bad: Memory limit without request (still BestEffort for memory)
requests: { cpu: 50m }
limits:   { cpu: 200m, memory: 256Mi }
```

#### labels.version: "v1"

**What it is:** Custom label added to all resources

**Purpose:**
- 🏷️ **Version tracking** - Identify which version is deployed
- 📊 **Monitoring queries** - Filter metrics by version
- 🔍 **Debugging** - Find pods by version quickly
- 🔀 **Traffic routing** - Services can select by version

**How templates use this:**
```yaml
# In _helpers.tpl
labels:
  version: {{ .Values.labels.version | quote }}

# Results in:
metadata:
  labels:
    version: "v1"
```

**Practical usage:**
```bash
# Get all v1 pods
kubectl get pods -n helm-scenarios -l version=v1

# Get all v2 pods (after upgrade with bad-values.yaml)
kubectl get pods -n helm-scenarios -l version=v2-broken

# Show version label in output
kubectl get pods -n helm-scenarios -L version
```

---

## 📄 bad-values.yaml - Intentionally Broken Configuration

```yaml
# bad-values.yaml
# Intentionally broken values that will cause a deployment failure.
# Uses a non-existent image tag that will never pull successfully,
# causing pods to enter ImagePullBackOff and the release to time out.

replicaCount: 2

image:
  repository: nginx
  # This tag does not exist -- pods will fail with ImagePullBackOff
  tag: "99.99.99-nonexistent"
  pullPolicy: Always

service:
  type: ClusterIP
  port: 80
  targetPort: 80

resources:
  requests:
    cpu: 25m
    memory: 32Mi
  limits:
    cpu: 100m
    memory: 128Mi

labels:
  version: "v2-broken"
```

### What Makes This Configuration Fail

#### image.tag: "99.99.99-nonexistent"

**What it is:** A deliberately non-existent image tag

**Why it fails:**
- Docker Hub has no `nginx:99.99.99-nonexistent` image
- Kubelet tries to pull image from registry
- Registry returns 404 Not Found
- Pod enters **ImagePullBackOff** state
- Kubernetes retries with exponential backoff
- Pod never becomes Ready

**Error sequence:**
```
1. Pod created → Status: Pending
2. Kubelet tries to pull image → Status: Waiting (Reason: ContainerCreating)
3. Pull fails (404) → Status: Waiting (Reason: ErrImagePull)
4. Kubernetes waits before retry → Status: Waiting (Reason: ImagePullBackOff)
5. Retry pull → Fail again → Back to ImagePullBackOff
6. Exponential backoff: 10s → 20s → 40s → 80s → 160s → 300s (max)
```

**Viewing the error:**
```bash
# See pod status
kubectl get pods -n helm-scenarios
# NAME                    READY   STATUS             RESTARTS   AGE
# recovery-demo-xyz       0/1     ImagePullBackOff   0          2m

# See detailed events
kubectl describe pod recovery-demo-xyz -n helm-scenarios
# Events:
#   Warning  Failed     kubelet  Failed to pull image "nginx:99.99.99-nonexistent": rpc error: code = NotFound desc = failed to pull and unpack image
#   Warning  Failed     kubelet  Error: ErrImagePull
#   Normal   BackOff    kubelet  Back-off pulling image "nginx:99.99.99-nonexistent"
```

#### image.pullPolicy: Always

**What it is:** Forces Kubernetes to always try pulling from registry

**Why Always makes failure worse:**
- **Can't use cache** - Even if image was cached, ignores it
- **Every restart tries** - More registry load
- **No offline fallback** - Requires network connectivity

**Contrast with IfNotPresent:**
```yaml
# values.yaml (working)
pullPolicy: IfNotPresent
# - If nginx:1.24-alpine cached, uses it immediately
# - Fast pod startup (no pull delay)

# bad-values.yaml (broken)
pullPolicy: Always
# - Must contact registry every time
# - Guaranteed to fail for nonexistent image
# - No possibility of cached fallback
```

**When Always is appropriate:**
- Development with frequently updated images
- Security requirement to verify image signatures
- Using `:latest` tag (changes over time)
- Testing in isolated environments

#### labels.version: "v2-broken"

**What it is:** Custom label identifying the broken version

**Why include "broken" in the name:**
- ✅ **Self-documenting** - Clear this is the failure scenario
- ✅ **Easy filtering** - Can target broken pods specifically
- ✅ **Learning** - Reinforces that this is intentional failure

**Practical usage during scenario:**
```bash
# Find broken pods
kubectl get pods -n helm-scenarios -l version=v2-broken

# See events for broken pods
kubectl describe pod -n helm-scenarios -l version=v2-broken

# Compare with working pods
kubectl get pods -n helm-scenarios -l version=v1
```

**Label in action:**
```yaml
# After upgrade with bad-values.yaml
metadata:
  labels:
    version: "v2-broken"

# Kubernetes tries to create these pods
# They enter ImagePullBackOff
# But label helps identify them in the cluster
```

### Other Potential Failure Scenarios

While this scenario uses **image pull failure**, real-world failures can occur from:

#### Configuration Errors
```yaml
# Wrong environment variable
env:
  - name: DATABASE_URL
    value: "postgres://wrong-host:5432/db"  # Host doesn't exist

# Invalid resource format
resources:
  requests:
    cpu: "fifty-m"  # Invalid format, must be "50m"
```

#### Resource Constraints
```yaml
# Requesting more resources than any node has
resources:
  requests:
    cpu: 64     # No node has 64 CPU cores
    memory: 1Ti # No node has 1 TiB memory
```

#### Failed Probes
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 9999  # Wrong port (app listens on 8080)
  initialDelaySeconds: 5
  periodSeconds: 10
# Pod starts, but liveness probe fails → Kubernetes kills pod → CrashLoopBackOff
```

#### Application Crashes
```yaml
command: ["sh", "-c", "exit 1"]  # App immediately exits
# Pod starts → Container exits with code 1 → CrashLoopBackOff
```

---

## 📄 templates/deployment.yaml - Deployment Template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "recovery-demo.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "recovery-demo.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "recovery-demo.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "recovery-demo.labels" . | nindent 8 }}
    spec:
      containers:
        - name: nginx
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.targetPort }}
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 3
            periodSeconds: 5
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

### Template Breakdown

#### name: {{ include "recovery-demo.fullname" . }}

**What it is:** Deployment name using template helper function

**Renders to:**
```yaml
# With release name "recovery-demo"
name: recovery-demo
```

**Why use a helper:**
- **Consistency** - Same naming logic across all templates
- **Customization** - Can override in _helpers.tpl
- **Collision avoidance** - Can include chart name in full name

**Alternative patterns:**
```yaml
# Simple: just release name
name: {{ .Release.Name }}

# With chart name prefix
name: {{ .Release.Name }}-{{ .Chart.Name }}

# With truncation (max 63 chars for DNS)
name: {{ .Release.Name | trunc 63 | trimSuffix "-" }}
```

#### namespace: {{ .Release.Namespace }}

**What it is:** Target namespace for the deployment

**Set by:**
```bash
helm install recovery-demo ./chart -n helm-scenarios
#                                    ^^^^^^^^^^^^^^^^
#                              .Release.Namespace = "helm-scenarios"
```

**Why include explicitly:**
- **Clarity** - Makes namespace explicit in rendered YAML
- **kubectl compatibility** - Works with `kubectl apply -f`
- **Multi-tenancy** - Ensures resources go to correct namespace

**Default namespace:** If `-n` not specified, uses `default`

#### labels: {{- include "recovery-demo.labels" . | nindent 4 }}

**What it is:** Calls label template helper and indents output

**Template syntax:**
- `{{-` - Trim whitespace before
- `include "name" .` - Call named template with context
- `| nindent 4` - Indent output 4 spaces

**Renders to:** (from _helpers.tpl)
```yaml
labels:
  app.kubernetes.io/name: recovery-demo
  app.kubernetes.io/instance: recovery-demo
  app.kubernetes.io/version: "1.0.0"
  app.kubernetes.io/managed-by: Helm
  helm.sh/chart: recovery-demo-1.0.0
  version: "v1"  # From values.yaml
```

**Why use helper templates:**
- **DRY principle** - Define labels once, use everywhere
- **Maintainability** - Change in one place updates all resources
- **Consistency** - All resources have same label structure

#### replicas: {{ .Values.replicaCount }}

**What it is:** Number of pod replicas (from values)

**Renders to:**
```yaml
# With values.yaml
replicas: 2

# With bad-values.yaml
replicas: 2  # Same
```

**Dynamic example:**
```bash
# Override at install time
helm install recovery-demo ./chart --set replicaCount=5

# Renders to:
replicas: 5
```

#### selector.matchLabels

**What it is:** Selector used by Deployment to find its pods

```yaml
selector:
  matchLabels:
    {{- include "recovery-demo.selectorLabels" . | nindent 6 }}
```

**Renders to:**
```yaml
selector:
  matchLabels:
    app.kubernetes.io/name: recovery-demo
    app.kubernetes.io/instance: recovery-demo
```

**Why separate from full labels:**
- **Immutable** - Selector cannot change after Deployment created
- **Minimal** - Only include stable, identifying labels
- **Match guarantee** - Pods must have AT LEAST these labels

**Label hierarchy:**
```
Full labels (metadata.labels):
  - app.kubernetes.io/name
  - app.kubernetes.io/instance
  - app.kubernetes.io/version
  - helm.sh/chart
  - version
  - (many others possible)

Selector labels (subset):
  - app.kubernetes.io/name      ← Stable
  - app.kubernetes.io/instance  ← Stable
```

**Why version NOT in selector:**
```yaml
# BAD: Including version in selector
selector:
  matchLabels:
    version: v1

# Problem:
# - Upgrade changes version: v1 → v2
# - Selector would need to change: v1 → v2
# - Kubernetes FORBIDS selector changes on Deployments
# - Would require deleting and recreating Deployment
# - Causes downtime

# GOOD: Exclude version from selector
selector:
  matchLabels:
    app.kubernetes.io/instance: recovery-demo

# Benefits:
# - Selector stays constant
# - Upgrade can change version label: v1 → v2
# - Rolling update works smoothly
# - Zero downtime
```

#### template.metadata.labels

**What it is:** Labels applied to each pod

```yaml
template:
  metadata:
    labels:
      {{- include "recovery-demo.labels" . | nindent 8 }}
```

**Renders to:** (includes full labels)
```yaml
labels:
  app.kubernetes.io/name: recovery-demo
  app.kubernetes.io/instance: recovery-demo
  app.kubernetes.io/version: "1.0.0"
  app.kubernetes.io/managed-by: Helm
  helm.sh/chart: recovery-demo-1.0.0
  version: "v1"
```

**Must include selector labels:**
- Pods MUST have all labels from `selector.matchLabels`
- Can have additional labels (version, environment, etc.)
- Deployment finds pods using selector labels

#### image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"

**What it is:** Container image specification (templated)

**Renders to:**
```yaml
# With values.yaml
image: "nginx:1.24-alpine"

# With bad-values.yaml
image: "nginx:99.99.99-nonexistent"  # Fails to pull
```

**Why quote the image string:**
- **YAML safety** - Prevents parsing issues with colons
- **Consistency** - Works for all image formats

**Supports full image URIs:**
```yaml
# Docker Hub (default)
image: "nginx:1.24-alpine"

# Google Container Registry
image: "gcr.io/project/image:tag"

# AWS ECR
image: "123456789.dkr.ecr.us-west-2.amazonaws.com/app:v1"

# Private registry
image: "registry.company.com:5000/app:latest"
```

#### imagePullPolicy: {{ .Values.image.pullPolicy }}

**What it is:** When to pull the container image

**Renders to:**
```yaml
# With values.yaml
imagePullPolicy: IfNotPresent

# With bad-values.yaml
imagePullPolicy: Always  # Makes failure immediate
```

**Impact on failure scenario:**
- **Always** → Every pod creation attempts pull → Fails immediately
- **IfNotPresent** → If image cached, uses cache → Fails only if not cached
- **Never** → Only uses cache → Would fail if not preloaded

#### ports

**What it is:** Container ports exposed to the pod network

```yaml
ports:
  - name: http
    containerPort: {{ .Values.service.targetPort }}
    protocol: TCP
```

**Renders to:**
```yaml
ports:
  - name: http
    containerPort: 80
    protocol: TCP
```

**Port naming:**
- **Named ports** - Can reference by name in Service
- **Descriptive** - "http", "https", "metrics", "admin"
- **DNS-compatible** - Max 15 chars, lowercase, hyphens ok

**containerPort vs Service port:**
```yaml
# Deployment
containerPort: 80  # Container listens here

# Service
port: 80           # Service listens here
targetPort: 80     # Routes to container's port 80
```

#### livenessProbe

**What it is:** Health check to detect when container is alive

```yaml
livenessProbe:
  httpGet:
    path: /
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
```

**Probe types:**

| Type | Check | Use Case |
|------|-------|----------|
| **httpGet** | HTTP GET request | Web servers, REST APIs |
| **tcpSocket** | TCP connection | Databases, non-HTTP services |
| **exec** | Command execution | Custom health check script |

**Liveness behavior:**
- **Success** (HTTP 200-399) - Container is healthy
- **Failure** - Kubernetes kills and restarts container
- **Purpose** - Detect **deadlocks** and **hangs** (process running but not responding)

**Settings explained:**

```yaml
initialDelaySeconds: 5   # Wait 5s after container starts before first probe
periodSeconds: 10        # Check every 10 seconds
# failureThreshold: 3    # (default) Fail 3 times → restart container
# successThreshold: 1    # (default) Succeed 1 time → mark healthy
# timeoutSeconds: 1      # (default) Probe must respond within 1s
```

**Why initialDelaySeconds: 5:**
- nginx starts quickly (< 1 second)
- 5 seconds provides buffer for slow nodes
- Too low → false positives (restarts healthy containers)
- Too high → slow detection of real failures

**Why periodSeconds: 10:**
- Frequent enough to detect issues quickly
- Not so frequent as to overload container with probes
- 10s = reasonable trade-off for nginx

**Path: /**
- nginx root path (always responds)
- In production, use dedicated health endpoint: `/healthz`, `/health`

**Port: http**
- References named port from `ports` section
- Could also use number: `port: 80`

**Liveness vs Readiness:**
- **Liveness** - Is process alive? (deadlock detection)
- **Readiness** - Is process ready for traffic? (startup/warmup)

#### readinessProbe

**What it is:** Health check to detect when container is ready for traffic

```yaml
readinessProbe:
  httpGet:
    path: /
    port: http
  initialDelaySeconds: 3
  periodSeconds: 5
```

**Readiness behavior:**
- **Success** - Pod added to Service endpoints (receives traffic)
- **Failure** - Pod removed from Service endpoints (no traffic)
- **Purpose** - Prevent routing to containers still starting up or temporarily unavailable

**Difference from liveness:**

| Probe | Failure Action | Use Case |
|-------|----------------|----------|
| **Liveness** | Restart container | Detect deadlocks, frozen processes |
| **Readiness** | Stop sending traffic | Detect startup delay, temporary unavailability |

**Settings explained:**

```yaml
initialDelaySeconds: 3   # Wait 3s after container starts before first check
periodSeconds: 5         # Check every 5 seconds
```

**Why initialDelaySeconds: 3 (less than liveness):**
- Readiness checks as soon as possible (want to serve traffic ASAP)
- Liveness waits longer (avoids false positives during startup)
- nginx ready quickly, so 3s is safe

**Why periodSeconds: 5 (more frequent than liveness):**
- Faster detection of readiness state changes
- More important to quickly remove unhealthy pods from load balancing
- More traffic impact if ready pod becomes unready

**In failed release scenario:**
- **ImagePullBackOff** → Container never starts
- → Readiness probe never runs (no container to probe)
- → Pod stays in Waiting state, not Ready
- → Never receives traffic

**Production best practices:**
```yaml
# Dedicated health endpoint
readinessProbe:
  httpGet:
    path: /healthz      # Custom health check endpoint
    port: http
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 3
  successThreshold: 1

# Or check dependencies
readinessProbe:
  exec:
    command:
      - /bin/sh
      - -c
      - "curl -f http://database:5432 && curl -f http://cache:6379"
  initialDelaySeconds: 15
  periodSeconds: 10
```

#### resources: {{- toYaml .Values.resources | nindent 12 }}

**What it is:** CPU and memory requests/limits

**Template function:**
- `toYaml` - Converts Go object to YAML
- `nindent 12` - Indents output 12 spaces

**Renders to:**
```yaml
resources:
  requests:
    cpu: 25m
    memory: 32Mi
  limits:
    cpu: 100m
    memory: 128Mi
```

**Why use toYaml:**
- **Preserves structure** - Nested objects rendered correctly
- **Clean templates** - No need to manually template each line
- **Flexible** - Users can add custom fields in values

**Alternative (verbose):**
```yaml
# Without toYaml (more repetitive)
resources:
  requests:
    cpu: {{ .Values.resources.requests.cpu }}
    memory: {{ .Values.resources.requests.memory }}
  limits:
    cpu: {{ .Values.resources.limits.cpu }}
    memory: {{ .Values.resources.limits.memory }}
```

---

## 📄 templates/service.yaml - Service Template

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "recovery-demo.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "recovery-demo.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      protocol: TCP
      name: http
  selector:
    {{- include "recovery-demo.selectorLabels" . | nindent 4 }}
```

### Service Template Breakdown

#### type: {{ .Values.service.type }}

**What it is:** Service type (ClusterIP, NodePort, LoadBalancer)

**Renders to:**
```yaml
# With values.yaml (and bad-values.yaml)
type: ClusterIP
```

**ClusterIP service:**
- **Internal-only** - Not accessible from outside cluster
- **Virtual IP** - Cluster-wide reachable IP address
- **DNS name** - `recovery-demo.helm-scenarios.svc.cluster.local`

**During failure scenario:**
- Service created successfully (even when pods fail)
- Service has no ready endpoints (pods not ready)
- Requests to service fail (no healthy backends)

**Check service status:**
```bash
# View service
kubectl get svc -n helm-scenarios
# NAME            TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
# recovery-demo   ClusterIP   10.96.123.45    <none>        80/TCP    2m

# Check endpoints
kubectl get endpoints -n helm-scenarios
# NAME            ENDPOINTS          AGE
# recovery-demo   <none>             2m
#                 ^^^^^^ No ready pods!
```

#### ports

**What it is:** Port configuration for the service

```yaml
ports:
  - port: {{ .Values.service.port }}
    targetPort: {{ .Values.service.targetPort }}
    protocol: TCP
    name: http
```

**Renders to:**
```yaml
ports:
  - port: 80
    targetPort: 80
    protocol: TCP
    name: http
```

**Port flow:**
```
Client → Service:80 → Pod:80 (nginx container)
```

**Named port:** `name: http`
- Required for multiple ports on same service
- Used in Ingress rules, Network Policies
- Descriptive (http, https, metrics, admin)

**During failure:**
- Service port `80` is open and listening
- But no backend pods are ready
- Requests time out or get connection refused
- **Important:** Service exists even when all pods fail

#### selector: {{- include "recovery-demo.selectorLabels" . | nindent 4 }}

**What it is:** Labels used to select backend pods

**Renders to:**
```yaml
selector:
  app.kubernetes.io/name: recovery-demo
  app.kubernetes.io/instance: recovery-demo
```

**How service selection works:**

1. **Service selector** matches pods with these labels
2. **Kubernetes watches** for pods with matching labels
3. **Endpoints object** lists IPs of ready pods
4. **kube-proxy** configures iptables/ipvs to route traffic
5. **Traffic flows** to ready pod IPs

**During failure (ImagePullBackOff):**
```bash
# Pods exist but are not ready
kubectl get pods -n helm-scenarios
# NAME                    READY   STATUS             RESTARTS   AGE
# recovery-demo-xyz       0/1     ImagePullBackOff   0          2m

# Service selector matches the pod labels
kubectl get pods -n helm-scenarios -l app.kubernetes.io/instance=recovery-demo
# NAME                    READY   STATUS             RESTARTS   AGE
# recovery-demo-xyz       0/1     ImagePullBackOff   0          2m

# But endpoints are empty (pod not ready)
kubectl get endpoints recovery-demo -n helm-scenarios
# NAME            ENDPOINTS   AGE
# recovery-demo   <none>      2m

# Service has no backends → requests fail
curl http://recovery-demo.helm-scenarios.svc.cluster.local
# curl: (7) Failed to connect to recovery-demo.helm-scenarios.svc.cluster.local port 80: Connection refused
```

**After rollback to working version:**
```bash
# Pods are ready
kubectl get pods -n helm-scenarios
# NAME                    READY   STATUS    RESTARTS   AGE
# recovery-demo-abc       1/1     Running   0          1m

# Endpoints now populated
kubectl get endpoints recovery-demo -n helm-scenarios
# NAME            ENDPOINTS        AGE
# recovery-demo   10.244.1.5:80    5m

# Service routes to healthy pods
curl http://recovery-demo.helm-scenarios.svc.cluster.local
# (nginx response)
```

---

## 📄 templates/_helpers.tpl - Template Helper Functions

```yaml
{{/*
Generate the full name for resources.
*/}}
{{- define "recovery-demo.fullname" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Generate chart labels.
*/}}
{{- define "recovery-demo.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- if .Values.labels }}
{{- range $key, $val := .Values.labels }}
{{ $key }}: {{ $val | quote }}
{{- end }}
{{- end }}
{{- end -}}

{{/*
Selector labels (subset of labels used for pod selection).
*/}}
{{- define "recovery-demo.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
```

### Helper Template Breakdown

#### recovery-demo.fullname

**What it is:** Generates resource name from release name

```go
{{- define "recovery-demo.fullname" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
```

**Breakdown:**
- `printf "%s" .Release.Name` - Format release name as string
- `trunc 63` - Truncate to 63 characters (DNS label max length)
- `trimSuffix "-"` - Remove trailing dash (if truncation cuts mid-word)

**Examples:**
```yaml
# Release: recovery-demo
{{ include "recovery-demo.fullname" . }}
# → recovery-demo

# Release: my-very-long-release-name-that-exceeds-sixty-three-characters-limit
{{ include "recovery-demo.fullname" . }}
# → my-very-long-release-name-that-exceeds-sixty-three-character
#   (truncated to 63 chars, no trailing dash)
```

**Why 63 characters:**
- **DNS label limit** - Kubernetes resource names become DNS labels
- **RFC 1035** - Max 63 characters per DNS label
- **Kubernetes requirement** - Names must be valid DNS subdomain names

**Usage in templates:**
```yaml
# deployment.yaml
metadata:
  name: {{ include "recovery-demo.fullname" . }}
# → name: recovery-demo

# service.yaml
metadata:
  name: {{ include "recovery-demo.fullname" . }}
# → name: recovery-demo

# Result: Deployment and Service have same name (common pattern)
```

#### recovery-demo.labels

**What it is:** Generates standard Kubernetes labels plus custom labels

```go
{{- define "recovery-demo.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- if .Values.labels }}
{{- range $key, $val := .Values.labels }}
{{ $key }}: {{ $val | quote }}
{{- end }}
{{- end }}
{{- end -}}
```

**Standard Kubernetes labels:**

| Label | Value | Purpose |
|-------|-------|---------|
| `app.kubernetes.io/name` | `recovery-demo` | Application name |
| `app.kubernetes.io/instance` | `recovery-demo` | Release name (unique instance) |
| `app.kubernetes.io/version` | `"1.0.0"` | Application version |
| `app.kubernetes.io/managed-by` | `Helm` | Tool managing the resource |
| `helm.sh/chart` | `recovery-demo-1.0.0` | Chart name and version |

**Custom labels from values:**
```yaml
# values.yaml
labels:
  version: "v1"

# Rendered:
version: "v1"
```

**Complete rendered output:**
```yaml
labels:
  app.kubernetes.io/name: recovery-demo
  app.kubernetes.io/instance: recovery-demo
  app.kubernetes.io/version: "1.0.0"
  app.kubernetes.io/managed-by: Helm
  helm.sh/chart: recovery-demo-1.0.0
  version: "v1"
```

**Why recommended labels:**
- **Tooling integration** - kubectl, monitoring, service mesh understand these
- **Consistency** - Standard across all Kubernetes applications
- **Filtering** - Easy to find resources by name, instance, version
- **Observability** - Dashboards can group by these labels

**Template syntax explained:**

```go
{{- if .Values.labels }}           # If custom labels defined
{{- range $key, $val := .Values.labels }}   # Iterate over each key-value pair
{{ $key }}: {{ $val | quote }}     # Output key: "value"
{{- end }}                         # End loop
{{- end }}                         # End if
```

**Example with multiple custom labels:**
```yaml
# values.yaml
labels:
  version: "v1"
  environment: production
  team: platform

# Rendered:
version: "v1"
environment: "production"
team: "platform"
```

#### recovery-demo.selectorLabels

**What it is:** Subset of labels for pod selection (immutable)

```go
{{- define "recovery-demo.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
```

**Renders to:**
```yaml
app.kubernetes.io/name: recovery-demo
app.kubernetes.io/instance: recovery-demo
```

**Why separate from full labels:**
- **Immutability** - Deployment selector cannot change after creation
- **Stability** - These labels never change across upgrades
- **Minimal** - Only include identifying labels, not version/environment

**Used in:**

```yaml
# Deployment selector (immutable)
spec:
  selector:
    matchLabels:
      {{- include "recovery-demo.selectorLabels" . | nindent 6 }}

# Service selector (can change)
spec:
  selector:
    {{- include "recovery-demo.selectorLabels" . | nindent 4 }}
```

**What's NOT included:**
- `app.kubernetes.io/version` - Changes on upgrades
- `helm.sh/chart` - Changes when chart version updates
- `version` - Custom label that changes (v1 → v2)

**Why exclude version from selector:**

```yaml
# BAD: Including version in selector
selector:
  matchLabels:
    app.kubernetes.io/name: recovery-demo
    version: v1   # ← Problem!

# Upgrade to v2:
# - New pods have version: v2
# - Selector needs to change: v1 → v2
# - Kubernetes FORBIDS selector changes
# - Must delete and recreate Deployment
# - Causes downtime

# GOOD: Exclude version from selector
selector:
  matchLabels:
    app.kubernetes.io/name: recovery-demo
    app.kubernetes.io/instance: recovery-demo

# Upgrade to v2:
# - Selector stays the same
# - New pods have version: v2 (but also have selector labels)
# - Deployment matches both v1 and v2 pods during rolling update
# - Rolling update proceeds smoothly
# - Zero downtime
```

---

## 🔄 How Helm Handles Failed Releases

### Release State Transitions

When an upgrade fails, Helm goes through these states:

```
1. Current release (revision N): Status = deployed
   ↓
2. helm upgrade command starts
   ↓
3. Helm creates new revision (N+1): Status = pending-upgrade
   ↓
4. Helm applies manifests to Kubernetes
   ↓
5. Helm waits for resources to become ready (--wait flag)
   ↓
6a. SUCCESS: All resources ready within timeout
    → Revision N+1: Status = deployed
    → Revision N: Status = superseded

6b. FAILURE: Resources not ready within timeout
    → Revision N+1: Status = failed
    → Revision N: Status = superseded (still!)
    → Current revision is N+1 (the failed one)
```

### Why Failed Revisions Matter

**Helm history after failed upgrade:**
```bash
helm history recovery-demo -n helm-scenarios

REVISION  STATUS      CHART             DESCRIPTION
1         superseded  recovery-demo-1.0.0  Install complete
2         failed      recovery-demo-1.0.0  Upgrade "recovery-demo" failed: timed out waiting for the condition
```

**Key insights:**
- **Revision 1 is superseded** - Even though revision 2 failed
- **Current revision is 2** - The failed revision is "current"
- **Can roll back to revision 1** - History preserved
- **Failed revision kept** - Useful for forensics

### Timeout Mechanism

**Default timeout:** 5 minutes (300 seconds)

**Custom timeout:**
```bash
helm upgrade recovery-demo ./chart -f bad-values.yaml --timeout 30s
#                                                      ^^^^^^^^^^^^
#                                            Only wait 30 seconds
```

**What happens during timeout:**

```
T=0s:   helm upgrade starts
        - Helm applies Deployment manifest
        - Kubernetes creates new ReplicaSet
        - Kubelet tries to pull image nginx:99.99.99-nonexistent

T=5s:   First ImagePullBackOff
        - Pull fails (404 Not Found)
        - Pod enters ErrImagePull state

T=10s:  Kubernetes retries pull
        - Pull fails again
        - Pod enters ImagePullBackOff
        - Exponential backoff begins (10s → 20s → 40s...)

T=30s:  Helm timeout reached (--timeout 30s)
        - Helm checks pod status: Not Ready
        - Helm marks release as FAILED
        - Helm exits with error code
        - But: Kubernetes keeps trying to pull image!
```

**Important:** Timeout doesn't stop Kubernetes from continuing attempts.

```bash
# After Helm times out and fails
kubectl get pods -n helm-scenarios

# Pods still exist and still trying to pull image
# NAME                    READY   STATUS             RESTARTS   AGE
# recovery-demo-xyz       0/1     ImagePullBackOff   0          5m
```

### Recovery Strategies

#### Strategy 1: Rollback

**When to use:**
- Failed upgrade (have previous good revision)
- Want to restore known-good state quickly
- Preserve release history

**How it works:**
```bash
helm rollback recovery-demo 1 -n helm-scenarios --wait
```

**What happens:**
1. Helm retrieves config from revision 1
2. Applies revision 1 manifests
3. Kubernetes performs rolling update
   - Creates pods with working image (nginx:1.24-alpine)
   - Terminates pods with broken image (nginx:99.99.99-nonexistent)
4. Creates new revision 3 (with revision 1's config)
5. Marks revision 3 as deployed

**Result:**
```bash
helm history recovery-demo -n helm-scenarios

REVISION  STATUS      CHART               DESCRIPTION
1         superseded  recovery-demo-1.0.0 Install complete
2         superseded  recovery-demo-1.0.0 Upgrade failed
3         deployed    recovery-demo-1.0.0 Rollback to 1
```

#### Strategy 2: Fix and Re-upgrade

**When to use:**
- Know the fix (e.g., correct image tag)
- Want to move forward, not backward
- Testing in non-production

**How it works:**
```bash
# Fix values
# Edit bad-values.yaml: tag: "1.24-alpine" (not "99.99.99-nonexistent")

# Re-upgrade
helm upgrade recovery-demo ./chart -f bad-values.yaml -n helm-scenarios --wait
```

**Result:**
```bash
helm history recovery-demo -n helm-scenarios

REVISION  STATUS      CHART               DESCRIPTION
1         superseded  recovery-demo-1.0.0 Install complete
2         superseded  recovery-demo-1.0.0 Upgrade failed
3         deployed    recovery-demo-1.0.0 Upgrade complete
```

#### Strategy 3: Uninstall and Reinstall

**When to use:**
- **pending-install** state (can't rollback from first install)
- Release history corrupted
- Want clean slate

**How it works:**
```bash
# Remove release entirely
helm uninstall recovery-demo -n helm-scenarios --wait

# Reinstall fresh
helm install recovery-demo ./chart -f values.yaml -n helm-scenarios --wait
```

**Result:**
- All history deleted
- New release starts at revision 1
- Clean state, but lose audit trail

**Trade-offs:**

| Strategy | Speed | History | Downtime | Use Case |
|----------|-------|---------|----------|----------|
| **Rollback** | Fast | Preserved | Minimal | Production, known-good state |
| **Fix + Re-upgrade** | Medium | Preserved | Minimal | Development, forward-looking |
| **Uninstall + Reinstall** | Slow | Lost | Full downtime | Stuck states, corruption |

---

## 🐛 Troubleshooting Failed Releases

### Diagnostic Workflow

```
1. Check release status
   helm status <release> -n <namespace>
   ↓
2. View release history
   helm history <release> -n <namespace>
   ↓
3. Check pod status
   kubectl get pods -n <namespace> -l app.kubernetes.io/instance=<release>
   ↓
4. Describe failing pods
   kubectl describe pod <pod-name> -n <namespace>
   ↓
5. Check pod logs
   kubectl logs <pod-name> -n <namespace>
   ↓
6. Choose recovery strategy (rollback, fix, or reinstall)
```

### Common Failure Scenarios

#### ImagePullBackOff

**Symptoms:**
```bash
kubectl get pods -n helm-scenarios
# NAME                    READY   STATUS             RESTARTS   AGE
# recovery-demo-xyz       0/1     ImagePullBackOff   0          2m
```

**Diagnosis:**
```bash
kubectl describe pod recovery-demo-xyz -n helm-scenarios
# Events:
#   Warning  Failed     kubelet  Failed to pull image "nginx:99.99.99-nonexistent"
#   Warning  Failed     kubelet  Error: ErrImagePull
```

**Causes:**
- Non-existent image tag
- Wrong registry URL
- Missing image pull secrets (private registry)
- Network issues

**Recovery:**
```bash
# Option 1: Rollback
helm rollback recovery-demo 1 -n helm-scenarios --wait

# Option 2: Fix image tag and re-upgrade
# Edit values: tag: "1.24-alpine"
helm upgrade recovery-demo ./chart -f values-fixed.yaml -n helm-scenarios --wait
```

#### CrashLoopBackOff

**Symptoms:**
```bash
kubectl get pods -n helm-scenarios
# NAME                    READY   STATUS             RESTARTS   AGE
# recovery-demo-xyz       0/1     CrashLoopBackOff   5          5m
```

**Diagnosis:**
```bash
kubectl logs recovery-demo-xyz -n helm-scenarios --previous
# (logs from crashed container)

kubectl describe pod recovery-demo-xyz -n helm-scenarios
# Events:
#   Warning  BackOff    kubelet  Back-off restarting failed container
```

**Causes:**
- Application crashes on startup
- Missing environment variables
- Failed liveness probe
- OOMKilled (memory limit exceeded)

**Recovery:**
```bash
# Check what changed
helm diff revision recovery-demo 1 2 -n helm-scenarios

# Rollback to stable version
helm rollback recovery-demo -n helm-scenarios --wait
```

#### Insufficient Resources

**Symptoms:**
```bash
kubectl get pods -n helm-scenarios
# NAME                    READY   STATUS    RESTARTS   AGE
# recovery-demo-xyz       0/1     Pending   0          10m
```

**Diagnosis:**
```bash
kubectl describe pod recovery-demo-xyz -n helm-scenarios
# Events:
#   Warning  FailedScheduling  default-scheduler  0/3 nodes available: insufficient cpu
```

**Causes:**
- Requested resources exceed node capacity
- No nodes with enough available resources
- Resource quotas exceeded

**Recovery:**
```bash
# Option 1: Reduce resource requests
# Edit values: resources.requests.cpu: "10m" (instead of "1000m")
helm upgrade recovery-demo ./chart -f values-lower-resources.yaml -n helm-scenarios --wait

# Option 2: Rollback to previous (lower) resources
helm rollback recovery-demo -n helm-scenarios --wait
```

#### Pending-Install State

**Symptoms:**
```bash
helm list -n helm-scenarios
# NAME            STATUS          CHART
# recovery-demo   pending-install recovery-demo-1.0.0
```

**Causes:**
- First install timed out
- Pods never became ready
- Ctrl+C during installation

**Why rollback doesn't work:**
```bash
helm rollback recovery-demo -n helm-scenarios
# Error: no revision to rollback to
# (Only revision 1 exists, and it's the current failed install)
```

**Recovery:**
```bash
# Must uninstall and reinstall
helm uninstall recovery-demo -n helm-scenarios --wait
kubectl delete pods -n helm-scenarios -l app.kubernetes.io/instance=recovery-demo --force --grace-period=0

# Reinstall with working values
helm install recovery-demo ./chart -f values.yaml -n helm-scenarios --wait
```

---

## 📚 Best Practices for Release Recovery

### Prevention

✅ **Test upgrades in non-production first**
```bash
# Staging environment
helm upgrade my-app ./chart -f staging-values.yaml --namespace staging --wait

# If successful, then production
helm upgrade my-app ./chart -f production-values.yaml --namespace production --wait
```

✅ **Use --dry-run to preview changes**
```bash
helm upgrade recovery-demo ./chart -f bad-values.yaml --dry-run --debug
# Review rendered manifests before applying
```

✅ **Always use --wait flag**
```bash
helm upgrade recovery-demo ./chart -f values.yaml --wait --timeout 5m
# Ensures Helm waits for resources to be ready
# Catches failures immediately
```

✅ **Set appropriate timeouts**
```bash
# Short timeout for fast-starting apps
helm upgrade web-app ./chart --wait --timeout 2m

# Long timeout for slow-starting apps (databases, big JVM apps)
helm upgrade postgres ./chart --wait --timeout 10m
```

✅ **Use liveness and readiness probes**
```yaml
# In deployment template
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Recovery

✅ **Know your last good revision before upgrading**
```bash
helm history recovery-demo -n helm-scenarios
# Note current deployed revision number
```

✅ **Have rollback command ready**
```bash
# Prepare before upgrade
LAST_GOOD_REV=$(helm history recovery-demo -n helm-scenarios --max 1 --output json | jq '.[0].revision')

# If upgrade fails
helm rollback recovery-demo $LAST_GOOD_REV -n helm-scenarios --wait
```

✅ **Automate rollback in CI/CD**
```bash
#!/bin/bash
if ! helm upgrade my-app ./chart -f values.yaml --wait --timeout 5m; then
    echo "Upgrade failed, rolling back..."
    helm rollback my-app --namespace production --wait
    exit 1
fi
```

✅ **Monitor during and after upgrade**
```bash
# Terminal 1: Watch pods
watch kubectl get pods -n helm-scenarios

# Terminal 2: Perform upgrade
helm upgrade recovery-demo ./chart -f values.yaml -n helm-scenarios --wait

# Terminal 3: Check application health
watch curl -s http://recovery-demo.helm-scenarios.svc.cluster.local/health
```

✅ **Document incidents**
```bash
# After recovery, document what happened
helm history recovery-demo -n helm-scenarios > incident-2024-01-15.txt

# Save failed manifest for analysis
helm get manifest recovery-demo --revision 2 -n helm-scenarios > failed-manifest.yaml
```

### Maintenance

✅ **Regularly clean up old revisions**
```bash
# Keep last 10 revisions only
helm upgrade recovery-demo ./chart --history-max 10 -n helm-scenarios
```

✅ **Back up release history**
```bash
# Export release history
helm get values recovery-demo -n helm-scenarios --revision 1 > backup-rev1-values.yaml
helm get manifest recovery-demo -n helm-scenarios --revision 1 > backup-rev1-manifest.yaml
```

✅ **Use Helm diff plugin**
```bash
# Install plugin
helm plugin install https://github.com/databus23/helm-diff

# Preview changes before upgrade
helm diff upgrade recovery-demo ./chart -f new-values.yaml -n helm-scenarios
```

---

## 🎓 Key Takeaways

1. **Release states matter** - Understanding deployed, failed, pending-* states is critical
2. **Timeout controls failure detection** - Use --timeout to fail fast or wait longer
3. **Rollback is safest** - Creates new revision with old config, preserves history
4. **pending-install requires uninstall** - Can't rollback from first revision
5. **Failed revision is current** - Even though it failed, it's the active revision
6. **Kubernetes continues after Helm fails** - Timeout stops Helm, not Kubernetes
7. **Always use --wait** - Ensures Helm waits for pods to be ready
8. **Test before production** - Catch failures in staging, not production
9. **Have rollback plan ready** - Know last good revision before upgrading
10. **Automate recovery** - CI/CD should auto-rollback on failure

---

## 🔗 Further Reading

- **Helm Rollback Documentation**: https://helm.sh/docs/helm/helm_rollback/
- **Helm Status Documentation**: https://helm.sh/docs/helm/helm_status/
- **Kubernetes Pod Lifecycle**: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
- **Container Probes**: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- **Helm Best Practices**: https://helm.sh/docs/chart_best_practices/
- **Debugging Kubernetes Deployments**: https://kubernetes.io/docs/tasks/debug/

---

*This guide provides comprehensive coverage of Helm failed release recovery. Mastering these techniques ensures you can quickly diagnose and recover from production deployment failures, minimizing downtime and maintaining system reliability.*
