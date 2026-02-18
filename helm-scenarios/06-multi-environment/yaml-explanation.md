# Helm Multi-Environment Deployment - Complete YAML Explanation

This comprehensive guide explains every aspect of deploying the same Helm chart to multiple environments (dev, staging, production) using values file layering - the most critical pattern in production Helm workflows.

---

## 🎯 What is Multi-Environment Deployment?

**Multi-environment deployment** is the practice of running the same application code with different configurations across multiple environments (development, staging, production) using a single Helm chart.

### Why This Pattern is Essential:

- **Consistency**: Same chart = same deployment logic across all environments
- **Reduces drift**: No manual environment-specific manifests to maintain
- **Promotes testing**: Test the exact same chart that runs in production
- **Simplifies CI/CD**: One chart, multiple values files in your pipeline
- **Environment parity**: Ensures dev/staging mirror production structure

### The Core Principle:

```
One Chart + Multiple Values Files = Multiple Environments
```

Instead of maintaining separate YAML manifests for dev, staging, and prod, you maintain:
- 1 chart with templates
- 1 base values.yaml (defaults)
- N environment-specific values files (overrides)

---

## 📊 Environment Configuration Strategy

This scenario demonstrates the typical progression from dev to production:

| Configuration | Development | Staging | Production |
|---------------|-------------|---------|------------|
| **Purpose** | Rapid iteration | Pre-prod testing | Live traffic |
| **Replicas** | 1 | 2 | 3 |
| **Logging** | debug (verbose) | warn (important) | info (balanced) |
| **Debug Mode** | Enabled | Disabled | Disabled |
| **Resources** | None (free-for-all) | Moderate limits | Strict limits |
| **Anti-Affinity** | No (single node ok) | No (cost savings) | Yes (HA required) |
| **Feature Flags** | All enabled | Partial | Production-ready only |
| **DB Connections** | 5 (minimal) | 20 (moderate) | 50 (high throughput) |

### The Philosophy:

- **Dev**: Maximum flexibility, minimum restrictions
- **Staging**: Mirror prod structure but cheaper
- **Production**: Strict limits, HA, optimized for reliability

---

## 📄 Chart.yaml - Chart Metadata

```yaml
apiVersion: v2
name: multi-env-app
description: A Helm chart demonstrating multi-environment deployment with different values files
type: application
version: 0.1.0
appVersion: "1.0.0"
```

### Field Breakdown:

#### apiVersion: v2

**What it is:** Helm chart API version

**Values:**
- `v1` - Helm 2 (deprecated)
- `v2` - Helm 3+ (current, use this)

**Why v2?**
- Supports dependencies in Chart.yaml
- Better metadata validation
- Required for modern Helm features

#### name: multi-env-app

**What it is:** Chart name used in templates

**Where it's used:**
```go
{{ .Chart.Name }}  // "multi-env-app"
```

**Naming conventions:**
- Lowercase letters, numbers, hyphens only
- No underscores or special characters
- Should match directory name

#### description

**What it is:** Human-readable chart description

**Best practices:**
- Concise (1-2 sentences)
- Describe what the chart does
- Mention key features

#### type: application

**What it is:** Chart type classification

**Options:**
- `application` - Deploys an application (most common)
- `library` - Reusable templates for other charts (no deployable resources)

**When to use library charts:**
```yaml
# Common pattern: shared helpers across company charts
type: library
```

#### version: 0.1.0

**What it is:** Chart version (SemVer)

**Semantic versioning:**
- `MAJOR.MINOR.PATCH`
- `0.1.0` = Initial development
- `1.0.0` = First stable release
- `1.1.0` = New feature (minor bump)
- `1.1.1` = Bug fix (patch bump)
- `2.0.0` = Breaking change (major bump)

**Critical rule:**
- **Chart version != App version**
- Change chart version when templates/values change
- Change appVersion when application code changes

#### appVersion: "1.0.0"

**What it is:** Version of the application being deployed

**Usage in templates:**
```yaml
image: myapp:{{ .Chart.AppVersion }}
```

**Best practice:** Quote the version
```yaml
appVersion: "1.0.0"  # Good - prevents YAML parsing issues
appVersion: 1.0.0    # Bad - may be parsed as float
```

---

## 📄 values.yaml - Base Defaults

```yaml
# Default values for multi-env-app
# These serve as the base that environment-specific files override

replicaCount: 1

image:
  repository: nginx
  tag: "1.24"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

# Application configuration
config:
  environment: "default"
  logLevel: "info"
  debugMode: false
  featureFlags:
    enableMetrics: true
    enableTracing: false
    enableProfiling: false
  database:
    host: "localhost"
    port: 5432
    name: "appdb"
    maxConnections: 10

# Resource limits (empty by default - no limits)
resources: {}

# Pod anti-affinity (disabled by default)
antiAffinity:
  enabled: false

# Node selector (empty by default)
nodeSelector: {}

# Tolerations (empty by default)
tolerations: []
```

### Base Values Philosophy:

**Purpose of values.yaml:**
1. **Sensible defaults** - Values that work in most environments
2. **Documentation** - Shows all available configuration options
3. **Baseline** - Starting point for environment overrides
4. **Safety** - Conservative settings that won't cause harm

**Why these defaults?**
- `replicaCount: 1` - Minimal viable deployment
- `resources: {}` - No limits (flexible, but risky)
- `antiAffinity.enabled: false` - Cost savings (but less HA)
- `config.environment: "default"` - Clear indication no environment specified

### Field-by-Field Explanation:

#### replicaCount: 1

**What it controls:** Number of pod replicas in Deployment

**Default reasoning:**
- Minimal resource usage
- Suitable for local development
- Overridden by all environments

**Template usage:**
```yaml
# templates/deployment.yaml
spec:
  replicas: {{ .Values.replicaCount }}
```

#### image

```yaml
image:
  repository: nginx
  tag: "1.24"
  pullPolicy: IfNotPresent
```

**repository: nginx**
- Docker image without tag
- Defaults to Docker Hub
- Production would use: `myregistry.io/myorg/myapp`

**tag: "1.24"**
- Specific image version (good practice)
- Never use `latest` in production
- Quoted to prevent YAML parsing as float

**pullPolicy: IfNotPresent**

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `IfNotPresent` | Pull if not cached | Default (efficient) |
| `Always` | Pull every pod start | Latest development images |
| `Never` | Only use cached | Air-gapped environments |

#### service

```yaml
service:
  type: ClusterIP
  port: 80
```

