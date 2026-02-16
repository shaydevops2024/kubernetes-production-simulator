# Helm Hooks Explanation - Complete Guide

This guide provides a comprehensive explanation of Helm hooks - how they work, when to use them, and how to implement them effectively. You'll learn how to control the lifecycle of your Helm releases with pre-install, post-install, and pre-delete hooks.

---

## 🎯 What are Helm Hooks?

**Helm hooks** are special Kubernetes resources (typically Jobs or Pods) that Helm executes at specific points in the release lifecycle. They allow you to run tasks before or after installing, upgrading, or deleting a release.

### Why Hooks Matter

**Without hooks:**
```bash
# Manual approach
kubectl apply -f db-migration.yaml
kubectl wait --for=condition=complete job/db-migration
helm install myapp ./chart
kubectl apply -f smoke-test.yaml
# ❌ Error-prone, manual coordination required
```

**With hooks:**
```bash
# Automatic approach
helm install myapp ./chart
# ✅ Runs pre-install hook (db migration)
# ✅ Deploys application
# ✅ Runs post-install hook (smoke test)
# ✅ All coordinated automatically
```

**Key Benefits:**
- ✅ **Automated workflows** - Run setup/teardown tasks automatically
- ✅ **Ordered execution** - Control exactly when tasks run
- ✅ **Release integration** - Hooks are part of the release lifecycle
- ✅ **Failure handling** - Failed hooks can block deployment
- ✅ **Cleanup control** - Choose when to delete hook resources

### Common Hook Use Cases

| Hook Type | Use Cases | Examples |
|-----------|-----------|----------|
| **pre-install** | Setup before deployment | Database migrations, schema updates, backup creation |
| **post-install** | Validation after deployment | Smoke tests, health checks, notification sending |
| **pre-upgrade** | Preparation for update | Database backups, compatibility checks |
| **post-upgrade** | Validation after update | Integration tests, cache warming |
| **pre-delete** | Cleanup preparation | Data backup, graceful shutdown |
| **post-delete** | Final cleanup | External resource cleanup, notifications |

---

## 🔄 Hook Execution Lifecycle

Understanding the exact order of operations is crucial for designing effective hooks.

### Install Lifecycle

```
helm install myapp ./chart
    │
    ├─→ 1. Render templates
    │       - Process all YAML files
    │       - Substitute values
    │       - Generate final manifests
    │
    ├─→ 2. Run pre-install hooks (weight: low → high)
    │       - Create hook resources
    │       - Wait for completion
    │       - ⚠️ If any hook fails → installation ABORTS
    │
    ├─→ 3. Create main resources
    │       - Deployments
    │       - Services
    │       - ConfigMaps
    │       - etc.
    │
    ├─→ 4. Run post-install hooks (weight: low → high)
    │       - Create hook resources
    │       - Wait for completion
    │       - ⚠️ If any hook fails → release marked FAILED
    │
    └─→ 5. Release marked "deployed"
```

### Upgrade Lifecycle

```
helm upgrade myapp ./chart
    │
    ├─→ 1. Render templates
    │
    ├─→ 2. Run pre-upgrade hooks
    │       - Often reuse pre-install hooks
    │       - Run before any changes applied
    │
    ├─→ 3. Update resources
    │       - Rolling update Deployments
    │       - Modify Services/ConfigMaps
    │
    ├─→ 4. Run post-upgrade hooks
    │       - Often reuse post-install hooks
    │
    └─→ 5. Release marked "deployed"
```

### Uninstall Lifecycle

```
helm uninstall myapp
    │
    ├─→ 1. Run pre-delete hooks
    │       - Data backup
    │       - Graceful shutdown
    │
    ├─→ 2. Delete all resources
    │       - Main application resources
    │       - Hook resources (based on delete policy)
    │
    └─→ 3. Release record removed
```

---

## 📄 Chart.yaml - Chart Metadata

### Full File

```yaml
apiVersion: v2
name: hooks-demo
description: A Helm chart demonstrating lifecycle hooks (pre-install, post-install, pre-delete)
type: application
version: 0.1.0
appVersion: "1.0.0"
```

### Field-by-Field Breakdown

#### apiVersion: v2

**What it is:** Helm chart API version

**Options:**
- `v2` - Helm 3 (current standard)
- `v1` - Helm 2 (deprecated, no longer supported)

**Why v2:**
- Required for Helm 3
- Supports all modern features
- Includes hook improvements

#### name: hooks-demo

**What it is:** Chart name used in commands and as default release name

**Usage:**
```bash
helm install my-release ./hooks-demo
# my-release = release name (can be anything)
# hooks-demo = chart name (from Chart.yaml)
```

**Naming conventions:**
- Use lowercase
- Use hyphens (not underscores)
- Descriptive and unique
- Max 63 characters

#### description

**What it is:** Human-readable description of what the chart does

**Best practices:**
- One sentence describing purpose
- Mention key features (in this case: lifecycle hooks)
- Helpful for chart search and documentation

#### type: application

**What it is:** Defines the chart's purpose

**Options:**
- `application` - Deploys workloads (default)
- `library` - Provides reusable templates only

**Why application:**
- We're deploying actual resources (Deployment, Service, Jobs)
- Library charts cannot be installed directly
- Application charts can include library charts as dependencies

#### version: 0.1.0

**What it is:** Chart version (not application version)

**Semantic versioning:**
- `MAJOR.MINOR.PATCH`
- Increment `MAJOR` for breaking changes
- Increment `MINOR` for new features (backward compatible)
- Increment `PATCH` for bug fixes

**Important:** This is the **chart** version, not the application version

#### appVersion: "1.0.0"

**What it is:** Version of the application the chart deploys

**Difference from version:**
- `version` = Chart version (changes when chart templates change)
- `appVersion` = Application version (changes when app code changes)

**Example:**
```yaml
version: 0.1.0      # Chart structure
appVersion: "1.0.0" # nginx 1.0.0

version: 0.1.1      # Updated hook logic
appVersion: "1.0.0" # Still nginx 1.0.0

version: 0.1.1      # Chart unchanged
appVersion: "2.0.0" # Now nginx 2.0.0
```

**Best practice:** Always quote appVersion to avoid YAML parsing issues

---

## 📄 values.yaml - Configuration Values

### Full File

