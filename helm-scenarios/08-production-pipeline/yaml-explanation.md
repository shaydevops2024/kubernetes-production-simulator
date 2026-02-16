# Helm Production Pipeline Explanation

This guide explains how to build a production-grade Helm deployment pipeline with linting, testing, atomic upgrades, and automated rollback. You'll understand every component needed for safe, reliable Kubernetes deployments.

---

## Table of Contents
1. [What is a Production Helm Pipeline?](#what-is-a-production-helm-pipeline)
2. [Chart.yaml - Pipeline Metadata](#chartyaml---pipeline-metadata)
3. [values.yaml - Default Configuration](#valuesyaml---default-configuration)
4. [values-staging.yaml - Staging Environment](#values-stagingyaml---staging-environment)
5. [values-prod.yaml - Production Environment](#values-prodyaml---production-environment)
6. [templates/deployment.yaml - Application Workload](#templatesdeploymentyaml---application-workload)
7. [templates/service.yaml - Network Exposure](#templatesserviceyaml---network-exposure)
8. [templates/tests/test-connection.yaml - Automated Testing](#templatesteststest-connectionyaml---automated-testing)
9. [Production Pipeline Stages](#production-pipeline-stages)
10. [Helm Safety Flags](#helm-safety-flags)
11. [Troubleshooting Production Issues](#troubleshooting-production-issues)
12. [Best Practices](#best-practices)

---

## What is a Production Helm Pipeline?

A **production Helm pipeline** is a systematic approach to deploying applications safely using Helm in CI/CD workflows. It includes validation, testing, deployment strategies, and automated recovery mechanisms.

### Why Production Pipelines Matter

**Without a pipeline (manual deployment):**
```bash
# Developer manually deploys
helm upgrade myapp ./chart
# ❌ No validation
# ❌ No testing
# ❌ No rollback plan
# ❌ Manual error-prone process
```

**With a production pipeline:**
```bash
# CI Stage (validation)
helm lint ./chart
helm template ./chart | kubeval
helm diff upgrade myapp ./chart

# CD Stage (safe deployment)
helm upgrade myapp ./chart --atomic --timeout 5m
helm test myapp
# ✅ Validated before deployment
# ✅ Automatically tested
# ✅ Auto-rollback on failure
# ✅ Repeatable and auditable
```

### Pipeline Benefits

- **Early Error Detection**: Catch issues in CI before they reach production
- **Consistent Deployments**: Same process every time, no human error
- **Automated Testing**: helm test validates deployments automatically
- **Safe Rollbacks**: --atomic flag auto-recovers from failures
- **Multi-Environment**: Separate values files for staging/production
- **Audit Trail**: Helm release history tracks all changes
- **Zero-Downtime**: Readiness probes + rolling updates prevent outages

---

## Chart.yaml - Pipeline Metadata

### Full File

```yaml
apiVersion: v2
name: pipeline-app
description: A production pipeline demo chart with linting, testing, and canary support
type: application
version: 1.0.0
appVersion: "1.0.0"
```

### Field-by-Field Breakdown

#### apiVersion: v2

**What it is:** Helm chart API version

**Options:**
- `v2` - Helm 3 (current standard)
- `v1` - Helm 2 (deprecated, removed)

**Why v2:**
- Required for Helm 3 compatibility
- Supports modern features (OCI registries, library charts)
- Required for Chart.lock and dependency conditions

#### name: pipeline-app

**What it is:** Chart name (used in `helm install <name>`)

**Naming conventions:**
- Lowercase letters, numbers, hyphens only
- Should match directory name
- Descriptive and unique within your organization

**Usage:**
```bash
# Chart name appears in:
helm install my-release pipeline-app/
# Resource names: <release-name> (not chart name)
kubectl get deployment my-release  # Uses release name
```

#### description

**What it is:** Human-readable chart description

**Best practices:**
- Keep under 120 characters
- Mention key features (testing, canary, multi-environment)
- Include use case (demo, production-ready, etc.)

**Where it appears:**
```bash
helm search repo pipeline-app
# Shows description in results

helm show chart pipeline-app
# Displays full chart metadata
```

#### type: application

**What it is:** Chart type classification

**Options:**

| Type | Purpose | Can Install? | Use Case |
|------|---------|--------------|----------|
| `application` | Deploys workloads | Yes | Normal apps, services |
| `library` | Reusable templates | No | Shared helpers, functions |

**Why application:**
- We're deploying actual resources (Deployment, Service)
- Library charts only provide templates to other charts
- Application charts can have dependencies

**Library chart example:**
```yaml
# common-lib/Chart.yaml
apiVersion: v2
name: common-lib
type: library  # Can't be installed directly

# app-chart/Chart.yaml
dependencies:
  - name: common-lib
    version: "1.0.0"
    repository: "file://../common-lib"
```

#### version: 1.0.0

**What it is:** Chart version (SemVer format)

**SemVer breakdown:**
- `1.0.0` = MAJOR.MINOR.PATCH
- **MAJOR**: Incompatible API changes (breaking)
- **MINOR**: Backwards-compatible functionality added
- **PATCH**: Backwards-compatible bug fixes

**When to bump:**

| Change | Version | Example |
|--------|---------|---------|
| Breaking template change | 2.0.0 | Remove required value |
| New feature/template | 1.1.0 | Add canary support |
| Bug fix | 1.0.1 | Fix typo in template |
| Value change (no template) | 1.0.1 | Update default replica count |

**Production strategy:**
```yaml
# Development
version: 1.0.0-beta.1

# Release candidate
version: 1.0.0-rc.1

# Production
version: 1.0.0

# Post-release fix
version: 1.0.1
```

#### appVersion: "1.0.0"

**What it is:** Version of the application being deployed (not the chart)

**Chart vs App Version:**

| Version | What It Tracks | Example |
|---------|----------------|---------|
| `version` | Helm chart changes | Template updates, new features |
| `appVersion` | Application code version | nginx 1.24 → 1.25 |

**Example evolution:**

```yaml
# Release 1: Initial chart
version: 1.0.0
appVersion: "1.0.0"  # nginx 1.24

# Release 2: Update nginx version (app change, chart unchanged)
version: 1.0.1       # Patch bump (updated default)
appVersion: "1.0.1"  # nginx 1.25

# Release 3: Add HPA template (chart change)
version: 1.1.0       # Minor bump (new feature)
appVersion: "1.0.1"  # Same app version
```

**Best practices:**
- Always use quotes: `"1.0.0"` (YAML treats bare numbers oddly)
- Match image tag when possible
- Use in image tag: `image: "nginx:{{ .Chart.AppVersion }}"`

**Usage in templates:**
```yaml
# templates/deployment.yaml
spec:
  template:
    metadata:
      labels:
        app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
    spec:
      containers:
        - image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
```

---

## values.yaml - Default Configuration

### Full File

```yaml
replicaCount: 2
image:
  repository: nginx
  tag: "1.24"
  pullPolicy: IfNotPresent
service:
  type: ClusterIP
  port: 80
resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 50m
    memory: 64Mi
canary:
  enabled: false
  weight: 20
healthcheck:
  path: /
  port: 80
```

### replicaCount: 2

**What it is:** Number of pod replicas for the deployment

**Why 2 as default:**
- **High availability**: Survives single pod failure
- **Rolling updates**: Can update one pod while other serves traffic
- **Reasonable resource usage**: Not excessive for default
- **Not production-scale**: Production overrides to 3+

**Replica count strategy:**

| Replicas | Use Case | Availability | Cost |
|----------|----------|--------------|------|
| 1 | Development, testing | No HA | Low |
| 2 | Staging, small prod | Basic HA | Medium |
| 3+ | Production standard | High HA | High |
| 5+ | High-traffic production | Very high HA | Very high |

**How it's used:**
```yaml
# templates/deployment.yaml
spec:
  replicas: {{ .Values.replicaCount }}
```

### image

**What it is:** Container image configuration

#### image.repository: nginx

**What it is:** Container image name (without tag)

**Format options:**
- `nginx` - Docker Hub official image
- `bitnami/nginx` - Docker Hub user/org image
- `ghcr.io/myorg/myapp` - GitHub Container Registry
- `myregistry.io:5000/myapp` - Private registry

**Production considerations:**
```yaml
# Development
image:
  repository: nginx  # Public Docker Hub

# Production
image:
  repository: mycompany.azurecr.io/nginx  # Private registry
```

#### image.tag: "1.24"

**What it is:** Container image tag/version

**Why quotes:** YAML interprets `1.24` as number, quotes preserve string

**Tag strategies:**

| Strategy | Example | Pros | Cons |
|----------|---------|------|------|
| **Specific version** | `"1.24.0"` | Reproducible, safe | Manual updates |
| **Minor version** | `"1.24"` | Auto patch updates | Less predictable |
| **Latest** | `"latest"` | Always current | Unpredictable, dangerous |
| **SHA digest** | `"sha256:abc..."` | Immutable, secure | Hard to read |

**Best practices:**
```yaml
# Production: Always specific versions
image:
  tag: "1.24.0"

# Use Chart.AppVersion as default
image:
  tag: "{{ .Chart.AppVersion }}"
```

#### image.pullPolicy: IfNotPresent

**What it is:** When to pull the image from registry

**Options:**

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `IfNotPresent` | Pull only if not cached | Default, efficient |
| `Always` | Pull on every pod start | Ensure latest image |
| `Never` | Never pull, use cache only | Air-gapped, testing |

**Default Kubernetes behavior:**
- Tags with `:latest` → defaults to `Always`
- Specific tags (`:1.24`) → defaults to `IfNotPresent`

**Production recommendation:**
```yaml
# Use Always with floating tags
image:
  tag: "1.24"  # Minor version, may update
  pullPolicy: Always  # Get patch updates

# Use IfNotPresent with specific tags
image:
  tag: "1.24.0"  # Exact version
  pullPolicy: IfNotPresent  # No need to pull repeatedly
```

### service

**What it is:** Kubernetes Service configuration for network exposure

#### service.type: ClusterIP

**What it is:** Service type determining how it's exposed

**Service types:**

| Type | Access | IP Source | Use Case |
|------|--------|-----------|----------|
| `ClusterIP` | Internal only | Cluster internal IP | Microservices, databases |
| `NodePort` | External via node:port | Cluster IP + node ports | Testing, non-cloud |
| `LoadBalancer` | External via LB | Cloud provider LB | Production web apps |
| `ExternalName` | DNS CNAME | None (DNS alias) | External service proxy |

**Why ClusterIP as default:**
- Most services are internal (microservices architecture)
- External access via Ingress (Layer 7, more features)
- Cheaper (no LoadBalancer cost)
- More secure (not directly exposed)

**Production pattern:**
```yaml
# Internal service
service:
  type: ClusterIP

# Ingress for external access
ingress:
  enabled: true
  hosts:
    - host: myapp.example.com
```

#### service.port: 80

**What it is:** Port the Service listens on

**Port vs TargetPort:**
- `port: 80` - Service port (what clients connect to)
- `targetPort: 8080` - Container port (where app listens)

**Example:**
```yaml
# Service listens on 80, forwards to container port 8080
service:
  port: 80
  targetPort: 8080

# Access from another pod:
curl http://pipeline-app:80
# → Forwards to pod port 8080
```

### resources

**What it is:** CPU and memory resource management

#### Structure

```yaml
resources:
  limits:    # Maximum allowed
    cpu: 100m
    memory: 128Mi
  requests:  # Minimum guaranteed
    cpu: 50m
    memory: 64Mi
```

**Requests vs Limits:**

| Type | Purpose | Impact | Exceeding Limit |
|------|---------|--------|-----------------|
| **requests** | Scheduling guarantee | Pod placement | N/A (always available) |
| **limits** | Resource cap | Throttling/OOM | CPU: throttled, Memory: killed |

#### CPU Units

**Format:**
- `1` or `1000m` = 1 full CPU core
- `100m` = 0.1 cores (10% of one core)
- `50m` = 0.05 cores (5% of one core)

**Our values:**
- `requests.cpu: 50m` - Guaranteed 5% of a core
- `limits.cpu: 100m` - Max 10% of a core
- **Ratio: 2x** - Can burst to 2× baseline

**Choosing CPU values:**

| Application | Requests | Limits | Reasoning |
|-------------|----------|--------|-----------|
| Static web server | 50m | 100m | Low CPU need |
| API backend | 250m | 1000m | Moderate CPU, allow burst |
| Data processing | 1000m | 2000m | CPU-intensive |

#### Memory Units

**Format:**
- `Mi` = Mebibyte (1024² bytes = 1,048,576 bytes)
- `Gi` = Gibibyte (1024³ bytes = 1,073,741,824 bytes)
- `M` = Megabyte (1000² bytes) - avoid, less common in K8s
- `G` = Gigabyte (1000³ bytes) - avoid, less common in K8s

**Our values:**
- `requests.memory: 64Mi` - Guaranteed 67 MB
- `limits.memory: 128Mi` - Max 134 MB
- **Ratio: 2x** - Can use up to 2× baseline

**Memory behavior:**
- **Exceeding limit**: Pod killed with OOMKilled (Out Of Memory)
- **Restart policy**: Usually `Always`, pod restarts after OOM
- **No throttling**: Unlike CPU, memory can't be throttled

**Quality of Service (QoS) Classes:**

| QoS Class | Condition | Priority | Our Config |
|-----------|-----------|----------|------------|
| **Guaranteed** | requests = limits | Highest | No |
| **Burstable** | requests < limits | Medium | **Yes** ✓ |
| **BestEffort** | No requests/limits | Lowest | No |

**Production recommendations:**
```yaml
# Development/Staging (low resources)
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 100m
    memory: 128Mi

# Production (generous resources, 2-4x burst)
resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 1000m
    memory: 512Mi
```

### canary

**What it is:** Canary deployment configuration (feature flag)

```yaml
canary:
  enabled: false  # Disabled by default
  weight: 20      # 20% traffic to canary when enabled
```

**What is a canary deployment:**
- Deploy new version alongside old version
- Route small percentage of traffic to new version
- Monitor metrics, error rates
- Gradually increase traffic or rollback

**How it works with Helm:**
```bash
# Install main release
helm install myapp ./pipeline-app

# Install canary release with canary values
helm install myapp-canary ./pipeline-app \
  --set canary.enabled=true \
  --set canary.weight=10 \
  --set image.tag=2.0.0-rc1

# Service mesh routes 10% to canary
# Monitor, then increase weight or rollback
```

**Canary workflow:**
```
1. Deploy v1.0 (100% traffic) ← stable
2. Deploy v2.0-canary (10% traffic) ← test
3. Monitor metrics for 30 min
4. If healthy: increase to 50%
5. If healthy: increase to 100%
6. Delete canary release, upgrade main to v2.0
7. If unhealthy at any point: delete canary
```

**Traffic splitting requires:**
- Service mesh (Istio, Linkerd) OR
- Ingress controller with traffic splitting (NGINX Plus, Traefik) OR
- Flagger (progressive delivery operator)

### healthcheck

**What it is:** Health probe configuration for liveness/readiness checks

```yaml
healthcheck:
  path: /
  port: 80
```

**Purpose:**
- Kubernetes uses this to check if container is healthy
- Liveness probe: Restart container if failing
- Readiness probe: Remove from service endpoints if failing

**How it's used:**
```yaml
# templates/deployment.yaml
livenessProbe:
  httpGet:
    path: {{ .Values.healthcheck.path }}
    port: {{ .Values.healthcheck.port }}
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: {{ .Values.healthcheck.path }}
    port: {{ .Values.healthcheck.port }}
  initialDelaySeconds: 3
  periodSeconds: 5
```

**Best practices:**
```yaml
# Simple web server
healthcheck:
  path: /
  port: 80

# Application with health endpoint
healthcheck:
  path: /health
  port: 8080

# Application with separate readiness check
healthcheck:
  liveness:
    path: /healthz
    port: 8080
  readiness:
    path: /ready
    port: 8080
```

---

## values-staging.yaml - Staging Environment

### Full File

```yaml
replicaCount: 1
image:
  tag: "1.24"
resources:
  limits:
    cpu: 50m
    memory: 64Mi
  requests:
    cpu: 25m
    memory: 32Mi
```

### Purpose

**Staging environment characteristics:**
- **Lower cost**: Fewer resources than production
- **Testing ground**: Validates changes before production
- **Production-like**: Same chart, different scale
- **Overrides only**: Only specifies changed values

### Merging Strategy

**Helm merges values in this order:**
1. Chart's `values.yaml` (defaults)
2. `-f values-staging.yaml` (overrides)
3. `--set` flags (highest priority)

**Resulting merged values:**
```yaml
# Merged result when using: -f values-staging.yaml
replicaCount: 1           # From values-staging.yaml
image:
  repository: nginx       # From values.yaml (not overridden)
  tag: "1.24"            # From values-staging.yaml
  pullPolicy: IfNotPresent  # From values.yaml (not overridden)
service:
  type: ClusterIP         # From values.yaml (not overridden)
  port: 80                # From values.yaml (not overridden)
resources:                # From values-staging.yaml
  limits:
    cpu: 50m
    memory: 64Mi
  requests:
    cpu: 25m
    memory: 32Mi
```

### replicaCount: 1

**Why 1 in staging:**
- **Cost savings**: Half the pods of default (2 → 1)
- **Sufficient for testing**: Single replica can validate functionality
- **Not production-ready**: Staging doesn't need HA

**Risk:**
- No high availability (pod failure = downtime)
- Can't test load balancing behavior
- Rolling update causes brief downtime

**Staging vs Production replicas:**
```yaml
# values-staging.yaml
replicaCount: 1  # Minimal, cost-effective

# values-prod.yaml
replicaCount: 3  # HA, load distribution
```

### resources (Staging)

**Staging resources:**
```yaml
resources:
  requests:
    cpu: 25m      # 50% less than default
    memory: 32Mi  # 50% less than default
  limits:
    cpu: 50m      # 50% less than default
    memory: 64Mi  # 50% less than default
```

**Why reduce resources in staging:**
- Lower cost (less cluster capacity needed)
- Sufficient for functional testing
- Tests if app works with minimal resources
- Still maintains 2x burst ratio (requests → limits)

**Staging vs Production resources:**

| Environment | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-------------|-------------|-----------|----------------|--------------|
| **Staging** | 25m | 50m | 32Mi | 64Mi |
| **Default** | 50m | 100m | 64Mi | 128Mi |
| **Production** | 100m | 200m | 128Mi | 256Mi |

---

## values-prod.yaml - Production Environment

### Full File

```yaml
replicaCount: 3
image:
  tag: "1.24"
resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

### Purpose

**Production environment characteristics:**
- **High availability**: 3+ replicas survive failures
- **Generous resources**: Handles real user traffic
- **Performance**: Lower latency, higher throughput
- **Reliability**: Tolerates pod/node failures

### replicaCount: 3

**Why 3 in production:**
- **High availability**: Survives 1 pod failure (2 remain)
- **Load distribution**: Spreads traffic across 3 pods
- **Rolling updates**: Update 1 pod at a time, 2 always available
- **Zone distribution**: Can spread across 3 availability zones

**Replica count formula:**
```
Minimum replicas = Max(
  3,  # HA baseline
  ceil(expectedQPS / podCapacity),  # Capacity planning
  ceil(zoneCount × 1.5)  # Zone distribution
)
```

**Example capacity planning:**
```
Expected load: 100 requests/second
Pod capacity: 50 requests/second
Required replicas: 100 / 50 = 2
With HA: 3 (to survive failures)
With overhead: 4 (to handle spikes)
```

**Replica strategy by traffic:**

| Traffic Level | Replicas | Reasoning |
|---------------|----------|-----------|
| Development | 1 | No HA needed |
| Staging | 1-2 | Basic testing |
| Small production | 3 | HA baseline |
| Medium production | 5-10 | Load + HA |
| High production | 10+ | Use HPA instead |

### resources (Production)

**Production resources:**
```yaml
resources:
  requests:
    cpu: 100m      # 2x default, 4x staging
    memory: 128Mi  # 2x default, 4x staging
  limits:
    cpu: 200m      # 2x default, 4x staging
    memory: 256Mi  # 2x default, 4x staging
```

**Why increase resources in production:**
- Handle real user traffic
- Faster response times
- Buffer for traffic spikes
- Prevent resource contention

**Resource scaling factor:**
```
Staging → Production: 4x resources
- 4x CPU request (25m → 100m)
- 4x CPU limit (50m → 200m)
- 4x Memory request (32Mi → 128Mi)
- 4x Memory limit (64Mi → 256Mi)
```

**Production resource sizing:**
```yaml
# Small production (< 1000 users)
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi

# Medium production (1000-10000 users)
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

# Large production (> 10000 users)
resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 2000m
    memory: 4Gi
```

---

## templates/deployment.yaml - Application Workload

### Full File

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}
  labels:
    app: {{ .Release.Name }}
    chart: {{ .Chart.Name }}-{{ .Chart.Version }}
    release: {{ .Release.Name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
        release: {{ .Release.Name }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - containerPort: 80
              protocol: TCP
          livenessProbe:
            httpGet:
              path: {{ .Values.healthcheck.path }}
              port: {{ .Values.healthcheck.port }}
            initialDelaySeconds: 5
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: {{ .Values.healthcheck.path }}
              port: {{ .Values.healthcheck.port }}
            initialDelaySeconds: 3
            periodSeconds: 5
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

### Metadata Section

#### name: {{ .Release.Name }}

**What it is:** Deployment name (from `helm install <name>`)

**Helm template objects:**
- `.Release.Name` - Name provided at install time
- `.Chart.Name` - Chart name from Chart.yaml
- `.Values.*` - Values from values.yaml

**Example:**
```bash
helm install my-app ./pipeline-app
# Creates Deployment named: my-app
```

#### labels

**Why labels matter:**
- Kubernetes uses labels for selection
- Enable querying: `kubectl get pods -l app=my-app`
- Required for Service selector matching
- Helm uses labels for release tracking

**Label best practices:**
```yaml
labels:
  app: {{ .Release.Name }}              # Application identifier
  chart: {{ .Chart.Name }}-{{ .Chart.Version }}  # Chart version tracking
  release: {{ .Release.Name }}           # Helm release tracking
  # Recommended additional labels:
  app.kubernetes.io/name: {{ .Chart.Name }}
  app.kubernetes.io/instance: {{ .Release.Name }}
  app.kubernetes.io/version: {{ .Chart.AppVersion }}
  app.kubernetes.io/managed-by: {{ .Release.Service }}  # "Helm"
```

### Spec Section

#### replicas: {{ .Values.replicaCount }}

**Template variable replacement:**
```yaml
# values-staging.yaml
replicaCount: 1

# Renders to:
spec:
  replicas: 1

# values-prod.yaml
replicaCount: 3

# Renders to:
spec:
  replicas: 3
```

#### selector.matchLabels

**Purpose:** Defines which pods belong to this Deployment

**Must match:** Pod template labels

**Example:**
```yaml
# Deployment selector
selector:
  matchLabels:
    app: my-app

# Pod template labels (must include app: my-app)
template:
  metadata:
    labels:
      app: my-app  # ← Matches selector
      release: my-app
```

**Common error:**
```yaml
# Wrong - selector mismatch
selector:
  matchLabels:
    app: my-app
template:
  metadata:
    labels:
      application: my-app  # ❌ Doesn't match "app"
# Error: selector doesn't match template labels
```

### Container Spec

#### image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"

**Template rendering:**
```yaml
# values.yaml
image:
  repository: nginx
  tag: "1.24"

# Renders to:
image: "nginx:1.24"
```

**Advanced patterns:**
```yaml
# Use Chart.AppVersion as fallback
image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"

# Support image digest
{{- if .Values.image.digest }}
image: "{{ .Values.image.repository }}@{{ .Values.image.digest }}"
{{- else }}
image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
{{- end }}
```

#### ports

**What it is:** Ports exposed by the container

```yaml
ports:
  - containerPort: 80
    protocol: TCP
```

**Not the same as Service port:**
- `containerPort: 80` - Port app listens on inside container
- `service.port: 80` - Port Service exposes
- `service.targetPort: 80` - Port Service forwards to (usually = containerPort)

#### livenessProbe

**Purpose:** Detect if container is deadlocked or unhealthy → restart it

```yaml
livenessProbe:
  httpGet:
    path: {{ .Values.healthcheck.path }}
    port: {{ .Values.healthcheck.port }}
  initialDelaySeconds: 5  # Wait 5s after container starts
  periodSeconds: 10        # Check every 10s
```

**Probe types:**

| Type | Use Case | Example |
|------|----------|---------|
| `httpGet` | HTTP endpoint | `GET /health → 200 OK` |
| `tcpSocket` | TCP port open | Port 3306 accepts connections |
| `exec` | Run command | `pg_isready` script |

**Liveness probe parameters:**
- `initialDelaySeconds: 5` - Wait before first probe
- `periodSeconds: 10` - Probe every 10 seconds
- `timeoutSeconds: 1` - Probe timeout (default)
- `successThreshold: 1` - Success after 1 probe (default)
- `failureThreshold: 3` - Restart after 3 failures (default)

**Probe behavior:**
```
Container starts
↓
Wait 5s (initialDelaySeconds)
↓
Probe every 10s (periodSeconds)
↓
If 3 consecutive failures (failureThreshold)
↓
Restart container
```

#### readinessProbe

**Purpose:** Detect if container is ready to serve traffic → add/remove from Service endpoints

```yaml
readinessProbe:
  httpGet:
    path: {{ .Values.healthcheck.path }}
    port: {{ .Values.healthcheck.port }}
  initialDelaySeconds: 3  # Shorter than liveness
  periodSeconds: 5         # Check more frequently
```

**Liveness vs Readiness:**

| Aspect | Liveness | Readiness |
|--------|----------|-----------|
| **Purpose** | Is container alive? | Is container ready? |
| **Failure action** | Restart container | Remove from Service |
| **Use case** | Detect deadlock | Detect temporary unavailability |
| **Frequency** | Less frequent | More frequent |

**Example scenario:**
```
App starts
↓
Readiness probe fails (app loading)
↓
Pod not added to Service (no traffic)
↓
App finishes loading
↓
Readiness probe succeeds
↓
Pod added to Service (receives traffic)
↓
App deadlocks
↓
Liveness probe fails 3 times
↓
Container restarts
```

**Best practices:**
```yaml
# Separate endpoints for different concerns
livenessProbe:
  httpGet:
    path: /healthz  # Simple alive check
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready    # Check dependencies (DB, cache)
  periodSeconds: 5
```

#### resources: {{- toYaml .Values.resources | nindent 12 }}

**Template function breakdown:**

| Function | Purpose |
|----------|---------|
| `toYaml` | Convert Go object to YAML |
| `nindent 12` | Indent 12 spaces and add newline |
| `{{-` | Trim whitespace before |
| `-}}` | Trim whitespace after |

**How it works:**
```yaml
# values.yaml
resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 50m
    memory: 64Mi

# Renders to (indented 12 spaces):
          resources:
            limits:
              cpu: 100m
              memory: 128Mi
            requests:
              cpu: 50m
              memory: 64Mi
```

**Why use toYaml:**
- Preserves nested structure
- No need to template each field individually
- Easier to maintain

---

## templates/service.yaml - Network Exposure

### Full File

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}
  labels:
    app: {{ .Release.Name }}
    chart: {{ .Chart.Name }}-{{ .Chart.Version }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: 80
      protocol: TCP
  selector:
    app: {{ .Release.Name }}
```

### Service Basics

**What a Service does:**
- Provides stable DNS name for pods
- Load balances traffic across multiple pods
- Survives pod restarts (pods get new IPs, Service IP stable)

**DNS resolution:**
```bash
# Inside cluster
curl http://my-app:80
# Resolves to: my-app.namespace.svc.cluster.local
```

### type: {{ .Values.service.type }}

**Rendered values:**
```yaml
# values.yaml (default)
service:
  type: ClusterIP
# Renders to: type: ClusterIP

# Override to NodePort
--set service.type=NodePort
# Renders to: type: NodePort
```

### ports

**Port configuration:**
```yaml
ports:
  - port: {{ .Values.service.port }}  # Service port (external)
    targetPort: 80                     # Container port (internal)
    protocol: TCP
```

**Port flow:**
```
Client connects to:
  http://my-app:80
    ↓
Service port: 80
    ↓
Forwards to targetPort: 80
    ↓
Container port: 80
    ↓
Application receives request
```

**Example with different ports:**
```yaml
# values.yaml
service:
  port: 8080  # Service listens on 8080

# templates/service.yaml
ports:
  - port: {{ .Values.service.port }}  # 8080
    targetPort: 80                     # Container still on 80

# Usage:
curl http://my-app:8080  # Connect to Service on 8080
# Service forwards to container port 80
```

### selector

**Purpose:** Identifies which pods receive traffic from this Service

```yaml
selector:
  app: {{ .Release.Name }}
```

**Must match:** Pod labels from Deployment template

**Example:**
```yaml
# Service selector
selector:
  app: my-app

# Selects pods with this label:
# Deployment
spec:
  template:
    metadata:
      labels:
        app: my-app  # ← Matches selector
```

**How it works:**
```
Service created with selector: app=my-app
↓
Kubernetes finds all pods with label app=my-app
↓
Service endpoints = list of pod IPs
↓
Traffic load-balanced across all matching pods
```

---

## templates/tests/test-connection.yaml - Automated Testing

### Full File

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ .Release.Name }}-test-connection"
  labels:
    app: {{ .Release.Name }}
  annotations:
    "helm.sh/hook": test
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  containers:
    - name: wget
      image: busybox:1.36
      command: ['wget']
      args: ['{{ .Release.Name }}:{{ .Values.service.port }}', '-O', '/dev/null', '--timeout=5']
  restartPolicy: Never
```

### Helm Test Hooks

**What is helm test:**
- Runs pods annotated with `helm.sh/hook: test`
- Validates deployment after `helm install` or `helm upgrade`
- Part of CI/CD pipeline: if test fails, rollback

**Workflow:**
```bash
# Deploy
helm install my-app ./pipeline-app

# Run test
helm test my-app
# Creates test pod, checks exit code
# Exit 0 = success, non-zero = failure

# View test results
kubectl logs my-app-test-connection
```

### annotations

#### "helm.sh/hook": test

**What it does:**
- Marks this pod as a test hook
- Not deployed during `helm install`
- Only created when running `helm test`

**Other hook types:**
- `pre-install` - Before install
- `post-install` - After install
- `pre-upgrade` - Before upgrade
- `post-upgrade` - After upgrade
- `pre-delete` - Before delete
- `test` - During helm test

#### "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded

**What it does:** Controls when test pods are deleted

**Policies:**

| Policy | Delete When |
|--------|-------------|
| `before-hook-creation` | Before creating new test pod |
| `hook-succeeded` | After successful test |
| `hook-failed` | After failed test |

**Our config:** `before-hook-creation,hook-succeeded`
- Delete old test pod before creating new one
- Delete test pod after success
- Keep test pod after failure (for debugging)

**Behavior:**
```bash
# First test
helm test my-app
# Creates pod, test succeeds, pod deleted

# Second test
helm test my-app
# Deletes old pod (before-hook-creation), creates new pod

# Test fails
helm test my-app
# Creates pod, test fails, pod NOT deleted (can debug)
kubectl logs my-app-test-connection  # View failure logs
```

### Test Pod Spec

#### image: busybox:1.36

**Why busybox:**
- Tiny image (~5 MB)
- Contains basic utilities (wget, curl, nc, sh)
- Fast download and startup
- Standard for Kubernetes testing

#### command: ['wget']

**Test logic:**
```yaml
command: ['wget']
args:
  - '{{ .Release.Name }}:{{ .Values.service.port }}'  # URL to test
  - '-O'               # Output to file
  - '/dev/null'        # Discard output (we just want exit code)
  - '--timeout=5'      # Fail if no response in 5s
```

**Rendered example:**
```bash
helm install my-app ./pipeline-app
# Renders to:
wget my-app:80 -O /dev/null --timeout=5
```

**What it tests:**
1. Service DNS resolves (`my-app`)
2. Service is reachable on specified port (`:80`)
3. HTTP request succeeds (exit code 0)
4. Response received within 5 seconds

**Exit codes:**
- `0` - Success (helm test passes)
- Non-zero - Failure (helm test fails)

#### restartPolicy: Never

**Why Never:**
- Test runs once and exits
- Don't retry failed tests automatically
- Clear pass/fail signal

**Options:**
- `Never` - Run once, exit
- `OnFailure` - Retry on failure
- `Always` - Restart continuously (not for tests)

### Advanced Test Examples

**Test with multiple checks:**
```yaml
# templates/tests/test-full.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ .Release.Name }}-test-full"
  annotations:
    "helm.sh/hook": test
spec:
  containers:
    - name: test
      image: curlimages/curl:latest
      command: ['sh', '-c']
      args:
        - |
          echo "Testing health endpoint..."
          curl -f http://{{ .Release.Name }}/health || exit 1

          echo "Testing API endpoint..."
          curl -f http://{{ .Release.Name }}/api/status || exit 1

          echo "All tests passed!"
  restartPolicy: Never
```

**Test with database connectivity:**
```yaml
# templates/tests/test-db.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ .Release.Name }}-test-db"
  annotations:
    "helm.sh/hook": test
spec:
  containers:
    - name: test
      image: postgres:15
      command: ['psql']
      args:
        - '-h'
        - '{{ .Release.Name }}-postgresql'
        - '-U'
        - 'appuser'
        - '-c'
        - 'SELECT 1'
      env:
        - name: PGPASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ .Release.Name }}-postgresql
              key: password
  restartPolicy: Never
```

---

## Production Pipeline Stages

### Complete CI/CD Pipeline

```yaml
# .gitlab-ci.yml or .github/workflows/deploy.yml
stages:
  - validate
  - test-render
  - deploy-staging
  - test-staging
  - deploy-production
  - test-production
```

### Stage 1: Validation (CI)

**Purpose:** Catch errors before deployment

```bash
# Lint chart
helm lint ./chart

# Lint with all values files
helm lint ./chart -f values-staging.yaml
helm lint ./chart -f values-prod.yaml

# Check for common issues
helm lint ./chart --strict  # Treat warnings as errors
```

**What helm lint checks:**
- Chart.yaml required fields
- Template syntax errors
- Missing required values
- YAML syntax errors
- File structure issues

**Example output:**
```
==> Linting ./chart
[INFO] Chart.yaml: icon is recommended
[ERROR] templates/deployment.yaml: unable to parse YAML: error converting YAML to JSON
Error: 1 chart(s) linted, 1 chart(s) failed
```

### Stage 2: Template Rendering (CI)

**Purpose:** Preview exact YAML that will be applied

```bash
# Render templates
helm template my-app ./chart -f values-staging.yaml

# Render and validate against K8s schema
helm template my-app ./chart -f values-staging.yaml | kubeval --strict

# Check resource counts
helm template my-app ./chart -f values-staging.yaml | grep -c '^kind:'
```

**What to check:**
- All expected resources present
- Image tags correct
- Resource limits appropriate
- No secrets in plain text

**Advanced validation:**
```bash
# Validate with kubeconform (faster than kubeval)
helm template my-app ./chart | kubeconform -strict -summary

# Policy validation with OPA
helm template my-app ./chart | conftest test -p policy/ -

# Security scanning
helm template my-app ./chart | trivy config -
```

### Stage 3: Preview Changes (CI)

**Purpose:** Show diff before applying changes

```bash
# Install helm-diff plugin
helm plugin install https://github.com/databus23/helm-diff

# Preview changes
helm diff upgrade my-app ./chart -f values-prod.yaml

# Show only new resources
helm diff upgrade my-app ./chart -f values-prod.yaml --show-secrets=false
```

**Example output:**
```diff
default, my-app, Deployment (apps) has changed:
  spec:
    replicas:
-     1
+     3
    template:
      spec:
        containers:
          - resources:
              limits:
                cpu:
-                 50m
+                 200m
```

### Stage 4: Deploy Staging (CD)

**Purpose:** Deploy to staging environment first

```bash
# Deploy with atomic flag (auto-rollback on failure)
helm upgrade my-app ./chart \
  --install \
  -f values-staging.yaml \
  --namespace staging \
  --create-namespace \
  --atomic \
  --timeout 5m \
  --wait
```

**Flag explanations:**

| Flag | Purpose | Impact |
|------|---------|--------|
| `--install` | Install if not exists | Creates release if first time |
| `--atomic` | Auto-rollback on failure | Combines --wait + rollback |
| `--timeout 5m` | Max wait time | Fail if not ready in 5 min |
| `--wait` | Wait for ready | Don't return until pods ready |
| `--create-namespace` | Create namespace | Creates namespace if missing |

### Stage 5: Test Staging (CD)

**Purpose:** Validate staging deployment

```bash
# Run Helm tests
helm test my-app --namespace staging

# Application-specific tests
kubectl run test-staging --rm -it --image=curlimages/curl -- \
  curl -f http://my-app.staging:80/health

# Load tests
kubectl run load-test --rm -it --image=busybox -- \
  sh -c 'for i in $(seq 1 100); do wget -q -O- http://my-app.staging:80; done'
```

**What to test:**
- Health endpoints respond
- API endpoints functional
- Database connectivity
- External service integration
- Performance within acceptable range

### Stage 6: Deploy Production (CD)

**Purpose:** Promote to production after staging validation

```bash
# Deploy to production with atomic flag
helm upgrade my-app ./chart \
  --install \
  -f values-prod.yaml \
  --namespace production \
  --create-namespace \
  --atomic \
  --timeout 10m \
  --wait \
  --max-history 10 \
  --description "Deploy $(git rev-parse --short HEAD)"
```

**Production-specific flags:**

| Flag | Purpose |
|------|---------|
| `--timeout 10m` | Longer timeout for production (more replicas) |
| `--max-history 10` | Limit stored revisions (prevent etcd bloat) |
| `--description` | Add deployment notes (git commit, ticket number) |

**Blue-Green deployment:**
```bash
# Deploy "green" alongside "blue"
helm upgrade my-app-green ./chart \
  -f values-prod.yaml \
  --namespace production \
  --atomic

# Smoke test green
helm test my-app-green

# Switch traffic (update Ingress or Service)
kubectl patch ingress my-app -p '{"spec":{"rules":[{"host":"app.example.com","http":{"paths":[{"backend":{"service":{"name":"my-app-green"}}}]}}]}}'

# Monitor, then delete blue
helm uninstall my-app-blue
```

### Stage 7: Test Production (CD)

**Purpose:** Validate production deployment

```bash
# Run Helm tests
helm test my-app --namespace production

# Smoke tests
curl -f https://app.example.com/health

# Monitor metrics
kubectl top pods -n production -l app=my-app

# Check logs for errors
kubectl logs -n production -l app=my-app --tail=100 | grep -i error
```

---

## Helm Safety Flags

### Critical Production Flags

#### --atomic

**What it does:** Combines `--wait` + auto-rollback on failure

**Syntax:**
```bash
helm upgrade my-app ./chart --atomic --timeout 5m
```

**Behavior:**
```
1. Apply changes
2. Wait for all resources to be ready
3. If ready within timeout: Success
4. If not ready: Automatic rollback to previous release
5. Exit code: 0 (success) or 1 (failed + rolled back)
```

**Why critical:**
- Prevents leaving cluster in broken state
- No manual intervention needed
- CI/CD can rely on exit code

**Example failure:**
```bash
helm upgrade my-app ./chart --atomic --timeout 1m \
  --set image.tag=99.99.99-nonexistent

# Output:
# Release "my-app" failed, and has been rolled back due to atomic being set.
# Error: timed out waiting for the condition
```

#### --wait

**What it does:** Wait for all resources to be ready before returning

**Syntax:**
```bash
helm upgrade my-app ./chart --wait --timeout 5m
```

**What "ready" means:**

| Resource | Ready Condition |
|----------|-----------------|
| Deployment | All replicas running and ready |
| StatefulSet | All replicas running and ready |
| DaemonSet | Desired number running on each node |
| Job | Successfully completed |
| PVC | Bound to PV |

**Without --wait:**
```bash
helm upgrade my-app ./chart
# Returns immediately (does not wait)
# Pods might still be starting or crashing
```

**With --wait:**
```bash
helm upgrade my-app ./chart --wait --timeout 5m
# Waits up to 5 minutes for all pods to be ready
# Returns only when deployment is complete
```

#### --timeout

**What it does:** Maximum time to wait (with --wait or --atomic)

**Syntax:**
```bash
helm upgrade my-app ./chart --atomic --timeout 10m
```

**Choosing timeout values:**

| Scenario | Timeout | Reasoning |
|----------|---------|-----------|
| Small app (1-3 pods) | 2-5m | Fast startup |
| Large app (10+ pods) | 5-10m | Sequential rolling update |
| StatefulSets | 10-30m | Sequential pod creation |
| With init containers | 5-15m | Depends on init duration |

**Calculation formula:**
```
Timeout >= (maxReplicas × podStartupTime) + (initContainerTime) + buffer

Example:
- 10 replicas
- 30s per pod startup
- 2min init container
- Total: (10 × 30s) + 2min + 1min buffer = 8min
```

#### --cleanup-on-fail

**What it does:** Remove newly created resources if upgrade fails

**Syntax:**
```bash
helm upgrade my-app ./chart --atomic --cleanup-on-fail
```

**What gets cleaned up:**
- New resources created in this upgrade
- Does NOT remove existing resources from prior release

**Use case:**
```bash
# Upgrade adds a new ConfigMap and updates Deployment
helm upgrade my-app ./chart --atomic --cleanup-on-fail

# Upgrade fails
# Result:
# - New ConfigMap deleted (cleanup-on-fail)
# - Deployment rolled back to previous version (atomic)
# - Old ConfigMap preserved
```

#### --max-history

**What it does:** Limit stored release revisions (prevent etcd bloat)

**Syntax:**
```bash
helm upgrade my-app ./chart --max-history 10
```

**Why limit history:**
- Each revision stored in Kubernetes Secret
- Too many revisions → large Secrets → etcd performance issues
- Old revisions rarely needed

**Recommended values:**

| Use Case | --max-history | Reasoning |
|----------|---------------|-----------|
| Development | 3 | Minimal history needed |
| Staging | 5 | Some rollback capacity |
| Production | 10 | Balance history vs storage |
| High-frequency deploys | 15-20 | Need more rollback options |

**Check revision count:**
```bash
helm history my-app -n production
# Shows all stored revisions
```

---

## Troubleshooting Production Issues

### Upgrade Stuck or Timing Out

**Symptom:**
```bash
helm upgrade my-app ./chart --atomic --timeout 5m
# Hangs for 5 minutes, then:
# Error: timed out waiting for the condition
```

**Debug steps:**

1. **Check pod status:**
```bash
kubectl get pods -n production -l app=my-app
# Look for: ImagePullBackOff, CrashLoopBackOff, Pending
```

2. **Check pod events:**
```bash
kubectl describe pod <pod-name> -n production
# Look for: Failed to pull image, Insufficient resources, Unschedulable
```

3. **Check logs:**
```bash
kubectl logs <pod-name> -n production
kubectl logs <pod-name> -n production --previous  # Previous crash
```

4. **Check readiness probes:**
```bash
kubectl get pod <pod-name> -n production -o jsonpath='{.status.containerStatuses[0].ready}'
# false = readiness probe failing
```

**Common causes:**

| Issue | Symptom | Fix |
|-------|---------|-----|
| Wrong image tag | ImagePullBackOff | Verify image.tag value |
| Insufficient resources | Pending | Increase cluster capacity or reduce requests |
| Failing readiness probe | 0/1 Ready | Fix app or adjust probe timing |
| Init container fails | Init:Error | Check init container logs |

### Rollback Failed Upgrade

**Manual rollback:**
```bash
# View release history
helm history my-app -n production

# Rollback to specific revision
helm rollback my-app 5 -n production --wait

# Rollback to previous revision
helm rollback my-app -n production --wait
```

**Verify rollback:**
```bash
# Check current revision
helm list -n production

# Check pod image
kubectl get deployment my-app -n production -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### Release in Failed State

**Symptom:**
```bash
helm list -n production
# STATUS: failed
```

**Options:**

1. **Rollback to last good revision:**
```bash
helm rollback my-app -n production
```

2. **Force upgrade (dangerous):**
```bash
helm upgrade my-app ./chart --force --atomic
# --force recreates resources (downtime!)
```

3. **Uninstall and reinstall (last resort):**
```bash
helm uninstall my-app -n production
helm install my-app ./chart -f values-prod.yaml -n production
# ⚠️ Causes downtime and data loss!
```

### Helm Test Failures

**Symptom:**
```bash
helm test my-app -n production
# NAME: my-app
# LAST DEPLOYED: ...
# NAMESPACE: production
# STATUS: deployed
# REVISION: 5
# TEST SUITE:     my-app-test-connection
# Last Started:   ...
# Last Completed: ...
# Phase:          Failed
```

**Debug test failure:**
```bash
# Get test pod logs
kubectl logs my-app-test-connection -n production

# Check if Service exists
kubectl get svc my-app -n production

# Check Service endpoints
kubectl get endpoints my-app -n production

# Test Service connectivity manually
kubectl run test --rm -it --image=busybox -- \
  wget -O- my-app:80 --timeout=5
```

### Unexpected Values Applied

**Symptom:** Wrong values rendered in deployment

**Debug:**
```bash
# Check merged values
helm get values my-app -n production

# Check ALL values (including defaults)
helm get values my-app -n production --all

# Preview what would be deployed
helm template my-app ./chart -f values-prod.yaml | less
```

**Common causes:**
- Wrong values file specified
- --set flag overriding values file
- Typo in values file key
- Wrong template logic (if/else conditions)

---

## Best Practices

### Chart Development

**1. Use specific versions:**
```yaml
# Chart.yaml
version: 1.0.0              # Not 1.0
appVersion: "1.24.0"        # Not "1.24" or "latest"
```

**2. Provide defaults for all values:**
```yaml
# values.yaml - Complete defaults
replicaCount: 2             # Not left empty
image:
  repository: nginx
  tag: "1.24"               # Not ""
  pullPolicy: IfNotPresent  # Not missing
```

**3. Use helpers for repeated logic:**
```yaml
# templates/_helpers.tpl
{{- define "app.labels" -}}
app: {{ .Release.Name }}
chart: {{ .Chart.Name }}-{{ .Chart.Version }}
release: {{ .Release.Name }}
{{- end -}}

# templates/deployment.yaml
labels:
  {{- include "app.labels" . | nindent 4 }}
```

**4. Document all values:**
```yaml
# values.yaml
# Number of pod replicas
# For production, use 3+ for high availability
replicaCount: 2

# Container image configuration
image:
  # Image repository (without tag)
  repository: nginx
  # Image tag (use specific versions in production)
  tag: "1.24"
```

### Pipeline Configuration

**1. Separate staging and production:**
```yaml
# .github/workflows/deploy.yml
jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: |
          helm upgrade my-app ./chart \
            -f values-staging.yaml \
            --namespace staging \
            --atomic --timeout 5m

  deploy-production:
    needs: deploy-staging  # Only after staging succeeds
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          helm upgrade my-app ./chart \
            -f values-prod.yaml \
            --namespace production \
            --atomic --timeout 10m
```

**2. Always use --atomic in CI/CD:**
```bash
# CI/CD pipeline command
helm upgrade my-app ./chart \
  --atomic \
  --timeout 10m \
  --wait

# Never in CI/CD:
helm upgrade my-app ./chart  # ❌ No safety flags
```

**3. Add deployment metadata:**
```bash
helm upgrade my-app ./chart \
  --set metadata.gitCommit=$(git rev-parse HEAD) \
  --set metadata.buildNumber=${CI_BUILD_NUMBER} \
  --description "Deploy ${CI_BUILD_NUMBER} - $(git log -1 --oneline)"
```

**4. Run helm test in pipeline:**
```yaml
# After deployment
- name: Run Helm tests
  run: helm test my-app --namespace production --timeout 5m
```

### Security Practices

**1. Never commit secrets:**
```yaml
# ❌ Bad - values-prod.yaml
database:
  password: "supersecret123"

# ✅ Good - values-prod.yaml
database:
  existingSecret: "db-credentials"
  existingSecretKey: "password"
```

**2. Use image digests for immutability:**
```yaml
# values-prod.yaml
image:
  repository: nginx
  digest: "sha256:ab5c..." # Immutable reference
```

**3. Scan charts for security issues:**
```bash
# Scan rendered manifests
helm template my-app ./chart | trivy config -

# Scan images
trivy image nginx:1.24
```

**4. Use minimal permissions:**
```yaml
# templates/deployment.yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
```

### Monitoring and Observability

**1. Add release labels to resources:**
```yaml
# templates/deployment.yaml
metadata:
  labels:
    app.kubernetes.io/managed-by: {{ .Release.Service }}  # "Helm"
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/version: {{ .Chart.AppVersion }}
    helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
```

**2. Export deployment metrics:**
```yaml
# Add annotations for Prometheus
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9090"
```

**3. Set up alerts:**
```yaml
# Prometheus alert
- alert: HelmDeploymentFailed
  expr: |
    kube_deployment_status_replicas_available{namespace="production"}
    < kube_deployment_spec_replicas{namespace="production"}
  for: 5m
```

### Release Management

**1. Use semantic versioning:**
```yaml
# Breaking change
version: 2.0.0  # MAJOR bump

# New feature
version: 1.1.0  # MINOR bump

# Bug fix
version: 1.0.1  # PATCH bump
```

**2. Tag releases in Git:**
```bash
git tag v1.0.0
git push origin v1.0.0
```

**3. Document changes:**
```markdown
# CHANGELOG.md

## [1.1.0] - 2024-01-15
### Added
- Health check probes
- Resource limits
- Helm test for connectivity

### Changed
- Increased default replicas from 1 to 2

### Fixed
- Service selector mismatch
```

**4. Maintain upgrade path:**
```bash
# Test upgrade from previous version
helm install my-app ./chart-v1.0.0
helm upgrade my-app ./chart-v1.1.0
# Ensure no errors
```

---

## Further Reading

### Official Documentation
- **Helm Official Docs**: https://helm.sh/docs/
- **Helm Best Practices**: https://helm.sh/docs/chart_best_practices/
- **Helm Release Lifecycle**: https://helm.sh/docs/topics/charts_hooks/
- **Kubernetes Deployment Strategies**: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/

### Tools and Plugins
- **helm-diff**: https://github.com/databus23/helm-diff
- **kubeval**: https://github.com/instrumenta/kubeval
- **kubeconform**: https://github.com/yannh/kubeconform
- **trivy**: https://github.com/aquasecurity/trivy

### Advanced Topics
- **ArgoCD with Helm**: https://argo-cd.readthedocs.io/en/stable/user-guide/helm/
- **Flux with Helm**: https://fluxcd.io/docs/guides/helmreleases/
- **Helmfile**: https://github.com/helmfile/helmfile
- **Chart Testing**: https://github.com/helm/chart-testing

---

*This comprehensive guide covers everything needed to build production-grade Helm deployment pipelines. Master these concepts to deploy safely, reliably, and confidently to Kubernetes production environments.*