**type: ClusterIP**
- Internal-only access
- Safe default (no external exposure)
- Environments can override to NodePort/LoadBalancer

**port: 80**
- Service port for internal cluster communication
- Other pods use: `http://multi-env-app:80`

#### config

This is where the magic happens - all environment-specific application configuration.

##### config.environment: "default"

**What it does:** Identifies which environment is running

**How to use in app:**
```javascript
// Application reads from environment variable
const env = process.env.APP_ENVIRONMENT;
if (env === 'production') {
  // Disable debug features
}
```

**Template usage:**
```yaml
# Creates label: app.kubernetes.io/environment: production
app.kubernetes.io/environment: {{ .Values.config.environment }}
```

##### config.logLevel: "info"

**What it controls:** Application logging verbosity

**Standard levels:**
```
debug → info → warn → error → fatal
 ↑                              ↑
Most verbose             Least verbose
```

**Per environment:**
- **Dev**: `debug` - See everything
- **Staging**: `warn` - Important events only
- **Prod**: `info` - Balanced visibility

**Why not debug in prod?**
- Performance overhead (excessive I/O)
- Log storage costs
- Potential info leakage

##### config.debugMode: false

**What it enables:** Debug features in the application

**Typical debug features:**
- Detailed stack traces
- Request/response logging
- Performance profiling
- Test endpoints enabled

**Security warning:**
```yaml
debugMode: true   # ⚠️ NEVER in production!
# Risks: info disclosure, performance degradation, security bypass
```

##### config.featureFlags

```yaml
featureFlags:
  enableMetrics: true
  enableTracing: false
  enableProfiling: false
```

**What it is:** Runtime feature toggles

**enableMetrics: true**
- Prometheus metrics endpoint
- Safe to enable everywhere
- Essential for production monitoring

**enableTracing: false**
- Distributed tracing (Jaeger, Zipkin)
- High overhead in production
- Useful in staging for debugging

**enableProfiling: false**
- CPU/memory profiling endpoints
- **NEVER in production** - performance impact
- Good for dev performance analysis

##### config.database

```yaml
database:
  host: "localhost"
  port: 5432
  name: "appdb"
  maxConnections: 10
```

**Why in values?**
- Different database per environment
- Different connection pools per environment
- Easy to override without code changes

**host patterns:**
- Dev: `postgres-dev.database.svc.cluster.local`
- Staging: `postgres-staging.database.svc.cluster.local`
- Prod: `postgres-prod.database.svc.cluster.local`

**maxConnections strategy:**
- Dev: 5 (low concurrency)
- Staging: 20 (moderate testing)
- Prod: 50 (high traffic)

#### resources: {}

**What it means:** No resource limits or requests

**Why empty by default?**
- Flexibility for different environments
- Avoids one-size-fits-all limits
- Each environment sets appropriate values

**The risk:**
```yaml
resources: {}  # Pod can consume unlimited CPU/memory
# Can starve other pods, crash nodes
```

**Template handling:**
```yaml
{{- if .Values.resources }}
resources:
  {{- toYaml .Values.resources | nindent 12 }}
{{- end }}
```

#### antiAffinity

```yaml
antiAffinity:
  enabled: false
```

**What it is:** Control for pod anti-affinity rules

**When enabled:** Spreads pods across nodes for HA

**Why disabled by default?**
- Requires multi-node cluster
- Development often runs on single node
- Cost savings in staging

**Production override:**
```yaml
antiAffinity:
  enabled: true  # Ensures HA by spreading replicas
```

---

## 📄 values-dev.yaml - Development Overrides

```yaml
# Development environment overrides
# Minimal resources, verbose logging, debug enabled

replicaCount: 1

config:
  environment: "development"
  logLevel: "debug"
  debugMode: true
  featureFlags:
    enableMetrics: true
    enableTracing: true
    enableProfiling: true
  database:
    host: "postgres-dev.database.svc.cluster.local"
    port: 5432
    name: "appdb_dev"
    maxConnections: 5

# No resource limits in dev - let developers iterate freely
resources: {}

antiAffinity:
  enabled: false
```

### Development Philosophy:

**Goals:**
- 🚀 Fast iteration
- 🔍 Maximum visibility
- 💻 Developer-friendly
- 💰 Minimal resource usage

### Key Overrides Explained:

#### replicaCount: 1

**Why only 1?**
- Faster deployment cycles
- Easier debugging (fewer logs to correlate)
- Saves resources on laptop/dev cluster
- No HA needed in dev

#### logLevel: "debug"

**What you see:**
```
[DEBUG] Database query: SELECT * FROM users WHERE id=1
[DEBUG] Request headers: {...}
[DEBUG] Response time: 45ms
[INFO] User authenticated successfully
[WARN] Slow query detected
```

**Usefulness:**
- See exact SQL queries
- View all HTTP requests/responses
- Track timing of operations
- Debug race conditions

#### debugMode: true

**Enables:**
- `/debug/pprof` endpoints (Go profiling)
- Detailed error messages with stack traces
- Request/response logging
- Hot reload of configuration
- Test data seeding endpoints

**Example:**
```bash
# Access debug endpoints
curl http://app-dev:8080/debug/pprof/heap
curl http://app-dev:8080/debug/seed-test-data
```

#### featureFlags - All Enabled

```yaml
enableMetrics: true     # Prometheus metrics
enableTracing: true     # Distributed tracing
enableProfiling: true   # CPU/memory profiling
```

**Why enable everything?**
- Developers need to test these features
- Find performance issues early
- Validate instrumentation code
- No cost concerns in dev

#### database

```yaml
host: "postgres-dev.database.svc.cluster.local"
name: "appdb_dev"
maxConnections: 5
```

**Key points:**
- Separate dev database (avoid prod data access)
- Low connection pool (1 developer at a time)
- Test data, not real customer data
- Can reset/seed data freely

**Kubernetes DNS:**
```
postgres-dev.database.svc.cluster.local
    ↑         ↑       ↑      ↑
  service  namespace svc  cluster
```

#### resources: {}

**No limits in dev means:**
```yaml
# What Kubernetes sees:
resources:
  requests: {}   # No guaranteed resources
  limits: {}     # No maximum enforcement
```

**Pros:**
- Developer can run resource-intensive operations
- No throttling during local testing
- Flexibility for performance testing

**Cons:**
- Can starve other dev pods
- Not production-like (testing without limits)

---

## 📄 values-staging.yaml - Staging Overrides