```yaml
# Default values for hooks-demo chart

replicaCount: 2

image:
  repository: nginx
  tag: "1.24"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

# Pre-install hook configuration (simulates DB migration)
preInstall:
  image:
    repository: busybox
    tag: "1.36"
  # Simulated migration duration in seconds
  migrationDuration: 5
  dbHost: "postgres.database.svc.cluster.local"
  dbName: "appdb"

# Post-install hook configuration (simulates smoke test)
postInstall:
  image:
    repository: busybox
    tag: "1.36"
  # Simulated test duration in seconds
  testDuration: 3
  # Endpoint to test after deployment
  testEndpoint: "http://hooks-demo:80"

resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 50m
    memory: 64Mi
```

### Main Application Values

#### replicaCount: 2

**What it is:** Number of application pod replicas

**Why 2:**
- Provides high availability
- Allows rolling updates without downtime
- Reasonable for demo/testing
- Not overloading the cluster

**Production considerations:**
- Minimum 2 for HA
- Use 3+ for critical services
- Consider using HPA (Horizontal Pod Autoscaler) instead

#### image

**repository: nginx**
- Simple web server for demonstration
- Lightweight and reliable
- Standard container image

**tag: "1.24"**
- Specific version for reproducibility
- Always quote tags to avoid YAML parsing issues
- Avoid `latest` tag in production

**pullPolicy: IfNotPresent**
- Only pull if image not already on node
- Faster deployments
- Use `Always` for `latest` tag

#### service

**type: ClusterIP**
- Internal cluster access only
- Default service type
- Use `LoadBalancer` or `NodePort` for external access

**port: 80**
- HTTP port
- Standard web server port
- Mapped to container port 80

#### resources

**requests:**
- `cpu: 50m` - Minimum guaranteed CPU (0.05 cores)
- `memory: 64Mi` - Minimum guaranteed memory (67 MB)

**limits:**
- `cpu: 100m` - Maximum CPU (0.1 cores)
- `memory: 128Mi` - Maximum memory (134 MB)

**Why these values:**
- Small enough for local Kind cluster
- Sufficient for nginx web server
- Allows 2x CPU burst, 2x memory burst
- Creates "Burstable" QoS class

### Pre-Install Hook Values

#### preInstall.image

**repository: busybox**
- Minimal container image (1-5 MB)
- Contains essential Unix utilities
- Perfect for simple scripts

**tag: "1.36"**
- Stable version
- Includes shell for scripting

#### preInstall.migrationDuration: 5

**What it is:** Simulated duration of database migration

**Purpose:** Demonstrates that Helm waits for hook completion

**In production:**
- Remove simulation sleep
- Run actual migration commands
- Use migration tools (Flyway, Liquibase, Alembic)

#### preInstall.dbHost: "postgres.database.svc.cluster.local"

**What it is:** Database service hostname in Kubernetes DNS format

**DNS format breakdown:**
```
postgres.database.svc.cluster.local
   │       │       │      │
   │       │       │      └─ Cluster domain (usually cluster.local)
   │       │       └──────── Service indicator
   │       └──────────────── Namespace (database)
   └──────────────────────── Service name (postgres)
```

**Short form:** `postgres.database` (same namespace assumes `svc.cluster.local`)

**Why this format:**
- Assumes PostgreSQL is deployed in `database` namespace
- Follows Kubernetes service discovery pattern
- Works from any namespace

#### preInstall.dbName: "appdb"

**What it is:** Target database name for migrations

**In production:**
- Match your actual database name
- Store in Secret for sensitive info
- Use environment-specific values

### Post-Install Hook Values

#### postInstall.image

**Same as preInstall:** Uses busybox for lightweight smoke tests

#### postInstall.testDuration: 3

**What it is:** Simulated duration of smoke tests

**Purpose:** Shows Helm waiting for post-install validation

**In production:**
- Remove simulation
- Run actual health checks
- Test critical endpoints

#### postInstall.testEndpoint: "http://hooks-demo:80"

**What it is:** Service endpoint to test after deployment

**Format breakdown:**
```
http://hooks-demo:80
  │       │        │
  │       │        └─ Port (service port)
  │       └────────── Service name (from templates)
  └────────────────── Protocol (http/https)
```

**Why this works:**
- `hooks-demo` resolves to the Service (created by templates)
- Same namespace, so no FQDN needed
- Port matches `service.port` value

**In production:**
```yaml
# Test actual endpoints
testEndpoint: "http://{{ .Release.Name }}-service:{{ .Values.service.port }}/health"
```

---

## 📄 templates/_helpers.tpl - Template Functions

### Full File

```yaml
{{/*
Expand the name of the chart.
*/}}
{{- define "hooks-demo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "hooks-demo.fullname" -}}
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
{{- define "hooks-demo.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "hooks-demo.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "hooks-demo.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hooks-demo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

### Template Functions Explained

#### hooks-demo.name

**Purpose:** Returns the chart name with optional override

**Logic:**
```go
1. If .Values.nameOverride is set → use that
2. Otherwise → use .Chart.Name
3. Truncate to 63 characters (Kubernetes label limit)
4. Remove trailing hyphens
```

**Usage:**
```yaml
app.kubernetes.io/name: {{ include "hooks-demo.name" . }}
# Result: "hooks-demo"
```

**Why 63 characters:**
- Kubernetes label value limit
- DNS subdomain name limit
- Ensures compliance across all resources

#### hooks-demo.fullname

**Purpose:** Generates full resource names (combines release + chart name)

**Logic:**
```go
1. If .Values.fullnameOverride is set → use that
2. Else if release name contains chart name → use release name only
3. Else → combine release name + chart name
4. Truncate to 63 characters
5. Remove trailing hyphens
```

**Examples:**
```bash
# Release: my-app, Chart: hooks-demo
# Result: "my-app-hooks-demo"

# Release: hooks-demo, Chart: hooks-demo
# Result: "hooks-demo" (avoids duplication)

# With override
helm install --set fullnameOverride=custom-name
# Result: "custom-name"
```

**Why this pattern:**
- Avoids name collisions between releases
- Enables multiple installations in same namespace
- Follows Helm best practices

#### hooks-demo.labels

**Purpose:** Standard labels applied to all resources

**Generates:**
```yaml
helm.sh/chart: hooks-demo-0.1.0
app.kubernetes.io/name: hooks-demo
app.kubernetes.io/instance: my-release
app.kubernetes.io/managed-by: Helm
```

**Label explanations:**

**helm.sh/chart: hooks-demo-0.1.0**
- Tracks which chart version created the resource
- Format: `name-version`
- Plus signs replaced with underscores for DNS compliance

**app.kubernetes.io/name: hooks-demo**
- Application name (from chart)
- Part of Kubernetes recommended labels
- Used for filtering and grouping

**app.kubernetes.io/instance: my-release**
- Release name (unique per installation)
- Distinguishes multiple installations of same chart
- Critical for multi-tenant scenarios

**app.kubernetes.io/managed-by: Helm**
- Indicates Helm manages this resource
- Other values: `kubectl`, `kustomize`, etc.
- Useful for inventory and auditing

#### hooks-demo.selectorLabels

**Purpose:** Minimal labels used for pod selectors

**Generates:**
```yaml
app.kubernetes.io/name: hooks-demo
app.kubernetes.io/instance: my-release
```

**Why separate from full labels:**
- Pod selectors are **immutable** after creation
- Full labels include chart version (changes on upgrade)
- Selector labels must be stable across upgrades
- Using full labels would prevent updates

**Important:** Never use version info in selectors!

---

## 📄 templates/pre-install-job.yaml - Database Migration Hook

### Full File

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "hooks-demo.fullname" . }}-db-migrate
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "hooks-demo.labels" . | nindent 4 }}
    app.kubernetes.io/component: pre-install-hook
  annotations:
    # This annotation marks it as a Helm hook
    "helm.sh/hook": pre-install,pre-upgrade
    # Hook weight controls execution order (lower = runs first)
    "helm.sh/hook-weight": "0"
    # Delete the hook resource after it succeeds
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  backoffLimit: 3
  ttlSecondsAfterFinished: 120
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ include "hooks-demo.name" . }}
        app.kubernetes.io/component: db-migration
    spec:
      restartPolicy: Never
      containers:
        - name: db-migrate
          image: "{{ .Values.preInstall.image.repository }}:{{ .Values.preInstall.image.tag }}"
          command:
            - /bin/sh
            - -c
            - |
              echo "============================================"
              echo "  PRE-INSTALL HOOK: Database Migration"
              echo "============================================"
              echo ""
              echo "[$(date)] Starting database migration..."
              echo "[$(date)] Target database: {{ .Values.preInstall.dbHost }}/{{ .Values.preInstall.dbName }}"
              echo ""
              echo "[$(date)] Step 1/4: Checking database connectivity..."
              sleep 1
              echo "[$(date)] Step 1/4: Database connection OK"
              echo ""
              echo "[$(date)] Step 2/4: Creating backup of current schema..."
              sleep 1
              echo "[$(date)] Step 2/4: Backup created: backup_$(date +%Y%m%d_%H%M%S).sql"
              echo ""
              echo "[$(date)] Step 3/4: Applying migration scripts..."
              sleep {{ .Values.preInstall.migrationDuration }}
              echo "[$(date)] Step 3/4: Migration 001_create_users_table.sql ... OK"
              echo "[$(date)] Step 3/4: Migration 002_add_email_index.sql ... OK"
              echo "[$(date)] Step 3/4: Migration 003_create_orders_table.sql ... OK"
              echo ""
              echo "[$(date)] Step 4/4: Verifying schema integrity..."
              sleep 1
              echo "[$(date)] Step 4/4: Schema verification passed"
              echo ""
              echo "============================================"
              echo "  Database migration completed successfully!"
              echo "  Applied 3 migrations in {{ .Values.preInstall.migrationDuration }}s"
              echo "============================================"
```

### Hook Annotations - The Key to Hook Behavior

#### "helm.sh/hook": pre-install,pre-upgrade

**What it is:** Tells Helm when to run this hook

**Multiple values:** Comma-separated list of hook types

**Supported values:**
- `pre-install` - Before any resources are created during install
- `post-install` - After all resources are created during install
- `pre-upgrade` - Before any resources are updated during upgrade
- `post-upgrade` - After all resources are updated during upgrade
- `pre-rollback` - Before any resources are restored during rollback
- `post-rollback` - After all resources are restored during rollback
- `pre-delete` - Before any resources are deleted during uninstall
- `post-delete` - After all resources are deleted during uninstall
- `test` - When `helm test` is run

**Why pre-install,pre-upgrade:**
```yaml
pre-install   → Run before first deployment
pre-upgrade   → Run before each update
# Ensures database migrations run before app starts, always
```

**Common patterns:**
```yaml
# Database migrations - always run before deployment
"helm.sh/hook": pre-install,pre-upgrade

# Smoke tests - always run after deployment
"helm.sh/hook": post-install,post-upgrade

# Cleanup - only run before deletion
"helm.sh/hook": pre-delete
```

**What happens:**
1. Helm renders this template like any other
2. Sees the hook annotation
3. Separates it from main resources
4. Creates it at the specified lifecycle point
5. Waits for completion before proceeding

#### "helm.sh/hook-weight": "0"

**What it is:** Controls execution order when multiple hooks exist

**Type:** String (not integer)

**Range:** Any integer value (negative to positive)

**Lower weight runs first:**
```yaml
Hook A: weight: "-5"  → Runs 1st
Hook B: weight: "0"   → Runs 2nd
Hook C: weight: "10"  → Runs 3rd
```

**Default:** If not specified, weight is `0`

**Use cases:**

**Multiple migrations:**
```yaml
# schema-migration.yaml
"helm.sh/hook-weight": "0"   # Schema first

# data-migration.yaml
"helm.sh/hook-weight": "10"  # Data second
```

**Ordered setup:**
```yaml
# create-namespace.yaml
"helm.sh/hook-weight": "-10"

# create-secrets.yaml
"helm.sh/hook-weight": "-5"

# db-migration.yaml
"helm.sh/hook-weight": "0"
```

**Why "0" for this hook:**
- It's the only pre-install hook
- Default value works fine
- Good baseline for future hooks

**Best practices:**
- Use increments of 5 or 10 (room for insertion)
- Negative weights for setup
- Positive weights for validation
- Document weight rationale in comments

#### "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded

**What it is:** Controls when Helm deletes the hook resource

**Multiple policies:** Comma-separated list (OR logic)

**Available policies:**

| Policy | When It Triggers | Use Case |
|--------|-----------------|----------|
| `before-hook-creation` | Before running hook again | Update hooks each install |
| `hook-succeeded` | After hook completes successfully | Cleanup successful runs |
| `hook-failed` | After hook fails | Cleanup failed attempts |
| `manual` | Never (manual deletion required) | Inspect all runs |

**Our policy: before-hook-creation,hook-succeeded**

**Behavior:**
```bash
# First install
helm install app ./chart
→ Creates pre-install-job
→ Job succeeds
→ Helm deletes Job (hook-succeeded)

# Upgrade
helm upgrade app ./chart
→ No Job exists (was deleted)
→ Creates new pre-install-job
→ Job succeeds
→ Helm deletes Job (hook-succeeded)

# Upgrade again (if Job wasn't deleted)
helm upgrade app ./chart
→ Old Job exists
→ Helm deletes old Job (before-hook-creation)
→ Creates new Job
→ Job succeeds
→ Helm deletes Job (hook-succeeded)
```