```yaml
# Staging environment overrides
# Moderate resources, warn-level logging, mirrors prod structure

replicaCount: 2

config:
  environment: "staging"
  logLevel: "warn"
  debugMode: false
  featureFlags:
    enableMetrics: true
    enableTracing: true
    enableProfiling: false
  database:
    host: "postgres-staging.database.svc.cluster.local"
    port: 5432
    name: "appdb_staging"
    maxConnections: 20

resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi

antiAffinity:
  enabled: false
```

### Staging Philosophy:

**Goals:**
- 🎭 Mirror production (but cheaper)
- 🧪 Test at scale
- 💵 Cost-efficient
- ⚖️ Balance between dev and prod

**Staging is for:**
- Load testing
- Integration testing
- Pre-production validation
- Customer demos
- QA testing

### Key Overrides Explained:

#### replicaCount: 2

**Why 2?**
- Tests multi-replica behavior
- Validates load balancing
- Cheaper than 3 (prod)
- Good enough for testing

**What it tests:**
- Session affinity
- Stateless design
- Rolling updates
- Service discovery

#### logLevel: "warn"

**What you see:**
```
[WARN] Database connection pool 80% full
[WARN] Slow API response: 2.5s
[ERROR] Failed to connect to payment gateway
```

**Why warn, not debug?**
- Reduces log volume (and costs)
- Focuses on problems, not noise
- More production-like
- Still shows important events

**Cost impact:**
```
Debug:  1000 MB/day of logs → $50/month storage
Warn:   100 MB/day of logs  → $5/month storage
```

#### debugMode: false

**Staging should mirror prod:**
- No debug endpoints
- No test data seeding
- Production-like error handling
- Realistic performance

**Why disable?**
- Test actual production code paths
- Validate error handling works
- Measure real performance
- Find prod-specific bugs

#### featureFlags

```yaml
enableMetrics: true      # Yes - needed for monitoring
enableTracing: true      # Yes - useful for debugging
enableProfiling: false   # No - performance overhead
```

**enableTracing: true in staging**

**Why?**
- Debug distributed transactions
- Find bottlenecks before prod
- Validate instrumentation
- Low traffic volume = lower overhead

**Example:**
```
User Request → API Gateway → Auth Service → Database
  └─ Trace ID: 7a8b9c → All services tagged
```

#### resources

```yaml
resources:
  limits:
    cpu: 200m        # 0.2 CPU cores max
    memory: 256Mi    # 256 MiB max
  requests:
    cpu: 100m        # 0.1 CPU cores guaranteed
    memory: 128Mi    # 128 MiB guaranteed
```

**What this configuration provides:**

**Requests (guaranteed):**
- Scheduler only places pod on nodes with 100m CPU available
- Pod always gets at least 128Mi memory
- Used for bin-packing decisions