**Why this combination:**
- Keeps cluster clean (auto-deletes on success)
- Handles re-runs gracefully (deletes old before creating new)
- Failed runs remain for debugging (not deleted by hook-failed)

**Alternative policies:**

**Keep for inspection:**
```yaml
"helm.sh/hook-delete-policy": before-hook-creation
# Keeps successful runs, deletes only before next run
```

**Always cleanup:**
```yaml
"helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded,hook-failed
# Deletes regardless of outcome
```

**Never cleanup:**
```yaml
"helm.sh/hook-delete-policy": ""
# Manual kubectl delete required
```

### Job Specification

#### apiVersion: batch/v1

**What it is:** Kubernetes Job API version

**Stable since:** Kubernetes 1.8+

**Alternative:** `batch/v1beta1` (older clusters)

#### kind: Job

**What it is:** Kubernetes Job resource

**Why Job vs Pod:**
- ✅ Jobs track completion status
- ✅ Jobs handle retries automatically
- ✅ Jobs support backoff limits
- ✅ Jobs clean up Pods on completion
- ✅ Helm waits for Job completion

**When to use Pod:**
- Quick tasks (no retry needed)
- Debugging purposes
- Very simple scripts

#### metadata

**name: {{ include "hooks-demo.fullname" . }}-db-migrate**

**Template breakdown:**
```bash
# Release: my-app
# Result: "my-app-hooks-demo-db-migrate"
```

**Suffix: -db-migrate**
- Descriptive suffix
- Distinguishes from post-install hook
- Max 63 characters total

**namespace: {{ .Release.Namespace }}**
- Deployed to same namespace as release
- `.Release.Namespace` from helm install -n
- Default: `default`

**labels**
- Includes standard labels from `_helpers.tpl`
- Additional: `app.kubernetes.io/component: pre-install-hook`
- Used for filtering: `kubectl get jobs -l app.kubernetes.io/component=pre-install-hook`

#### spec.backoffLimit: 3

**What it is:** Maximum number of retry attempts

**How it works:**
```
Attempt 1: Job fails
  → Wait (exponential backoff)
Attempt 2: Job fails
  → Wait (longer)
Attempt 3: Job fails
  → Wait (longer)
Attempt 4: Job fails
  → Job marked permanently failed (backoffLimit reached)
```

**Default:** 6 (if not specified)

**Why 3:**
- Enough retries for transient issues
- Not too many (avoids delaying deployment)
- Balance between resilience and speed

**Production considerations:**
- Lower (1-2) for fast failures
- Higher (5+) for flaky networks
- 0 for no retries

#### spec.ttlSecondsAfterFinished: 120

**What it is:** Seconds to keep Job after completion before automatic deletion

**Behavior:**
```bash
Job completes at 10:00:00
↓
TTL controller waits 120 seconds
↓
Job auto-deleted at 10:02:00 (including pods)
```

**Why 120 seconds:**
- Enough time to inspect logs if needed
- Not too long (prevents cluster clutter)
- Pairs with `hook-succeeded` delete policy

**Important:** TTL controller must be enabled (default in most clusters)

**Production values:**
- `60` - Fast cleanup
- `300` - More inspection time
- `null` - Disable TTL (manual cleanup)

#### spec.template.spec.restartPolicy: Never

**What it is:** What to do when container exits

**Options:**
- `Never` - Don't restart, mark Pod as failed (Jobs)
- `OnFailure` - Restart container on failure (Jobs)
- `Always` - Always restart (Deployments)

**Why Never:**
- Clear failure signaling
- Job handles retries at Pod level (backoffLimit)
- Container restarts would be hidden retries
- Clean logs (one attempt per pod)

**Alternative: OnFailure**
```yaml
restartPolicy: OnFailure
# Container restarts inside same Pod
# Logs remain in same pod (harder to debug)
```

### Container Specification

#### image

**Template:**
```yaml
image: "{{ .Values.preInstall.image.repository }}:{{ .Values.preInstall.image.tag }}"
```

**Renders to:**
```yaml
image: "busybox:1.36"
```

**Why busybox:**
- Tiny (1-5 MB)
- Contains shell for scripting
- Standard Unix utilities
- Fast to pull and start

**Production alternatives:**
```yaml
# Dedicated migration image
image: "myapp/migrations:v1.2.3"

# Database client image
image: "postgres:16-alpine"

# Custom tooling image
image: "mycompany/db-tools:latest"
```

#### command

**What it is:** Overrides container's default ENTRYPOINT

**Format:**
```yaml
command:
  - /bin/sh          # Shell interpreter
  - -c               # Execute following string
  - |                # Multi-line YAML literal block
    # Script content here
```

**Why this format:**
- Multi-line scripts are readable
- YAML literal block (`|`) preserves formatting
- Shell interpreter for advanced scripting
- Inline script (no external files needed)

### Migration Script Breakdown

The script demonstrates a realistic database migration flow:

#### Step 1: Database Connectivity Check

```bash
echo "[$(date)] Step 1/4: Checking database connectivity..."
sleep 1
echo "[$(date)] Step 1/4: Database connection OK"
```

**In production:**
```bash
# PostgreSQL
pg_isready -h $DB_HOST -p 5432 -U $DB_USER

# MySQL
mysqladmin ping -h $DB_HOST -u $DB_USER -p$DB_PASSWORD

# Generic
nc -zv $DB_HOST 5432
```

#### Step 2: Backup Creation

```bash
echo "[$(date)] Step 2/4: Creating backup of current schema..."
echo "[$(date)] Step 2/4: Backup created: backup_$(date +%Y%m%d_%H%M%S).sql"
```

**In production:**
```bash
# PostgreSQL dump
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql

# Upload to S3
aws s3 cp backup.sql s3://backups/db/$(date +%Y%m%d)_${RELEASE_NAME}.sql
```

#### Step 3: Apply Migrations

```bash
echo "[$(date)] Step 3/4: Applying migration scripts..."
sleep {{ .Values.preInstall.migrationDuration }}
echo "[$(date)] Step 3/4: Migration 001_create_users_table.sql ... OK"
```

**In production with migration tools:**

**Flyway:**
```bash
flyway -url=jdbc:postgresql://$DB_HOST/$DB_NAME \
       -user=$DB_USER \
       -password=$DB_PASSWORD \
       migrate
```

**Liquibase:**
```bash
liquibase --url=jdbc:postgresql://$DB_HOST/$DB_NAME \
          --username=$DB_USER \
          --password=$DB_PASSWORD \
          update
```

**Alembic (Python):**
```bash
alembic upgrade head
```

**Custom SQL:**
```bash
for migration in /migrations/*.sql; do
  psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f $migration
  if [ $? -ne 0 ]; then
    echo "Migration failed: $migration"
    exit 1
  fi
done
```

#### Step 4: Schema Verification

```bash
echo "[$(date)] Step 4/4: Verifying schema integrity..."
echo "[$(date)] Step 4/4: Schema verification passed"
```

**In production:**
```bash
# Check table exists
psql -c "SELECT COUNT(*) FROM users;" > /dev/null
if [ $? -ne 0 ]; then
  echo "Migration verification failed"
  exit 1
fi

# Verify indexes
psql -c "SELECT indexname FROM pg_indexes WHERE tablename='users';"
```

---

## 📄 templates/post-install-job.yaml - Smoke Test Hook

### Full File

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "hooks-demo.fullname" . }}-smoke-test
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "hooks-demo.labels" . | nindent 4 }}
    app.kubernetes.io/component: post-install-hook
  annotations:
    # This hook runs AFTER all resources are created
    "helm.sh/hook": post-install,post-upgrade
    # Higher weight means it runs after lower-weight post-install hooks
    "helm.sh/hook-weight": "5"
    # Keep the hook resource around after it succeeds (for log inspection)
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  backoffLimit: 2
  ttlSecondsAfterFinished: 300
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ include "hooks-demo.name" . }}
        app.kubernetes.io/component: smoke-test
    spec:
      restartPolicy: Never
      containers:
        - name: smoke-test
          image: "{{ .Values.postInstall.image.repository }}:{{ .Values.postInstall.image.tag }}"
          command:
            - /bin/sh
            - -c
            - |
              echo "============================================"
              echo "  POST-INSTALL HOOK: Smoke Tests"
              echo "============================================"
              echo ""
              echo "[$(date)] Running post-deployment smoke tests..."
              echo "[$(date)] Target endpoint: {{ .Values.postInstall.testEndpoint }}"
              echo ""
              echo "[$(date)] Test 1/4: Service DNS resolution..."
              sleep 1
              echo "[$(date)] Test 1/4: PASSED - Service resolves correctly"
              echo ""
              echo "[$(date)] Test 2/4: HTTP connectivity check..."
              sleep 1
              # Try to reach the service (may or may not work depending on timing)
              if wget -q -O /dev/null --timeout=5 {{ .Values.postInstall.testEndpoint }} 2>/dev/null; then
                echo "[$(date)] Test 2/4: PASSED - HTTP 200 OK"
              else
                echo "[$(date)] Test 2/4: PASSED - Service endpoint registered (pods still starting)"
              fi
              echo ""
              echo "[$(date)] Test 3/4: Deployment replica count..."
              sleep 1
              echo "[$(date)] Test 3/4: PASSED - Expected replicas scheduled"
              echo ""
              echo "[$(date)] Test 4/4: Configuration validation..."
              sleep {{ .Values.postInstall.testDuration }}
              echo "[$(date)] Test 4/4: PASSED - Configuration is valid"
              echo ""
              echo "============================================"
              echo "  Smoke tests completed: 4/4 PASSED"
              echo "  Deployment is healthy!"
              echo "============================================"
```

### Key Differences from Pre-Install Hook

#### "helm.sh/hook": post-install,post-upgrade

**When it runs:** AFTER all main resources are created

**Execution order:**
```
1. Pre-install hooks complete
2. Deployment, Service created
3. Post-install hooks run ← This hook
4. Release marked "deployed"
```

**Why post-install,post-upgrade:**
- Validate deployment succeeded
- Test that application is responding
- Verify configuration is correct
- Catch issues before marking release as deployed

#### "helm.sh/hook-weight": "5"

**Why 5 instead of 0:**
- Runs after other post-install hooks with weight 0
- Allows multiple validation phases
- Room for insertion (weight 1-4)

**Example multi-hook scenario:**
```yaml
# basic-health-check.yaml
"helm.sh/hook-weight": "0"   # Quick check runs first

# smoke-tests.yaml
"helm.sh/hook-weight": "5"   # Detailed tests run second

# integration-tests.yaml
"helm.sh/hook-weight": "10"  # Full tests run last
```

#### "helm.sh/hook-delete-policy": before-hook-creation

**Only one policy:** Not combined with `hook-succeeded`

**Behavior:**
```bash
# First install
helm install app ./chart
→ Creates smoke-test Job
→ Job succeeds
→ Job REMAINS (not deleted)
→ Can inspect logs: kubectl logs job/app-smoke-test

# Upgrade
helm upgrade app ./chart
→ Old Job exists
→ Helm DELETES old Job (before-hook-creation)
→ Creates new Job
→ New Job succeeds
→ New Job REMAINS
```

**Why keep the Job:**
- Inspection of test results
- Debugging failed deployments
- Audit trail of validation
- View logs without watching during install

**Trade-off:**
- ✅ Better observability
- ❌ Requires periodic cleanup
- ❌ More cluster resources used

#### spec.backoffLimit: 2

**Why 2 instead of 3:**
- Smoke tests should be reliable
- Fewer retries for faster feedback
- If tests fail twice, likely real issue

#### spec.ttlSecondsAfterFinished: 300

**Why 300 (5 minutes) instead of 120:**
- More time to inspect test results
- Allows team to review logs
- Not critical to clean up quickly
- Balanced with `before-hook-creation` policy

### Smoke Test Script Breakdown

#### Test 1: Service DNS Resolution

```bash
echo "[$(date)] Test 1/4: Service DNS resolution..."
```

**In production:**
```bash
# Test DNS resolution
nslookup hooks-demo
if [ $? -ne 0 ]; then
  echo "FAILED: Service DNS not resolving"
  exit 1
fi

# Test with dig (more detailed)
dig hooks-demo +short
```

#### Test 2: HTTP Connectivity

```bash
if wget -q -O /dev/null --timeout=5 {{ .Values.postInstall.testEndpoint }} 2>/dev/null; then
  echo "[$(date)] Test 2/4: PASSED - HTTP 200 OK"
else
  echo "[$(date)] Test 2/4: PASSED - Service endpoint registered (pods still starting)"
fi
```

**Important:** This test is graceful (doesn't fail)

**Why:**
- Pods may still be starting (rollout in progress)
- Service created but pods not ready yet
- Helm waits for hooks, not Deployments
- Use `--wait` flag for Deployment readiness

**Production HTTP tests:**
```bash
# Test with curl
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $ENDPOINT)
if [ $HTTP_CODE -ne 200 ]; then
  echo "FAILED: Expected 200, got $HTTP_CODE"
  exit 1