**Limits (maximum):**
- CPU throttled if exceeds 200m (slows down, doesn't crash)
- Memory killed if exceeds 256Mi (OOMKilled)

**Burst capacity:**
- CPU: 2x burst (100m → 200m)
- Memory: 2x burst (128Mi → 256Mi)

**QoS Class: Burstable**
```yaml
# Because requests < limits
# Medium priority during resource pressure
```

**Sizing strategy:**
- Based on load testing results
- 2x production minimum (allows bursts)
- Affordable for testing
- Catches resource-hungry code

#### database

```yaml
host: "postgres-staging.database.svc.cluster.local"
name: "appdb_staging"
maxConnections: 20
```

**maxConnections: 20**

**Calculation:**
```
2 replicas × 10 connections per replica = 20 total
```

**Why 20?**
- Supports moderate load testing
- Mirrors prod pool sizing logic
- Prevents connection exhaustion
- Tests pool management

**Connection pool best practices:**
```
connections_per_pod = (max_connections / replicas) - buffer
20 / 2 = 10 connections per pod (with headroom)
```

---

## 📄 values-prod.yaml - Production Overrides

```yaml
# Production environment overrides
# Strict resources, info logging, HA with anti-affinity

replicaCount: 3

config:
  environment: "production"
  logLevel: "info"
  debugMode: false
  featureFlags:
    enableMetrics: true
    enableTracing: false
    enableProfiling: false
  database:
    host: "postgres-prod.database.svc.cluster.local"
    port: 5432
    name: "appdb_prod"
    maxConnections: 50

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

antiAffinity:
  enabled: true
```

### Production Philosophy:

**Goals:**
- 🛡️ Reliability above all
- 📊 Observability
- 🔒 Security
- ⚡ Performance
- 💰 Cost-effective at scale

**Production is sacred:**
- Every change is deliberate
- Resources are predictable
- High availability is mandatory
- Debug features are disabled

### Key Overrides Explained:

#### replicaCount: 3

**Why 3?**

**High Availability:**
```
1 replica:  Downtime during deployments
2 replicas: 50% capacity during rolling update
3 replicas: 66% capacity during rolling update ✓
```

**Failure tolerance:**
```
3 replicas across 3 nodes:
- 1 node fails → 2 replicas still running (66% capacity)
- Can handle updates + 1 node failure
```

**Update math:**
```yaml
# Deployment strategy (default)
maxUnavailable: 25%  # 1 pod down during updates
maxSurge: 25%        # 1 extra pod during updates

# Update sequence:
3 pods → 4 pods (surge) → 3 pods (old one terminated) → repeat
```

**Production guideline:**
- Minimum 3 replicas for customer-facing services
- 2 replicas acceptable for internal services
- 1 replica only for non-critical batch jobs

#### logLevel: "info"

**What you see:**
```
[INFO] Server started on port 8080
[INFO] Request completed: GET /api/users status=200 duration=45ms
[INFO] Database connection pool initialized: 50 connections
[WARN] Cache miss rate high: 45%
[ERROR] Payment gateway timeout
```

**Why info, not debug?**

**Performance:**
- Debug logging adds 10-30% CPU overhead
- Info logging adds ~2% CPU overhead

**Cost:**
```
Debug:  5 GB/day/replica × 3 replicas = 15 GB/day → $750/month
Info:   500 MB/day/replica × 3 replicas = 1.5 GB/day → $75/month
```

**Security:**
- Debug logs may leak sensitive data (PII, tokens)
- Info logs carefully sanitized

**Actionability:**
- Info level provides what you need for monitoring
- Debug level overwhelms with noise

#### debugMode: false

**Production security:**

**Disabled debug features:**
```yaml
debugMode: false means:
- No /debug/pprof endpoints (prevents DoS)
- No test data seeding endpoints
- No verbose error messages (no stack traces to users)
- No hot-reload (stability)
```

**Attack scenario if enabled:**
```bash
# Attacker discovers debug endpoints
curl https://api.company.com/debug/pprof/heap
# → Downloads memory dump with customer data
# → Massive security incident
```

**Always verify prod:**
```bash
kubectl get cm app-prod-multi-env-app-config -n helm-scenarios-prod -o yaml | grep DEBUG
# Should show: DEBUG_MODE: "false"
```

#### featureFlags

```yaml
enableMetrics: true      # Yes - essential for monitoring
enableTracing: false     # No - too much overhead at scale
enableProfiling: false   # No - security and performance risk
```

**enableMetrics: true**

**Why required in prod:**
- Prometheus scraping for dashboards
- Alerting based on metrics
- Autoscaling signals (HPA)
- SLA tracking

**Example metrics:**
```
http_requests_total{method="GET", status="200"} 1234567
http_request_duration_seconds{endpoint="/api/users"} 0.045
database_connections_active 42
```

**enableTracing: false**

**Why disabled?**

**Overhead at scale:**
```
1000 req/sec × 5ms tracing overhead = 5 seconds/second = 100% CPU
```

**Cost:**
```
Tracing storage: $500/month for 1M spans/day
Without tracing: $0
```

**When to enable:**
- During incident investigation (temporarily)
- Sampled tracing (1% of requests)
- Specific high-value transactions

**enableProfiling: false**

**Why absolutely not in prod:**
- CPU profiling adds 10-20% overhead
- Memory profiling can trigger GC storms
- Exposes internal implementation details
- Potential DoS vector

#### resources - Production Sizing

```yaml
resources:
  limits:
    cpu: 500m        # 0.5 CPU cores max
    memory: 512Mi    # 512 MiB max
  requests:
    cpu: 250m        # 0.25 CPU cores guaranteed
    memory: 256Mi    # 256 MiB guaranteed
```

**How these values were determined:**

**Step 1: Measure in staging**
```bash
kubectl top pod -n helm-scenarios-staging
# app-staging-xxx: 120m CPU, 200Mi memory
```

**Step 2: Add safety margin**
```
Measured: 120m CPU, 200Mi memory
+ 2x buffer: 240m CPU, 400Mi memory
+ Round up: 250m CPU, 512Mi memory (requests)
```

**Step 3: Set burst capacity**
```
Requests × 2 = Limits
250m × 2 = 500m CPU
256Mi × 2 = 512Mi memory
```

**Production resource best practices:**

**Never use unbounded resources:**
```yaml
resources: {}  # ❌ NEVER IN PROD
# Can consume entire node, crash critical services
```

**Set both requests and limits:**
```yaml
resources:
  requests:  # For scheduling
    cpu: 250m
    memory: 256Mi
  limits:    # For safety
    cpu: 500m
    memory: 512Mi
```

**Capacity planning:**
```
3 replicas × 250m CPU = 750m CPU minimum needed
3 replicas × 500m CPU = 1500m CPU if all pods burst
Plan cluster capacity: 2000m CPU available
```

#### database

```yaml
host: "postgres-prod.database.svc.cluster.local"
name: "appdb_prod"
maxConnections: 50
```

**maxConnections: 50**

**Connection pool math:**
```
3 replicas × 15 connections per replica = 45 connections
+ 5 spare for bursts = 50 total
```

**Why not more?**
- PostgreSQL connection overhead: ~10MB per connection
- 1000 connections = 10GB memory just for connections
- Too many connections = context switching overhead

**Why not fewer?**
- Under high load, apps block waiting for connections
- Slow queries hold connections longer
- Need headroom for traffic spikes

**Production tuning:**
```yaml
# Application connection pool config (example)
pool:
  min: 2           # Minimum per replica
  max: 15          # Maximum per replica
  idleTimeout: 30s # Close idle connections
  maxLifetime: 1h  # Recycle long-lived connections
```

#### antiAffinity.enabled: true

**The HA game-changer:**

**What it does:**
```yaml
# Spreads pods across different nodes
Pod 1 → Node A
Pod 2 → Node B
Pod 3 → Node C

# Not:
Pod 1, 2, 3 → Node A  # ❌ Single point of failure
```

**Template expansion:**
```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/name
                operator: In
                values:
                  - multi-env-app
              - key: app.kubernetes.io/instance
                operator: In
                values:
                  - app-prod
          topologyKey: kubernetes.io/hostname
```

**Why "preferred" not "required"?**

**Preferred (soft):**
```yaml
preferredDuringSchedulingIgnoredDuringExecution
# Scheduler tries to spread, but schedules anyway if can't
# Prevents deployment failure if not enough nodes
```

**Required (hard):**
```yaml
requiredDuringSchedulingIgnoredDuringExecution
# Scheduler MUST spread, or pods stay Pending
# Risk: If only 2 nodes available, 3rd pod stays Pending
```

**Production trade-off:**
- Use "preferred" for flexibility
- Use "required" for strict compliance requirements

**Verify anti-affinity working:**
```bash
kubectl get pods -n helm-scenarios-prod -o wide
# Should show pods on different nodes
NAME           NODE
app-prod-xxx   kind-worker
app-prod-yyy   kind-worker2
app-prod-zzz   kind-worker3
```

---

## 📄 templates/deployment.yaml - The Adaptable Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "multi-env-app.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "multi-env-app.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "multi-env-app.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "multi-env-app.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/environment: {{ .Values.config.environment }}
      annotations:
        # Force rolling restart when ConfigMap changes
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
    spec:
      {{- if .Values.antiAffinity.enabled }}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app.kubernetes.io/name
                      operator: In
                      values:
                        - {{ include "multi-env-app.name" . }}
                    - key: app.kubernetes.io/instance
                      operator: In
                      values:
                        - {{ .Release.Name }}
                topologyKey: kubernetes.io/hostname
      {{- end }}
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 80
              protocol: TCP
          envFrom:
            - configMapRef:
                name: {{ include "multi-env-app.fullname" . }}-config
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
          {{- if .Values.resources }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

### Template Patterns Explained:

#### Conditional Anti-Affinity

```yaml
{{- if .Values.antiAffinity.enabled }}
affinity:
  podAntiAffinity:
    # ... anti-affinity rules
{{- end }}
```

**How it works:**

**Dev (antiAffinity.enabled: false):**
```yaml
# This entire block is omitted from rendered YAML
spec:
  containers:
    - name: multi-env-app
```

**Prod (antiAffinity.enabled: true):**
```yaml
spec:
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        # ... rules included
  containers:
    - name: multi-env-app
```

**Template syntax:**
- `{{-` - Left trim whitespace
- `}}` - End template
- `if .Values.x` - Conditional rendering

#### ConfigMap Checksum Annotation

```yaml
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

**What this does:** Forces pod restart when ConfigMap changes

**The problem it solves:**

```yaml
# Without checksum:
1. Update ConfigMap (change LOG_LEVEL)
2. Pods keep running with old config
3. Must manually restart pods

# With checksum:
1. Update ConfigMap (change LOG_LEVEL)
2. Checksum changes
3. Deployment sees pod template changed
4. Rolling restart automatically triggered
```

**How it works:**
1. Template engine includes entire configmap.yaml content
2. SHA256 hash computed
3. Hash embedded as annotation
4. Deployment controller sees annotation change
5. Rolling update triggered

**Production benefit:**
```bash
helm upgrade app-prod . -f values-prod.yaml
# ConfigMap updated from LOG_LEVEL=warn to LOG_LEVEL=error
# Pods automatically restart with new config
# No manual kubectl rollout restart needed
```

#### Conditional Resources

```yaml
{{- if .Values.resources }}
resources:
  {{- toYaml .Values.resources | nindent 12 }}
{{- end }}
```

**Why conditional?**

**Dev (resources: {}):**
```yaml
# Empty dict = false in Go templates
# No resources block rendered
spec:
  containers:
    - name: multi-env-app
      ports:
        # No resources section
```

**Prod (resources with values):**
```yaml
spec:
  containers:
    - name: multi-env-app
      resources:
        limits:
          cpu: 500m
          memory: 512Mi
        requests:
          cpu: 250m
          memory: 256Mi
```

**toYaml function:**
- Converts Go data structure to YAML
- Preserves structure and types
- `nindent 12` - Indent 12 spaces and add newline

#### Environment Variables from ConfigMap

```yaml
envFrom:
  - configMapRef:
      name: {{ include "multi-env-app.fullname" . }}-config
```

**What this does:** Injects all ConfigMap keys as environment variables

**Example:**

**ConfigMap:**
```yaml
data:
  LOG_LEVEL: "debug"
  DB_HOST: "postgres-dev"
  DEBUG_MODE: "true"
```

**Container sees:**
```bash
env | grep -E '(LOG_LEVEL|DB_HOST|DEBUG_MODE)'
LOG_LEVEL=debug
DB_HOST=postgres-dev
DEBUG_MODE=true
```

**Alternative (explicit env vars):**
```yaml
env:
  - name: LOG_LEVEL
    valueFrom:
      configMapKeyRef:
        name: my-config
        key: LOG_LEVEL
# Must repeat for every variable
```

**envFrom advantages:**
- Less verbose
- Add new config without changing Deployment
- Easy to see all config in one place

#### Health Probes

```yaml
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
```

**Liveness vs Readiness:**

| Probe | Purpose | Failure Action | Use Case |
|-------|---------|----------------|----------|
| **Liveness** | Is container alive? | Restart container | Deadlock detection |
| **Readiness** | Is container ready for traffic? | Remove from Service endpoints | Startup, graceful shutdown |

**Configuration explained:**

**Liveness:**
- `initialDelaySeconds: 5` - Wait 5s after container starts
- `periodSeconds: 10` - Check every 10 seconds
- Failures → Container restart

**Readiness:**
- `initialDelaySeconds: 3` - Wait 3s after container starts
- `periodSeconds: 5` - Check every 5 seconds
- Failures → Remove from load balancer

**Production tuning:**
```yaml
readinessProbe:
  httpGet:
    path: /healthz
    port: http
  initialDelaySeconds: 10   # App startup time
  periodSeconds: 5
  failureThreshold: 3        # Fail after 3 consecutive failures
  successThreshold: 1        # Back to healthy after 1 success
  timeoutSeconds: 2          # Probe timeout
```

---

## 📄 templates/service.yaml - Environment-Agnostic Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "multi-env-app.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "multi-env-app.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "multi-env-app.selectorLabels" . | nindent 4 }}
```

### Service Template Patterns:

#### Dynamic Service Type

```yaml
type: {{ .Values.service.type }}
```

**Renders differently per environment:**

**All environments (default):**
```yaml
type: ClusterIP  # Internal-only
```

**If overridden:**
```yaml
# values-dev.yaml
service:
  type: NodePort  # External access for testing
```

**Service type strategy:**
- Dev: ClusterIP or NodePort (local testing)
- Staging: ClusterIP + Ingress (prod-like)
- Prod: ClusterIP + Ingress + TLS (secure)

#### Named Port Reference

```yaml
ports:
  - port: 80
    targetPort: http  # References container port name
    name: http
```

**Why named ports?**

**Container definition:**
```yaml
ports:
  - name: http
    containerPort: 80
```

**Service references by name:**
```yaml
targetPort: http  # Not 80
```

**Benefits:**
- Change container port without changing Service
- Self-documenting
- Supports multiple ports easily

**Multiple ports example:**
```yaml
# Container
ports:
  - name: http
    containerPort: 8080
  - name: metrics
    containerPort: 9090

# Service
ports:
  - name: http
    port: 80
    targetPort: http
  - name: metrics
    port: 9090
    targetPort: metrics
```

---

## 📄 templates/configmap.yaml - Environment Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "multi-env-app.fullname" . }}-config
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "multi-env-app.labels" . | nindent 4 }}
data:
  APP_ENVIRONMENT: {{ .Values.config.environment | quote }}
  LOG_LEVEL: {{ .Values.config.logLevel | quote }}
  DEBUG_MODE: {{ .Values.config.debugMode | quote }}
  DB_HOST: {{ .Values.config.database.host | quote }}
  DB_PORT: {{ .Values.config.database.port | quote }}
  DB_NAME: {{ .Values.config.database.name | quote }}
  DB_MAX_CONNECTIONS: {{ .Values.config.database.maxConnections | quote }}
  FEATURE_METRICS: {{ .Values.config.featureFlags.enableMetrics | quote }}
  FEATURE_TRACING: {{ .Values.config.featureFlags.enableTracing | quote }}
  FEATURE_PROFILING: {{ .Values.config.featureFlags.enableProfiling | quote }}