fi

# Test with retry logic
for i in {1..30}; do
  if curl -s -f $ENDPOINT > /dev/null; then
    echo "PASSED: Service responding"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "FAILED: Service not responding after 30 attempts"
    exit 1
  fi
  sleep 2
done

# Test specific endpoint
curl -s $ENDPOINT/health | jq -e '.status == "healthy"'
```

#### Test 3: Deployment Replica Count

```bash
echo "[$(date)] Test 3/4: Deployment replica count..."
echo "[$(date)] Test 3/4: PASSED - Expected replicas scheduled"
```

**In production:**
```bash
# Check replica count with kubectl
EXPECTED_REPLICAS={{ .Values.replicaCount }}
ACTUAL_REPLICAS=$(kubectl get deployment {{ include "hooks-demo.fullname" . }} \
                  -n {{ .Release.Namespace }} \
                  -o jsonpath='{.status.availableReplicas}')

if [ "$ACTUAL_REPLICAS" -ne "$EXPECTED_REPLICAS" ]; then
  echo "FAILED: Expected $EXPECTED_REPLICAS replicas, found $ACTUAL_REPLICAS"
  exit 1
fi

# Check all pods are ready
READY_REPLICAS=$(kubectl get deployment {{ include "hooks-demo.fullname" . }} \
                 -n {{ .Release.Namespace }} \
                 -o jsonpath='{.status.readyReplicas}')

if [ "$READY_REPLICAS" -ne "$EXPECTED_REPLICAS" ]; then
  echo "FAILED: Not all replicas ready"
  exit 1
fi
```

#### Test 4: Configuration Validation

```bash
echo "[$(date)] Test 4/4: Configuration validation..."
echo "[$(date)] Test 4/4: PASSED - Configuration is valid"
```

**In production:**
```bash
# Test environment variables are set
curl -s $ENDPOINT/config | jq -e '.database.host != ""'

# Test required resources exist
kubectl get configmap {{ include "hooks-demo.fullname" . }}-config \
  -n {{ .Release.Namespace }}

# Test secrets are mounted
kubectl exec deploy/{{ include "hooks-demo.fullname" . }} \
  -n {{ .Release.Namespace }} \
  -- test -f /secrets/db-password
```

---

## 📄 templates/deployment.yaml - Main Application

### Full File

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "hooks-demo.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "hooks-demo.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "hooks-demo.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "hooks-demo.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 80
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

### Key Points

This is a **standard Deployment** with no hook annotations.

**Important:** It's created BETWEEN pre-install and post-install hooks:

```
1. Pre-install hook (db-migrate) runs
   ↓
2. Deployment created ← This file
   ↓
3. Service created
   ↓
4. Post-install hook (smoke-test) runs
```

### Probes Explained

#### livenessProbe

**Purpose:** Determines if container is alive

**Action on failure:** Kubelet kills and restarts container

**Settings:**
- `initialDelaySeconds: 5` - Wait 5s before first probe
- `periodSeconds: 10` - Probe every 10s

**Why these values:**
- nginx starts quickly (5s is enough)
- 10s gives time to recover from transient issues

#### readinessProbe

**Purpose:** Determines if container is ready to receive traffic

**Action on failure:** Remove pod from Service endpoints

**Settings:**
- `initialDelaySeconds: 3` - Probe sooner than liveness
- `periodSeconds: 5` - More frequent than liveness

**Why different from liveness:**
- Ready state changes more frequently
- Don't want to kill container for temporary issues
- Quick removal from load balancer

---

## 📄 templates/service.yaml - Application Service

### Full File

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "hooks-demo.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "hooks-demo.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "hooks-demo.selectorLabels" . | nindent 4 }}
```

### Key Points

**No hook annotations:** Created at normal time (after pre-install hooks)

**selector:**
```yaml
selector:
  app.kubernetes.io/name: hooks-demo
  app.kubernetes.io/instance: my-release
```

**Matches pods from Deployment:**
```yaml
# In Deployment template.metadata.labels
app.kubernetes.io/name: hooks-demo
app.kubernetes.io/instance: my-release
```

**Used by post-install hook:**
```yaml
# Hook can access service by name
testEndpoint: "http://hooks-demo:80"
```

---

## 🔧 How Components Work Together

### Complete Flow Diagram

```
helm install hooks-demo ./05-helm-hooks/ -n helm-scenarios

1. Render Phase
   ├─ Process templates/pre-install-job.yaml
   │    → Sees "helm.sh/hook: pre-install"
   │    → Separates from main resources
   │
   ├─ Process templates/deployment.yaml
   │    → No hook annotation
   │    → Queued as main resource
   │
   ├─ Process templates/service.yaml
   │    → No hook annotation
   │    → Queued as main resource
   │
   └─ Process templates/post-install-job.yaml
        → Sees "helm.sh/hook: post-install"
        → Separates from main resources

2. Pre-Install Phase
   ├─ Create Job: hooks-demo-db-migrate
   ├─ Wait for completion (up to timeout)
   ├─ Job Pod runs migration script
   ├─ Script completes successfully (exit 0)
   ├─ Job status: Complete
   └─ Helm deletes Job (hook-delete-policy: hook-succeeded)

3. Resource Creation Phase
   ├─ Create Deployment: hooks-demo
   │    ├─ ReplicaSet created
   │    └─ 2 Pods created (replicaCount: 2)
   │
   └─ Create Service: hooks-demo
        └─ Endpoints updated with pod IPs

4. Post-Install Phase
   ├─ Create Job: hooks-demo-smoke-test
   ├─ Wait for completion (up to timeout)
   ├─ Job Pod runs smoke tests
   │    ├─ Test 1: DNS resolution ✓
   │    ├─ Test 2: HTTP connectivity ✓
   │    ├─ Test 3: Replica count ✓
   │    └─ Test 4: Configuration ✓
   ├─ Script completes successfully (exit 0)
   ├─ Job status: Complete
   └─ Job REMAINS (hook-delete-policy: before-hook-creation only)

5. Finalization
   └─ Release marked "deployed"
```

### Timing Example

```
00:00 - helm install command issued
00:01 - Templates rendered
00:01 - Pre-install Job created
00:02 - Pre-install Job Pod running
00:07 - Pre-install Job completed (5s migration + 2s other)
00:07 - Pre-install Job deleted (hook-succeeded policy)
00:08 - Deployment created
00:08 - Service created
00:09 - Deployment Pods starting
00:09 - Post-install Job created
00:10 - Post-install Job Pod running
00:14 - Post-install Job completed (3s test + 1s other)
00:14 - Post-install Job remains
00:14 - Release marked "deployed"
```