```

### ConfigMap Best Practices:

#### Always Quote Values

```yaml
LOG_LEVEL: {{ .Values.config.logLevel | quote }}
```

**Why?**

**Without quote:**
```yaml
# values.yaml
logLevel: true

# Renders as:
LOG_LEVEL: true  # YAML boolean

# Container sees:
echo $LOG_LEVEL
# Output: true (not "true")
```

**With quote:**
```yaml
# Renders as:
LOG_LEVEL: "true"  # YAML string

# Container sees:
echo $LOG_LEVEL
# Output: true (as string)
```

**Critical for:**
- Booleans (true/false)
- Numbers (5432, 100, 3.14)
- Special strings (yes, no, on, off)

#### Naming Conventions

**Environment variable best practices:**
```yaml
UPPER_SNAKE_CASE: "value"  # Standard
lower-kebab-case: "value"   # Non-standard
camelCase: "value"          # Non-standard
```

**Prefixing strategy:**
```yaml
# Group by category
DB_HOST: "postgres"
DB_PORT: "5432"
DB_NAME: "app"

FEATURE_METRICS: "true"
FEATURE_TRACING: "false"

APP_ENVIRONMENT: "production"
APP_LOG_LEVEL: "info"
```

#### Rendered Examples

**Development:**
```yaml
data:
  APP_ENVIRONMENT: "development"
  LOG_LEVEL: "debug"
  DEBUG_MODE: "true"
  DB_HOST: "postgres-dev.database.svc.cluster.local"
  DB_MAX_CONNECTIONS: "5"
  FEATURE_PROFILING: "true"