### Value Flow

```yaml
# values.yaml
preInstall:
  migrationDuration: 5
  dbHost: "postgres.database.svc"

postInstall:
  testDuration: 3
  testEndpoint: "http://hooks-demo:80"

# templates/pre-install-job.yaml
sleep {{ .Values.preInstall.migrationDuration }}
# Renders to: sleep 5

echo "Target: {{ .Values.preInstall.dbHost }}"
# Renders to: Target: postgres.database.svc

# templates/post-install-job.yaml
sleep {{ .Values.postInstall.testDuration }}
# Renders to: sleep 3

wget {{ .Values.postInstall.testEndpoint }}
# Renders to: wget http://hooks-demo:80
```

---

## 🛠️ Practical Use Cases

### 1. Database Migrations

**Problem:** Need to update database schema before new app version starts

**Solution:**
```yaml
# templates/pre-upgrade-migration.yaml
annotations:
  "helm.sh/hook": pre-upgrade
  "helm.sh/hook-weight": "0"
  "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
command:
  - /app/migrate
  - --from=$(CURRENT_VERSION)
  - --to=$(NEW_VERSION)
```

**Best practices:**
- Always create backup first
- Use idempotent migrations
- Test rollback scenarios
- Set reasonable timeout

### 2. Data Initialization

**Problem:** First install needs seed data

**Solution:**
```yaml
# templates/post-install-seed.yaml
annotations:
  "helm.sh/hook": post-install  # Only on install
  "helm.sh/hook-weight": "10"
command:
  - /app/seed-data
  - --admin-email=$(ADMIN_EMAIL)
```

**Why post-install only:**
- Don't reseed on every upgrade
- Data already exists after first install

### 3. External Service Registration

**Problem:** Register application with external service discovery

**Solution:**
```yaml
# templates/post-install-register.yaml
annotations:
  "helm.sh/hook": post-install,post-upgrade
  "helm.sh/hook-weight": "10"
command:
  - curl
  - -X POST
  - http://service-registry/register
  - -d '{"name":"{{ .Release.Name }}","url":"{{ .Values.service.url }}"}'
```

### 4. Certificate Generation

**Problem:** Generate TLS certificates before ingress is created

**Solution:**
```yaml
# templates/pre-install-cert.yaml
annotations:
  "helm.sh/hook": pre-install
  "helm.sh/hook-weight": "-10"
command:
  - certbot
  - certonly
  - --standalone
  - -d {{ .Values.ingress.hostname }}
```

### 5. Cache Warming

**Problem:** Warm up cache after deployment

**Solution:**
```yaml
# templates/post-install-warm-cache.yaml
annotations:
  "helm.sh/hook": post-install,post-upgrade
  "helm.sh/hook-weight": "20"  # Run after smoke tests
command:
  - /app/warm-cache
  - --url={{ .Values.service.url }}
```

### 6. Backup Before Delete

**Problem:** Backup data before uninstalling application

**Solution:**
```yaml
# templates/pre-delete-backup.yaml
annotations:
  "helm.sh/hook": pre-delete
  "helm.sh/hook-weight": "0"
  "helm.sh/hook-delete-policy": before-hook-creation
command:
  - /app/backup
  - --output=s3://backups/{{ .Release.Name }}-$(date +%Y%m%d)
```

---

## 🚨 Troubleshooting

### Hook Fails During Install

**Symptoms:**
```bash
helm install myapp ./chart
Error: pre-install hook failed: Job failed: BackoffLimitExceeded
```

**Diagnosis:**
```bash
# Find hook Jobs
kubectl get jobs -n <namespace> -l app.kubernetes.io/instance=<release>

# Check Job status
kubectl describe job <hook-job-name> -n <namespace>

# View hook logs
kubectl logs job/<hook-job-name> -n <namespace>

# Check hook Pod events
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

**Common causes:**
1. **Script error** - Exit code non-zero
2. **Missing dependencies** - Database not ready
3. **Timeout** - Hook took too long
4. **Image pull error** - Wrong image or credentials
5. **Resource constraints** - Insufficient CPU/memory

**Solutions:**
```bash
# Increase timeout
helm install --timeout 10m

# Increase backoff limit
spec:
  backoffLimit: 5

# Add retry logic in script
for i in {1..10}; do
  if pg_isready; then break; fi
  sleep 5
done

# Check dependencies in script
until nc -z postgres 5432; do
  echo "Waiting for database..."
  sleep 2
done
```

### Hook Stuck in Running State

**Symptoms:**
```bash
helm install myapp ./chart
# Hangs indefinitely
^C
```

**Diagnosis:**
```bash
# Check if hook is running
kubectl get jobs -n <namespace>

# Check pod status
kubectl get pods -n <namespace> -l job-name=<hook-job>

# View logs
kubectl logs -f <hook-pod> -n <namespace>
```

**Common causes:**
1. **Infinite loop** - Script never exits
2. **Waiting for input** - Script expects user input
3. **Container not starting** - Image issues
4. **Resource quotas** - Can't schedule pod

**Solutions:**
```bash
# Kill stuck hook manually
kubectl delete job <hook-job> -n <namespace>

# Install with increased timeout
helm install --timeout 15m

# Add explicit timeout in script
timeout 300 /app/migration.sh

# Debug interactively
kubectl run debug --rm -it --image=busybox -- sh
```

### Hook Deleted Before Inspection

**Problem:** Can't see hook logs because Job was auto-deleted

**Solution:**
```yaml
# Change delete policy to keep Job
annotations:
  "helm.sh/hook-delete-policy": before-hook-creation
  # Removed: hook-succeeded

# Or disable TTL
spec:
  ttlSecondsAfterFinished: null

# Or increase TTL
spec:
  ttlSecondsAfterFinished: 3600  # 1 hour
```

**Retrieve logs immediately:**
```bash
# Watch during install
helm install myapp ./chart &
sleep 5
kubectl logs -f job/<hook-job> -n <namespace>
```

### Upgrade Fails Due to Old Hook

**Symptoms:**
```bash
helm upgrade myapp ./chart
Error: cannot patch "myapp-db-migrate" with kind Job
```

**Cause:** Old hook exists and `before-hook-creation` policy not set

**Solutions:**
```bash
# Delete old hook manually
kubectl delete job myapp-db-migrate -n <namespace>

# Then retry upgrade
helm upgrade myapp ./chart

# Or add to hook template
annotations:
  "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
```

### Hook Runs When It Shouldn't

**Problem:** Pre-install hook runs on upgrade

**Check annotations:**
```yaml
# Wrong - runs on both
"helm.sh/hook": pre-install,pre-upgrade

# Correct - only on install
"helm.sh/hook": pre-install
```

**Conditional hooks:**
```yaml
# Only create hook on install
{{- if .Release.IsInstall }}
apiVersion: batch/v1
kind: Job
# ... hook spec
{{- end }}
```

### Multiple Hooks Wrong Order

**Problem:** Hooks run in unexpected order

**Check weights:**
```bash
# View all hooks
helm get manifest <release> -n <namespace> | grep -A5 "helm.sh/hook"

# Ensure weights are ordered
Hook A: weight "0"   # First
Hook B: weight "5"   # Second
Hook C: weight "10"  # Third
```

**Fix:**
```yaml
# Use consistent increments
annotations:
  "helm.sh/hook-weight": "0"   # Setup
  "helm.sh/hook-weight": "10"  # Main task
  "helm.sh/hook-weight": "20"  # Validation
```

---

## ✅ Best Practices

### 1. Always Set Delete Policy

```yaml
# ❌ Bad - Hook lingers forever
annotations:
  "helm.sh/hook": post-install

# ✅ Good - Auto-cleanup
annotations:
  "helm.sh/hook": post-install
  "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
```

### 2. Use Appropriate Weights

```yaml
# ✅ Good - Leaves room for insertion
"helm.sh/hook-weight": "-10"  # Namespace
"helm.sh/hook-weight": "-5"   # Secrets
"helm.sh/hook-weight": "0"    # Schema migration
"helm.sh/hook-weight": "10"   # Data migration
"helm.sh/hook-weight": "20"   # Validation

# ❌ Bad - No room to insert between
"helm.sh/hook-weight": "0"
"helm.sh/hook-weight": "1"
"helm.sh/hook-weight": "2"
```

### 3. Set Realistic Timeouts

```yaml
# For migrations
spec:
  backoffLimit: 1  # Don't retry migrations
  activeDeadlineSeconds: 600  # 10 minutes max

# For smoke tests
spec:
  backoffLimit: 2  # Retry flaky tests
  activeDeadlineSeconds: 120  # 2 minutes max
```

### 4. Use Idempotent Scripts

```bash
# ✅ Good - Can run multiple times
if ! table_exists("users"); then
  create_table("users")
fi

# ❌ Bad - Fails on retry
create_table("users")  # Fails if exists
```

### 5. Provide Clear Logging

```bash
# ✅ Good - Detailed, timestamped
echo "[$(date)] Starting migration..."
echo "[$(date)] Applying 001_create_users.sql"
echo "[$(date)] Migration complete"

# ❌ Bad - No context
echo "Running"
echo "Done"
```

### 6. Handle Failures Gracefully

```bash
# ✅ Good - Explicit failure
if ! pg_isready; then
  echo "ERROR: Database not ready"
  exit 1
fi

# ❌ Bad - Silent failure
pg_isready
# Continues even if fails
```

### 7. Test Hooks Independently

```bash
# Test hook without installing
helm template myapp ./chart -s templates/pre-install-job.yaml | kubectl apply -f -

# Watch Job
kubectl get jobs -w

# View logs
kubectl logs job/myapp-db-migrate
```

### 8. Document Hook Behavior

```yaml
# ✅ Good - Clear documentation
annotations:
  "helm.sh/hook": pre-install,pre-upgrade
  "helm.sh/hook-weight": "0"
  "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
  # Runs database migrations before deployment
  # Cleaned up after success
  # Retries up to 3 times
```

### 9. Version Hook Images

```yaml
# ✅ Good - Pinned version
image: "myapp/migrations:v1.2.3"

# ❌ Bad - Unpredictable
image: "myapp/migrations:latest"
```

### 10. Consider Rollback Scenarios

```bash
# Include rollback logic
if [ "$OPERATION" = "rollback" ]; then
  echo "Running rollback migrations"
  /app/migrate-down
else
  echo "Running forward migrations"
  /app/migrate-up
fi
```

---

## 📚 Further Reading

### Official Documentation

- [Helm Hooks Documentation](https://helm.sh/docs/topics/charts_hooks/)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Kubernetes Pods Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)

### Hook Types Reference

| Hook | Phase | Use Case |
|------|-------|----------|
| `pre-install` | Before resource creation | Setup, migrations |
| `post-install` | After resource creation | Validation, tests |
| `pre-delete` | Before resource deletion | Backup, cleanup |
| `post-delete` | After resource deletion | External cleanup |
| `pre-upgrade` | Before resource update | Backup, validation |
| `post-upgrade` | After resource update | Tests, warming |
| `pre-rollback` | Before rollback | Snapshot state |
| `post-rollback` | After rollback | Validation |
| `test` | Manual test run | Integration tests |

### Delete Policy Reference

| Policy | Trigger | Best For |
|--------|---------|----------|
| `before-hook-creation` | Before creating new hook | Updates |
| `hook-succeeded` | After successful completion | Cleanup |
| `hook-failed` | After failure | Cleanup |
| (empty) | Never | Inspection |

### Hook Weight Patterns

```yaml
# Infrastructure setup
-20 to -10: Namespaces, RBAC, network policies
-10 to -1:  Secrets, ConfigMaps, PVCs

# Data operations
0 to 10:    Schema migrations
10 to 20:   Data migrations

# Validation
20 to 30:   Smoke tests
30 to 40:   Integration tests

# Finalization
40 to 50:   Notifications, registration
```

### Common Pitfalls

1. **Forgetting delete policy** → Cluster clutter
2. **Not testing rollback** → Failed rollbacks
3. **Missing error handling** → Silent failures
4. **Hardcoded values** → Not reusable
5. **No timeout** → Hung installs
6. **Wrong hook type** → Runs at wrong time
7. **Dependencies not ready** → Flaky hooks
8. **No logging** → Hard to debug
9. **Not idempotent** → Fails on retry
10. **Testing only in helm** → Miss kubectl issues

---

## 🎓 Summary

Helm hooks provide powerful lifecycle management for your releases:

- **Pre-install/upgrade hooks** prepare your environment (migrations, setup)
- **Post-install/upgrade hooks** validate your deployment (tests, checks)
- **Pre-delete hooks** perform cleanup (backups, graceful shutdown)
- **Hook weights** control execution order
- **Delete policies** manage hook lifecycle
- **Jobs** are the most common hook resource type

By mastering hooks, you can build robust, automated deployment workflows that handle complex dependencies and ensure your applications are deployed safely and reliably.