```

**Staging:**
```yaml
data:
  APP_ENVIRONMENT: "staging"
  LOG_LEVEL: "warn"
  DEBUG_MODE: "false"
  DB_HOST: "postgres-staging.database.svc.cluster.local"
  DB_MAX_CONNECTIONS: "20"
  FEATURE_PROFILING: "false"
```

**Production:**
```yaml
data:
  APP_ENVIRONMENT: "production"
  LOG_LEVEL: "info"
  DEBUG_MODE: "false"
  DB_HOST: "postgres-prod.database.svc.cluster.local"
  DB_MAX_CONNECTIONS: "50"
  FEATURE_PROFILING: "false"
```

---

## 📄 templates/_helpers.tpl - Reusable Template Functions

```yaml
{{/*
Expand the name of the chart.
*/}}
{{- define "multi-env-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "multi-env-app.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "multi-env-app.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "multi-env-app.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/environment: {{ .Values.config.environment }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "multi-env-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "multi-env-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

### Helper Functions Explained:

#### multi-env-app.name

```go
{{- define "multi-env-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
```

**What it does:** Returns the chart name (or override)

**Usage:**
```yaml
# In templates:
{{ include "multi-env-app.name" . }}
# Returns: "multi-env-app"
```

**Pipeline explanation:**
```go
default .Chart.Name .Values.nameOverride
// If nameOverride set, use it; otherwise use Chart.Name

| trunc 63
// Truncate to 63 characters (Kubernetes label limit)

| trimSuffix "-"
// Remove trailing hyphen if present
```

**Why 63 characters?**
- Kubernetes DNS label limit
- Ensures resources can be created
- Prevents validation errors

#### multi-env-app.fullname

```go
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
```

**What it does:** Combines release name + chart name

**Examples:**

**Release: app-dev, Chart: multi-env-app**
```
app-dev-multi-env-app
```

**Release: app-prod, Chart: multi-env-app**
```
app-prod-multi-env-app
```

**Why combine?**
- Multiple releases of same chart in same namespace
- Each release gets unique resource names
- Prevents naming conflicts

**Collision prevention:**
```yaml
# Without fullname:
name: multi-env-app  # Same for all releases!

# With fullname:
name: app-dev-multi-env-app      # Dev release
name: app-staging-multi-env-app  # Staging release
name: app-prod-multi-env-app     # Prod release
```

#### multi-env-app.labels

```go
{{- define "multi-env-app.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "multi-env-app.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/environment: {{ .Values.config.environment }}
{{- end }}
```

**Renders as:**

**Development:**
```yaml
labels:
  helm.sh/chart: multi-env-app-0.1.0
  app.kubernetes.io/name: multi-env-app
  app.kubernetes.io/instance: app-dev
  app.kubernetes.io/managed-by: Helm
  app.kubernetes.io/environment: development
```

**Production:**
```yaml
labels:
  helm.sh/chart: multi-env-app-0.1.0
  app.kubernetes.io/name: multi-env-app
  app.kubernetes.io/instance: app-prod
  app.kubernetes.io/managed-by: Helm
  app.kubernetes.io/environment: production
```

**Label purposes:**

| Label | Purpose | Example |
|-------|---------|---------|
| `helm.sh/chart` | Track chart version | Identify upgrade issues |
| `app.kubernetes.io/name` | Application name | Group resources |
| `app.kubernetes.io/instance` | Release name | Distinguish environments |
| `app.kubernetes.io/managed-by` | Management tool | Know it's Helm-managed |
| `app.kubernetes.io/environment` | Environment name | Filter by environment |

**Usage in selectors:**
```bash
# Get all prod resources
kubectl get all -l app.kubernetes.io/environment=production

# Get specific release
kubectl get all -l app.kubernetes.io/instance=app-prod
```

#### multi-env-app.selectorLabels

```go
{{- define "multi-env-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "multi-env-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

**Why separate from common labels?**

**Selector labels are immutable:**
```yaml
# Deployment
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: multi-env-app
      app.kubernetes.io/instance: app-prod
      # Cannot add more labels after creation!
```

**Common labels can change:**
```yaml
# Deployment metadata
metadata:
  labels:
    app.kubernetes.io/name: multi-env-app
    app.kubernetes.io/instance: app-prod
    helm.sh/chart: multi-env-app-0.1.0  # Can change
    app.kubernetes.io/environment: production  # Can change
```

**Best practice:**
- Minimal selector labels (name + instance)
- Rich metadata labels (chart version, environment, team, etc.)

---

## 🔄 Values File Merging and Precedence

### How Helm Merges Values

**Command:**
```bash
helm install app-prod ./chart -f values-prod.yaml
```

**Merge sequence:**
```
1. Chart defaults (values.yaml)
   ↓
2. User values file (values-prod.yaml) - OVERWRITES
   ↓
3. CLI --set flags - OVERWRITES
```

**Example merge:**

**values.yaml (base):**
```yaml
replicaCount: 1
config:
  logLevel: info
  debugMode: false
  database:
    host: localhost
    port: 5432
resources: {}
```

**values-prod.yaml (override):**
```yaml
replicaCount: 3
config:
  environment: production
  logLevel: info
  database:
    host: postgres-prod.database.svc.cluster.local
resources:
  limits:
    cpu: 500m
```

**Effective configuration (merged):**
```yaml
replicaCount: 3  # From prod
config:
  environment: production  # From prod (new key)
  logLevel: info           # From prod (same as base)
  debugMode: false         # From base (not overridden)
  database:
    host: postgres-prod.database.svc.cluster.local  # From prod
    port: 5432  # From base (not overridden)
resources:  # From prod (entire block replaced)
  limits:
    cpu: 500m
```

**Key insight:**
- Helm merges maps recursively
- Prod file only needs to specify what changes
- Base provides all defaults

---

## 🎓 Common Multi-Environment Patterns

### Pattern 1: Environment-Specific Secrets

**Problem:** Different environments need different secrets

**Solution:**
```bash
# Create environment-specific secrets
kubectl create secret generic app-secrets \
  --from-literal=db-password=dev-password \
  -n helm-scenarios

kubectl create secret generic app-secrets \
  --from-literal=db-password=prod-password-secure \
  -n helm-scenarios-prod
```

**values-prod.yaml:**
```yaml
secretName: app-secrets  # Same name, different namespace
```

**Template:**
```yaml
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: {{ .Values.secretName }}
        key: db-password
```

### Pattern 2: Multiple Values Files

**Layer multiple environments:**
```bash
helm install app-prod ./chart \
  -f values.yaml \          # Base
  -f values-prod.yaml \     # Environment
  -f values-region-us.yaml  # Region-specific
```

**values-region-us.yaml:**
```yaml
config:
  database:
    host: postgres-us-east-1.database.svc.cluster.local
  cdn:
    endpoint: cdn.us.company.com
```

### Pattern 3: Environment-Specific Ingress

**values-prod.yaml:**
```yaml
ingress:
  enabled: true
  host: api.company.com
  tls:
    enabled: true
    secretName: prod-tls
```

**values-dev.yaml:**
```yaml
ingress:
  enabled: false  # Use port-forward in dev
```

### Pattern 4: Autoscaling by Environment

**values-prod.yaml:**
```yaml
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPU: 70
```

**values-dev.yaml:**
```yaml
autoscaling:
  enabled: false  # Fixed replicas in dev
```

**Template:**
```yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
# ...
{{- end }}
```

---

## 🐛 Troubleshooting Multi-Environment Deployments

### Issue 1: Wrong configuration applied

**Symptom:**
```bash
kubectl get cm app-prod-config -o yaml
# Shows DEBUG_MODE: "true"  # ❌ Should be false!
```

**Diagnosis:**
```bash
# Check what values Helm used
helm get values app-prod -n helm-scenarios-prod

# Should show:
config:
  debugMode: false
```

**Causes:**
1. Wrong values file used during install
2. Values file not updated
3. ConfigMap checksum not triggering restart

**Fix:**
```bash
# Re-upgrade with correct values
helm upgrade app-prod ./chart -f values-prod.yaml -n helm-scenarios-prod

# Force pod restart
kubectl rollout restart deployment app-prod -n helm-scenarios-prod
```

### Issue 2: Pods not spreading across nodes

**Symptom:**
```bash
kubectl get pods -n helm-scenarios-prod -o wide
# All 3 pods on same node
```

**Diagnosis:**
```bash
# Check if anti-affinity enabled
helm get values app-prod -n helm-scenarios-prod | grep -A 2 antiAffinity
# Should show:
# antiAffinity:
#   enabled: true
```

**Causes:**
1. Anti-affinity not enabled in values
2. Not enough nodes available
3. Node selectors/taints preventing scheduling

**Fix:**
```bash
# Verify cluster has multiple nodes
kubectl get nodes

# Check pod events
kubectl describe pod app-prod-xxx -n helm-scenarios-prod

# Re-deploy with anti-affinity
helm upgrade app-prod ./chart -f values-prod.yaml -n helm-scenarios-prod
```

### Issue 3: Resource limits causing OOMKills

**Symptom:**
```bash
kubectl get pods -n helm-scenarios-prod
# app-prod-xxx   0/1   OOMKilled   3   5m
```

**Diagnosis:**
```bash
# Check memory limits
kubectl describe pod app-prod-xxx -n helm-scenarios-prod | grep -A 5 Limits
# Limits:
#   memory: 256Mi  # Too low!

# Check actual usage
kubectl top pod app-prod-xxx -n helm-scenarios-prod
# NAME            CPU   MEMORY
# app-prod-xxx    100m  280Mi  # Exceeds 256Mi limit
```

**Fix:**
```yaml
# values-prod.yaml - Increase limits
resources:
  limits:
    memory: 512Mi  # Doubled
```

```bash
helm upgrade app-prod ./chart -f values-prod.yaml -n helm-scenarios-prod
```

### Issue 4: Different environments showing same config

**Symptom:**
```bash
# Staging shows production database host
kubectl get cm app-staging-config -n helm-scenarios-staging -o yaml
# DB_HOST: postgres-prod.database.svc.cluster.local  # ❌
```

**Diagnosis:**
```bash
# Check what values file was used
helm get values app-staging -n helm-scenarios-staging --all | grep database
```

**Cause:**
Used production values file for staging deployment

**Fix:**
```bash
# Reinstall with correct values
helm uninstall app-staging -n helm-scenarios-staging
helm install app-staging ./chart -f values-staging.yaml -n helm-scenarios-staging
```

---

## 📚 Best Practices for Multi-Environment Deployments

### 1. DRY (Don't Repeat Yourself)

**Bad:**
```yaml
# values-dev.yaml - Repeats everything
replicaCount: 1
image:
  repository: nginx  # Duplicated
  tag: "1.24"        # Duplicated
config:
  logLevel: debug
  # ... 50 more lines
```

**Good:**
```yaml
# values-dev.yaml - Only overrides
replicaCount: 1
config:
  environment: development
  logLevel: debug
  debugMode: true
# Base values.yaml provides other defaults
```

### 2. Environment Parity

**Progressive complexity:**
```
Dev:     Minimal (easy to run locally)
  ↓
Staging: Mirrors prod (realistic testing)
  ↓
Prod:    Optimized (reliability + performance)
```

**Maintain parity:**
```yaml
# Same structure across all environments
config:
  environment: ${ENV}      # Only value differs
  logLevel: ${LEVEL}       # Only value differs
  database:
    host: ${DB_HOST}       # Only value differs
    port: 5432             # Same everywhere
    maxConnections: ${MAX} # Scales with environment
```

### 3. Validate Before Deploying

**Pre-deployment checks:**
```bash
# 1. Lint chart
helm lint ./chart -f values-prod.yaml

# 2. Dry-run install
helm install app-prod ./chart \
  -f values-prod.yaml \
  --dry-run --debug \
  -n helm-scenarios-prod

# 3. Template diff (vs staging)
diff \
  <(helm template ./chart -f values-staging.yaml) \
  <(helm template ./chart -f values-prod.yaml)

# 4. Validate rendered YAML
helm template ./chart -f values-prod.yaml | kubectl apply --dry-run=client -f -
```

### 4. Version Control Values Files

**Git repository structure:**
```
my-app/
├── chart/
│   ├── Chart.yaml
│   ├── values.yaml          # Committed
│   ├── values-dev.yaml      # Committed
│   ├── values-staging.yaml  # Committed
│   ├── values-prod.yaml     # Committed
│   └── templates/
└── .gitignore               # Don't commit secrets!
```

**Never commit secrets:**
```yaml
# values-prod.yaml
# ❌ DON'T:
database:
  password: super-secret-password

# ✅ DO:
database:
  passwordSecretName: db-credentials
  passwordSecretKey: password
```

### 5. Document Environment Differences

**Add comments to values files:**
```yaml
# values-prod.yaml

# Production requires HA:
# - 3+ replicas for redundancy
# - Anti-affinity to spread across nodes
# - Strict resource limits to prevent noisy neighbors
replicaCount: 3

# Logging optimized for cost/visibility balance:
# - info level: ~500MB/day/replica (vs debug: ~5GB/day)
# - Rotated every 24h, retained for 30d
config:
  logLevel: info
```

### 6. Test Value Overrides

**Automated testing:**
```bash
#!/bin/bash
# test-environments.sh

for env in dev staging prod; do
  echo "Testing $env environment..."

  # Render templates
  helm template app ./chart -f values-${env}.yaml > /tmp/${env}.yaml

  # Validate
  kubectl apply --dry-run=client -f /tmp/${env}.yaml

  # Check expected values
  if [ "$env" == "prod" ]; then
    grep -q "replicas: 3" /tmp/${env}.yaml || {
      echo "ERROR: Prod should have 3 replicas"
      exit 1
    }
  fi
done

echo "All environments validated!"
```

### 7. Use CI/CD Pipelines

**GitLab CI example:**
```yaml
# .gitlab-ci.yml
deploy-dev:
  stage: deploy
  script:
    - helm upgrade --install app-dev ./chart
        -f values-dev.yaml
        -n helm-scenarios
  only:
    - develop

deploy-staging:
  stage: deploy
  script:
    - helm upgrade --install app-staging ./chart
        -f values-staging.yaml
        -n helm-scenarios-staging
  only:
    - main

deploy-prod:
  stage: deploy
  script:
    - helm upgrade --install app-prod ./chart
        -f values-prod.yaml
        -n helm-scenarios-prod
  when: manual  # Require human approval
  only:
    - main
```

---

## 📊 Comparison: Before and After Multi-Environment Pattern

### Before (Manual Per-Environment Manifests)

**Challenges:**
```
app-dev/
├── deployment.yaml       # 100 lines, dev config hardcoded
├── service.yaml          # 20 lines
└── configmap.yaml        # 30 lines

app-staging/
├── deployment.yaml       # 100 lines, 90% same as dev
├── service.yaml          # 20 lines, identical to dev
└── configmap.yaml        # 30 lines, slightly different

app-prod/
├── deployment.yaml       # 100 lines, 85% same as dev
├── service.yaml          # 20 lines, identical to dev
└── configmap.yaml        # 30 lines, very different
```

**Problems:**
- 450 lines total (150 per environment)
- 90% duplication
- Fix in one env, manually copy to others
- Drift between environments
- Hard to see differences

### After (Helm Multi-Environment Pattern)

**Solution:**
```
chart/
├── Chart.yaml            # 6 lines
├── values.yaml           # 40 lines (base)
├── values-dev.yaml       # 10 lines (overrides only)
├── values-staging.yaml   # 12 lines (overrides only)
├── values-prod.yaml      # 15 lines (overrides only)
└── templates/
    ├── deployment.yaml   # 75 lines (parameterized)
    ├── service.yaml      # 17 lines (parameterized)
    └── configmap.yaml    # 19 lines (parameterized)
```

**Benefits:**
- 194 lines total (vs 450)
- 57% reduction
- Fix once in templates
- Guaranteed consistency
- Differences explicit in values files

---

## 🔗 Further Reading

### Official Documentation:
- **Helm Values Files**: https://helm.sh/docs/chart_template_guide/values_files/
- **Helm Template Functions**: https://helm.sh/docs/chart_template_guide/function_list/
- **Kubernetes Resource Management**: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- **Pod Affinity/Anti-Affinity**: https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity

### Best Practices:
- **12-Factor App**: https://12factor.net/config
- **Helm Best Practices**: https://helm.sh/docs/chart_best_practices/
- **Environment Parity**: https://12factor.net/dev-prod-parity

### Advanced Topics:
- **Helmfile** (multi-environment orchestration): https://github.com/helmfile/helmfile
- **Kustomize with Helm**: https://kubectl.docs.kubernetes.io/guides/config_management/components/
- **ArgoCD with Helm**: https://argo-cd.readthedocs.io/en/stable/user-guide/helm/

---

## 🎯 Key Takeaways

1. **One Chart, Multiple Environments** - Single source of truth, different configurations
2. **Values File Layering** - Base defaults + environment overrides = effective config
3. **Progressive Configuration** - Dev (flexible) → Staging (prod-like) → Prod (strict)
4. **DRY Principle** - Only override what changes, inherit the rest
5. **Anti-Affinity in Prod** - Spread replicas for HA
6. **Resource Limits** - Always set in prod, optional in dev
7. **Feature Flags** - Control features per environment
8. **Validate Before Deploy** - Use `helm template`, `--dry-run`, and diff
9. **Document Differences** - Comment why each environment differs
10. **Automate with CI/CD** - Deploy environments consistently

---

*This comprehensive guide provides everything you need to understand and implement multi-environment Helm deployments. This pattern is used in every production Kubernetes setup and is fundamental to effective Helm usage!*
