# Helm Secrets Management - Complete YAML Explanation

This guide provides a comprehensive, field-by-field explanation of secrets management in Helm, covering insecure practices, the lookup function, and production-ready approaches like sealed-secrets.

---

## 🎯 What is Secrets Management in Helm?

**Secrets management** is the practice of safely handling sensitive data (passwords, API keys, certificates) in your Helm charts without exposing them to unauthorized access or version control systems.

### The Fundamental Problem

Helm charts often need secrets, but there are serious security challenges:

1. **Helm Release History** - All values (including secrets) are stored in cluster as Kubernetes Secrets
2. **Git Repositories** - Values files with secrets get committed to version control
3. **Base64 is NOT Encryption** - Kubernetes Secrets are only base64-encoded
4. **--set Flags are Persistent** - Values passed via --set are stored in Helm release metadata

### Security Impact

```
User passes secret via:          Stored in:
--set secret.password=xxx   →    Helm release secret (visible with helm get values)
values.yaml in Git          →    Version control history (permanent record)
values.yaml as file         →    Helm release secret + potentially in CI/CD logs
```

**Result:** Your "secret" password may be stored in 3+ places, all accessible to anyone with cluster access.

---

## 📊 Secrets Management Approaches (Security Comparison)

| Approach | Security Level | GitOps Compatible | Ease of Use | Production Ready |
|----------|---------------|-------------------|-------------|------------------|
| `helm install --set secret=xxx` | ⚠️ Very Poor | ❌ No | ✅ Very Easy | ❌ Never |
| Secrets in values.yaml | ⚠️ Very Poor | ❌ No | ✅ Easy | ❌ Never |
| Environment variables | ⚠️ Poor | ❌ No | ✅ Easy | ❌ No |
| Helm lookup function | ⚡ Medium | ⚠️ Partial | ⚡ Medium | ⚠️ Limited |
| Sealed Secrets | ✅ High | ✅ Yes | ⚡ Medium | ✅ Yes |
| External Secrets Operator | ✅ High | ✅ Yes | ⚡ Medium | ✅ Yes |
| CSI Secret Store Driver | ✅ Very High | ✅ Yes | ⚠️ Complex | ✅ Yes |
| HashiCorp Vault + Injector | ✅ Very High | ✅ Yes | ⚠️ Complex | ✅ Yes |

**This scenario demonstrates the first four approaches and explains why production needs the last four.**

---

## 📄 Chart.yaml - Field-by-Field Breakdown

```yaml
apiVersion: v2
name: secrets-demo
description: A Helm chart demonstrating secrets management patterns and best practices
type: application
version: 0.1.0
appVersion: "1.0.0"
```

### apiVersion: v2

**What it is:** Helm chart API version

**Values:**
- `v1` - Helm 2 (deprecated, don't use)
- `v2` - Helm 3 (required for Helm 3+)

**Why v2:**
- Required for Helm 3.x
- Supports improved dependency management
- Enables library charts
- Better validation and error messages

### name: secrets-demo

**What it is:** Unique identifier for this chart

**Requirements:**
- Must match directory name: `helm-scenarios/07-secrets-management/`
- Lowercase letters, numbers, hyphens only
- No spaces or special characters
- Cannot start or end with hyphen

**Used for:**
- Default resource names (via `{{ .Chart.Name }}`)
- Helm list output
- Chart repository indexing

### description

**What it is:** Human-readable summary of chart purpose

**Purpose:**
- Shown in `helm search` output
- Displayed in chart repositories
- Documentation for chart users

**Best practices:**
- Keep under 100 characters
- Describe what the chart does, not how
- Mention key features or use cases

### type: application

**What it is:** Chart classification

**Types:**
- **application** - Deploys a workload (Deployment, StatefulSet, etc.)
- **library** - Only template helpers, no resources (e.g., common-labels chart)

**Our choice (application):**
- Creates actual Kubernetes resources (Deployment, Secret, Service)
- Can be installed with `helm install`
- Appears in `helm list`

**Library chart example:**
```yaml
# A library chart would only have _helpers.tpl
type: library
```

### version: 0.1.0

**What it is:** Chart version (SemVer format)

**Versioning rules:**
- **MAJOR.MINOR.PATCH** format
- Increment PATCH for bug fixes
- Increment MINOR for new features
- Increment MAJOR for breaking changes

**Example progression:**
```
0.1.0 → Initial release
0.1.1 → Fix typo in template
0.2.0 → Add support for externalSecret
1.0.0 → First production-ready release
```

**Important:** Chart version is independent of appVersion

### appVersion: "1.0.0"

**What it is:** Version of the application being deployed

**Differences:**
- **version** (0.1.0) = Chart code version
- **appVersion** (1.0.0) = Application/container version

**Example:**
```yaml
version: 0.5.0        # Chart templates updated
appVersion: "1.0.0"   # Still deploying nginx:1.0.0

version: 0.5.1        # Chart bug fix
appVersion: "1.1.0"   # Now deploying nginx:1.1.0
```

**Usage in templates:**
```yaml
image: nginx:{{ .Chart.AppVersion }}
```

---

## 📄 values.yaml - Default Values Explanation

```yaml
# Default values for secrets-demo chart

replicaCount: 1

image:
  repository: nginx
  tag: "1.24"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

# Secrets configuration
# WARNING: In production, NEVER store real secrets in values.yaml!
# This is for demonstration purposes only.
secrets:
  # Database credentials
  dbUsername: "app_user"
  dbPassword: "CHANGE_ME"
  # API key
  apiKey: "CHANGE_ME"
  # Whether to use the lookup function to preserve existing secrets
  useLookup: false

# External secret reference (for sealed-secrets approach)
externalSecret:
  enabled: false
  secretName: "app-sealed-secret"

resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 50m
    memory: 64Mi
```

### replicaCount: 1

**What it is:** Number of pod replicas to create

**Why 1 for this demo:**
- Secrets management is independent of replica count
- Saves cluster resources during learning
- Simplifies logs and debugging

**Production considerations:**
```yaml
replicaCount: 3  # High availability
```

### image.repository: nginx

**What it is:** Container image to deploy

**Why nginx:**
- Lightweight (small image size)
- Fast startup
- Standard base image
- Focus remains on secrets, not application complexity

**Real-world example:**
```yaml
image:
  repository: mycompany/app
  tag: "v2.1.0"
```

### image.tag: "1.24"

**What it is:** Image version tag

**Why quoted:**
- YAML interprets `1.24` as float (1.24)
- Quotes force string interpretation ("1.24")
- Prevents edge cases like `1.10` vs `1.1` comparison

**Best practices:**
```yaml
tag: "1.24"      # ✅ Good (string)
tag: latest      # ⚠️ Avoid (not reproducible)
tag: ""          # ✅ Defaults to .Chart.AppVersion
```

### image.pullPolicy: IfNotPresent

**What it is:** When to pull the container image

**Options:**
- **Always** - Pull on every pod start (slower, always fresh)
- **IfNotPresent** - Pull only if not cached locally (faster, common choice)
- **Never** - Never pull, must exist locally (testing only)

**Our choice (IfNotPresent):**
- Faster pod startup in local Kind cluster
- Sufficient for demo with fixed tag
- Avoids rate limits from Docker Hub

**Production for mutable tags:**
```yaml
pullPolicy: Always  # For 'latest' or 'dev' tags
```

### service.type: ClusterIP

**What it is:** How the service is exposed

**Why ClusterIP:**
- Internal-only access (cluster-internal)
- No external ports needed for secrets demo
- Most secure (no external exposure)

**Service types:**
```yaml
ClusterIP    # Internal only (10.96.0.1:80)
NodePort     # External via node:30000-32767
LoadBalancer # Cloud provider external LB
```

### service.port: 80

**What it is:** Port the Service listens on (inside cluster)

**Why 80:**
- Standard HTTP port
- Easy to remember
- Compatible with nginx default

**Port flow:**
```
Service:80 → Pod targetPort:80 → Container:8080
```

### secrets.dbUsername: "app_user"

**What it is:** Default database username

**⚠️ CRITICAL WARNING:**
```
This is for DEMO purposes ONLY!
In production, NEVER put real credentials in values.yaml!
```

**Why "app_user" is okay here:**
- Non-sensitive username (not a secret)
- Used to demonstrate the template pattern
- Will be replaced by lookup or external secret

**Production alternative:**
```yaml
# values.yaml
secrets:
  dbUsername: ""  # Leave empty

# Create secret externally:
kubectl create secret generic db-creds \
  --from-literal=DB_USERNAME=real_user \
  --from-literal=DB_PASSWORD=real_secure_password
```

### secrets.dbPassword: "CHANGE_ME"

**What it is:** Default database password (PLACEHOLDER ONLY)

**Why "CHANGE_ME":**
- Obviously not a real password
- Forces users to think about proper secret management
- Makes it obvious if default values are used
- Will fail any authentication (prevents accidents)

**Security implications if you actually pass a real password here:**
```bash
# ❌ INSECURE - Password stored in Helm release
helm install app . --set secrets.dbPassword=RealPassword123

# Where it's stored:
kubectl get secret -n helm-scenarios -l owner=helm
# → Helm release secret contains "RealPassword123" in plaintext
```

**Proper approach:**
```bash
# 1. Create secret manually
kubectl create secret generic app-creds \
  --from-literal=DB_PASSWORD=$(openssl rand -base64 32)

# 2. Install chart with lookup enabled
helm install app . --set secrets.useLookup=true

# 3. Or use sealed-secrets (best)
kubeseal < secret.yaml > sealed-secret.yaml
git add sealed-secret.yaml  # Safe to commit!
```

### secrets.apiKey: "CHANGE_ME"

**What it is:** API key placeholder

**Same principles as dbPassword:**
- Placeholder value only
- Should be replaced by external secret management
- "CHANGE_ME" makes misuse obvious

**Real-world API key patterns:**
```yaml
# values.yaml (public)
secrets:
  apiKey: ""  # Empty placeholder

# values-prod.yaml (NEVER commit to Git)
secrets:
  apiKey: "sk_live_abc123..."  # Real key

# Install:
helm install app . -f values.yaml -f values-prod.yaml
# Still insecure! Use sealed-secrets instead.
```

### secrets.useLookup: false

**What it is:** Toggle for the Helm lookup function behavior

**Values:**
- **false** (default) - Always create secret from values
- **true** - Reuse existing secret if it exists in cluster

**When false:**
```yaml
# Every helm upgrade overwrites the secret with values.yaml
data:
  DB_PASSWORD: {{ .Values.secrets.dbPassword | b64enc }}
```

**When true:**
```yaml
# Checks cluster first, preserves existing secret
{{- $existing := lookup "v1" "Secret" .Release.Namespace "app-secret" -}}
{{- if $existing }}
  # Use existing secret data (preserves manual updates)
{{- else }}
  # First install, use values.yaml
{{- end }}
```

**Use case:**
```bash
# Day 1: Operator creates secret with strong password
kubectl create secret generic app-creds \
  --from-literal=DB_PASSWORD=$(pwgen 32 1)

# Day 2: Developer upgrades chart
helm upgrade app . --set secrets.useLookup=true
# Secret NOT overwritten with "CHANGE_ME" from values.yaml!
```

**Limitations:**
- Only works during install/upgrade (not `helm template`)
- Requires cluster access at render time
- Breaks GitOps workflows (ArgoCD, FluxCD)
- See "lookup function limitations" section for details

### externalSecret.enabled: false

**What it is:** Switch between Helm-managed and externally-managed secrets

**When false (default):**
- Helm creates the Secret resource from values
- Secret lifecycle tied to Helm release
- Uninstall removes the secret

**When true:**
- Helm does NOT create the Secret
- You must create it externally (kubectl, sealed-secrets, etc.)
- Deployment references the external secret name
- Secret persists after helm uninstall

**Example usage:**
```bash
# 1. Create a sealed secret (encrypted, safe for Git)
cat <<EOF | kubeseal -o yaml > sealed-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-sealed-secret
  namespace: helm-scenarios
data:
  DB_PASSWORD: $(echo "SecurePass" | base64)
EOF

# 2. Apply the sealed secret
kubectl apply -f sealed-secret.yaml

# 3. Install Helm chart referencing it
helm install app . \
  --set externalSecret.enabled=true \
  --set externalSecret.secretName=app-sealed-secret
```

### externalSecret.secretName: "app-sealed-secret"

**What it is:** Name of the externally-managed secret to reference

**How it's used:**
```yaml
# In deployment.yaml
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: {{ .Values.externalSecret.secretName }}  # app-sealed-secret
        key: DB_PASSWORD
```

**Naming conventions:**
```yaml
# Pattern: <app>-<type>-secret
secretName: "myapp-db-secret"
secretName: "myapp-api-keys"
secretName: "myapp-tls-certs"
```

**Validation:**
```bash
# Verify the secret exists before install
kubectl get secret app-sealed-secret -n helm-scenarios
# NAME                TYPE     DATA   AGE
# app-sealed-secret   Opaque   3      5m
```

### resources.limits.cpu: 100m

**What it is:** Maximum CPU the container can use

**100m explained:**
- **m** = millicores (1000m = 1 full CPU core)
- **100m** = 0.1 cores = 10% of one CPU
- Container throttled if it exceeds this

**Why 100m:**
- nginx is lightweight
- Sufficient for low-traffic demo
- Prevents runaway CPU usage
- Protects other pods on the node

**Production sizing:**
```yaml
# Web server
limits:
  cpu: 500m  # 0.5 cores

# API backend
limits:
  cpu: 2000m  # 2 cores

# Batch processor
limits:
  cpu: 4000m  # 4 cores
```

### resources.limits.memory: 128Mi

**What it is:** Maximum memory the container can use

**128Mi explained:**
- **Mi** = Mebibyte (1024² bytes = 1,048,576 bytes)
- **128Mi** = 134,217,728 bytes ≈ 134 MB
- Container killed (OOMKilled) if exceeded

**Why 128Mi:**
- nginx base image ~50Mi
- Room for request buffering
- Prevents memory leaks from consuming entire node

**Memory limits are HARD:**
```yaml
# If pod uses 129Mi, Kubernetes kills it immediately
# Check with:
kubectl describe pod <name>
# Reason: OOMKilled
```

### resources.requests.cpu: 50m

**What it is:** Guaranteed minimum CPU reservation

**50m explained:**
- Kubernetes reserves 0.05 cores on the node
- Scheduler only places pod on nodes with ≥50m available
- Pod always gets at least this much CPU

**Requests vs Limits:**
```yaml
requests:
  cpu: 50m   # Guaranteed: pod always gets 50m
limits:
  cpu: 100m  # Ceiling: pod can burst up to 100m

# This allows 2x burst capacity
```

**Scheduling impact:**
```bash
# Node has 1000m total, 900m already requested
# This pod requests 50m → ✅ Will schedule (50m < 100m free)

# Another pod requests 150m → ❌ Won't schedule (150m > 100m free)
```

### resources.requests.memory: 64Mi

**What it is:** Guaranteed minimum memory reservation

**64Mi explained:**
- Kubernetes reserves 67,108,864 bytes on the node
- Pod always gets at least this much memory
- Scheduler won't place pod on full nodes

**Why 64Mi:**
- nginx typically uses ~50Mi
- 14Mi headroom for requests
- Conservative estimate for demo

**Memory requests vs limits:**
```yaml
requests:
  memory: 64Mi   # Reserved on node
limits:
  memory: 128Mi  # Can burst to 2x

# QoS Class: Burstable (requests < limits)
```

---

## 📄 templates/secret.yaml - Detailed Explanation

This is the core of the scenario - a Secret template with optional lookup function support.

```yaml
{{- if not .Values.externalSecret.enabled }}
{{/*
  Secret template with optional lookup function support.

  When useLookup is true:
  - If the secret already exists in the cluster, reuse its data
  - If it does not exist, create it from values
  This prevents helm upgrade from overwriting secrets that were
  manually rotated or set by an external process.

  When useLookup is false:
  - Always create/update the secret from values
*/}}
{{- $secretName := printf "%s-credentials" (include "secrets-demo.fullname" .) -}}
{{- $existingSecret := dict -}}
{{- if .Values.secrets.useLookup -}}
  {{- $existingSecret = (lookup "v1" "Secret" .Release.Namespace $secretName) | default dict -}}
{{- end -}}
apiVersion: v1
kind: Secret
metadata:
  name: {{ $secretName }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "secrets-demo.labels" . | nindent 4 }}
  annotations:
    helm.sh/resource-policy: keep
type: Opaque
{{- if and .Values.secrets.useLookup (hasKey $existingSecret "data") }}
# Preserving existing secret data (lookup found existing secret)
data:
  DB_USERNAME: {{ index $existingSecret.data "DB_USERNAME" }}
  DB_PASSWORD: {{ index $existingSecret.data "DB_PASSWORD" }}
  API_KEY: {{ index $existingSecret.data "API_KEY" }}
{{- else }}
# Creating secret from values (no existing secret found or lookup disabled)
data:
  DB_USERNAME: {{ .Values.secrets.dbUsername | b64enc | quote }}
  DB_PASSWORD: {{ .Values.secrets.dbPassword | b64enc | quote }}
  API_KEY: {{ .Values.secrets.apiKey | b64enc | quote }}
{{- end }}
{{- end }}
```

### Line 1: {{- if not .Values.externalSecret.enabled }}

**What it does:** Conditionally render this entire secret

**Syntax breakdown:**
- `{{-` = Template action with whitespace trimming (removes preceding whitespace)
- `if not X` = If X is false
- `.Values.externalSecret.enabled` = Access enabled value from values.yaml
- `}}` = Close template action

**Logic:**
```
if externalSecret.enabled = false:
    Render this secret (Helm manages it)
if externalSecret.enabled = true:
    Skip this secret (external tool manages it)
```

**Why this pattern:**
- Single chart supports both Helm-managed and external secrets
- Production uses externalSecret.enabled=true + sealed-secrets
- Development uses externalSecret.enabled=false + lookup function

**Example:**
```bash
# Helm-managed secret
helm install app . --set externalSecret.enabled=false

# Externally-managed secret
kubectl create secret generic app-sealed-secret ...
helm install app . --set externalSecret.enabled=true
```

### Lines 2-13: Comment Block

**What it is:** Multi-line template comment

**Syntax:**
```yaml
{{/*
This is a comment that won't appear in rendered output
*/}}
```

**Why comments matter:**
- Explain complex template logic
- Document assumptions
- Help future maintainers
- Don't appear in `helm template` output

**Best practices:**
- Comment non-obvious template logic
- Explain conditional branches
- Document function inputs/outputs
- Use `{{/*  */}}` not YAML `#` for templates

### Line 14: Variable Assignment - $secretName

```yaml
{{- $secretName := printf "%s-credentials" (include "secrets-demo.fullname" .) -}}
```

**What it does:** Creates a template variable with the secret's full name

**Syntax breakdown:**
- `$secretName` = Variable name (must start with `$`)
- `:=` = Assignment operator
- `printf "%s-credentials"` = Format string (like sprintf)
- `include "secrets-demo.fullname" .` = Call helper template
- `.` = Current context (passed to helper)

**Example output:**
```yaml
# If release name is "myapp"
$secretName = "myapp-secrets-demo-credentials"
```

**Why use variables:**
- DRY (Don't Repeat Yourself) - define once, use multiple times
- Consistency - same name used in metadata and conditionals
- Readability - `$secretName` is clearer than the full expression

**Helper function explained:**
```yaml
# _helpers.tpl defines:
{{- define "secrets-demo.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 -}}
{{- end }}

# Combines: release-name + chart-name
# Truncates to 63 chars (Kubernetes name limit)
```

### Line 15: Variable Assignment - $existingSecret

```yaml
{{- $existingSecret := dict -}}
```

**What it does:** Initialize an empty dictionary variable

**Syntax:**
- `$existingSecret` = Variable name
- `dict` = Create empty dictionary `{}`
- `-}}` = Trim trailing whitespace

**Why initialize to empty dict:**
- Prevents "undefined variable" errors
- Safe default when lookup is disabled
- `hasKey $existingSecret "data"` will return false for empty dict

**Dictionary (map) in Go templates:**
```yaml
{{- $myDict := dict "key1" "value1" "key2" "value2" -}}
# Creates: {"key1": "value1", "key2": "value2"}

{{- $emptyDict := dict -}}
# Creates: {}
```

### Lines 16-18: Conditional Lookup

```yaml
{{- if .Values.secrets.useLookup -}}
  {{- $existingSecret = (lookup "v1" "Secret" .Release.Namespace $secretName) | default dict -}}
{{- end -}}
```

**What it does:** Query the cluster for an existing secret if useLookup is enabled

**Line-by-line:**

**Line 16:** `if .Values.secrets.useLookup`
- Only execute lookup if user enabled it
- Defaults to false (no lookup)

**Line 17:** The lookup function call
```yaml
lookup "v1" "Secret" .Release.Namespace $secretName
```

**lookup function syntax:**
```
lookup <apiVersion> <kind> <namespace> <name>
```

**Parameters explained:**
- `"v1"` = API version for Secrets (core/v1)
- `"Secret"` = Kubernetes resource kind
- `.Release.Namespace` = Namespace where chart is being installed
- `$secretName` = Name of secret to find (from line 14)

**What lookup returns:**
- If secret exists: Full Secret object (with .metadata, .data, etc.)
- If secret doesn't exist: `nil` (null)

**| default dict:**
- Pipe operator passes lookup result to `default` function
- If lookup returns nil, use empty dict `{}` instead
- Prevents errors from accessing nil object

**Assignment:**
- `$existingSecret =` (single `=`, not `:=`)
- Reassigns the variable (already declared on line 15)
- Now contains either the found secret or empty dict

**Example scenarios:**

**Scenario A: Lookup disabled**
```yaml
useLookup: false
# If block skipped entirely
# $existingSecret remains empty dict from line 15
```

**Scenario B: Lookup enabled, secret exists**
```yaml
useLookup: true
# lookup returns:
# {
#   "metadata": {"name": "app-secret", ...},
#   "data": {"DB_PASSWORD": "cGFzc3dvcmQ=", ...}
# }
# $existingSecret = that secret object
```

**Scenario C: Lookup enabled, secret doesn't exist**
```yaml
useLookup: true
# lookup returns: nil
# | default dict converts to: {}
# $existingSecret = {}
```

### Lines 19-24: Secret Metadata

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ $secretName }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "secrets-demo.labels" . | nindent 4 }}
```

**apiVersion: v1**
- Secrets are in core API (no group)
- `v1` is the only version for Secrets
- Different from `apps/v1` (Deployments) or `batch/v1` (Jobs)

**kind: Secret**
- Kubernetes resource type
- Creates an Opaque Secret (default type)

**metadata.name: {{ $secretName }}**
- Uses variable from line 14
- Example: `myapp-secrets-demo-credentials`
- Must be DNS-1123 subdomain (lowercase, alphanumeric, hyphens)

**metadata.namespace: {{ .Release.Namespace }}**
- `.Release.Namespace` is built-in Helm object
- Set via `helm install --namespace <name>`
- Secrets are namespace-scoped (not cluster-wide)

**labels: {{- include "secrets-demo.labels" . | nindent 4 }}**

**Breakdown:**
- `include "secrets-demo.labels" .` = Call helper template function
- `.` = Pass current context to the helper
- `| nindent 4` = Pipe result to `nindent` function (indent 4 spaces)

**What the helper returns:**
```yaml
# From _helpers.tpl:
helm.sh/chart: secrets-demo-0.1.0
app.kubernetes.io/name: secrets-demo
app.kubernetes.io/instance: myapp
app.kubernetes.io/managed-by: Helm
```

**Why use include + nindent:**
```yaml
# Without nindent (wrong indentation):
labels:
helm.sh/chart: secrets-demo-0.1.0
  app.kubernetes.io/name: secrets-demo

# With nindent 4 (correct):
labels:
    helm.sh/chart: secrets-demo-0.1.0
    app.kubernetes.io/name: secrets-demo
```

### Lines 25-26: Annotations

```yaml
  annotations:
    helm.sh/resource-policy: keep
```

**What it is:** Special Helm annotation to control resource lifecycle

**helm.sh/resource-policy: keep**

**Purpose:** Preserve the Secret even after `helm uninstall`

**Behavior:**
```bash
# Without this annotation:
helm uninstall myapp
# Secret is deleted immediately

# With this annotation:
helm uninstall myapp
# Secret remains in cluster!
```

**Why keep secrets:**
- Prevent accidental data loss
- Preserve manually-rotated passwords
- Support external secret management workflows
- Operator can delete when ready

**Other policy values:**
```yaml
# Default (no annotation):
# Delete with release

helm.sh/resource-policy: keep
# Keep after uninstall (our choice)

helm.sh/resource-policy: before-hook-creation
# Delete before install/upgrade hooks
```

**Manual cleanup required:**
```bash
# After uninstall, secret still exists:
kubectl get secret myapp-secrets-demo-credentials
# Must delete manually:
kubectl delete secret myapp-secrets-demo-credentials
```

**Production considerations:**
- ✅ Good: Prevents accidental password loss
- ⚠️ Caution: Orphaned secrets accumulate
- 💡 Best practice: Document cleanup procedure

### Line 27: Secret Type

```yaml
type: Opaque
```

**What it is:** Secret subtype for Kubernetes

**Secret types:**

| Type | Purpose | Example Keys |
|------|---------|--------------|
| **Opaque** | Generic, arbitrary data (our choice) | Any key names |
| `kubernetes.io/service-account-token` | ServiceAccount token | token, ca.crt, namespace |
| `kubernetes.io/dockercfg` | Docker config (legacy) | .dockercfg |
| `kubernetes.io/dockerconfigjson` | Docker config | .dockerconfigjson |
| `kubernetes.io/basic-auth` | Basic auth | username, password |
| `kubernetes.io/ssh-auth` | SSH keys | ssh-privatekey |
| `kubernetes.io/tls` | TLS cert | tls.crt, tls.key |

**Why Opaque:**
- Most flexible (no key name requirements)
- Supports arbitrary key names (DB_PASSWORD, API_KEY, etc.)
- No schema validation
- Default type if omitted

**Type enforcement:**
```yaml
# Opaque - any keys allowed
type: Opaque
data:
  MY_CUSTOM_KEY: dmFsdWU=  # ✅ Allowed

# kubernetes.io/tls - specific keys required
type: kubernetes.io/tls
data:
  tls.crt: ...  # ✅ Required
  tls.key: ...  # ✅ Required
  custom: ...   # ❌ Validation error!
```

### Lines 28-42: Conditional Secret Data (The Core Logic)

```yaml
{{- if and .Values.secrets.useLookup (hasKey $existingSecret "data") }}
# Preserving existing secret data (lookup found existing secret)
data:
  DB_USERNAME: {{ index $existingSecret.data "DB_USERNAME" }}
  DB_PASSWORD: {{ index $existingSecret.data "DB_PASSWORD" }}
  API_KEY: {{ index $existingSecret.data "API_KEY" }}
{{- else }}
# Creating secret from values (no existing secret found or lookup disabled)
data:
  DB_USERNAME: {{ .Values.secrets.dbUsername | b64enc | quote }}
  DB_PASSWORD: {{ .Values.secrets.dbPassword | b64enc | quote }}
  API_KEY: {{ .Values.secrets.apiKey | b64enc | quote }}
{{- end }}
```

**This is the critical decision point that determines secret security!**

### Line 28: The Conditional Check

```yaml
{{- if and .Values.secrets.useLookup (hasKey $existingSecret "data") }}
```

**What it does:** Decide whether to preserve existing secret or create from values

**Syntax breakdown:**
- `and X Y` = Logical AND (both must be true)
- `.Values.secrets.useLookup` = User enabled lookup feature
- `hasKey $existingSecret "data"` = Secret exists and has data field

**Truth table:**

| useLookup | Secret Exists | hasKey "data" | Result | Action |
|-----------|---------------|---------------|--------|--------|
| false | No | false | ❌ FALSE | Create from values |
| false | Yes | true | ❌ FALSE | Create from values (overwrites!) |
| true | No | false | ❌ FALSE | Create from values (first install) |
| true | Yes | true | ✅ TRUE | Preserve existing |

**Why both conditions:**

**Condition 1:** `.Values.secrets.useLookup`
- User must explicitly enable preservation
- Defaults to false (safe default = overwrite with values)
- Opt-in behavior

**Condition 2:** `hasKey $existingSecret "data"`
- Verifies secret actually exists
- Prevents errors accessing nil object
- Handles first install gracefully

**hasKey function:**
```yaml
hasKey <dict> <key>
# Returns true if dictionary contains key
# Returns false if dictionary is empty or key missing

hasKey {} "data"                          # false (empty dict)
hasKey {"metadata": {...}} "data"         # false (no data key)
hasKey {"data": {"PASSWORD": "..."}} "data"  # true (has data key)
```

### Lines 30-33: Preserve Existing Secret (TRUE branch)

```yaml
# Preserving existing secret data (lookup found existing secret)
data:
  DB_USERNAME: {{ index $existingSecret.data "DB_USERNAME" }}
  DB_PASSWORD: {{ index $existingSecret.data "DB_PASSWORD" }}
  API_KEY: {{ index $existingSecret.data "API_KEY" }}
```

**What it does:** Copy existing secret data verbatim (no changes)

**Executed when:**
- useLookup = true
- Secret already exists in cluster
- Typical scenario: upgrading chart after manual secret creation

**index function:**
```yaml
{{ index <dict> <key> }}
# Accesses dictionary key
# Like: dict["key"] in Python
# Like: dict.get("key") in JavaScript

{{ index $existingSecret.data "DB_PASSWORD" }}
# Accesses: $existingSecret["data"]["DB_PASSWORD"]
# Returns: "U2VjdXJlUGFzcw==" (base64-encoded value)
```

**Why use index instead of dot notation:**
```yaml
# Dot notation (doesn't work for keys with underscores):
{{ $existingSecret.data.DB_PASSWORD }}  # ❌ Error! Underscore in key name

# Index notation (works for any key name):
{{ index $existingSecret.data "DB_PASSWORD" }}  # ✅ Correct
```

**What's preserved:**
```yaml
# Existing secret in cluster:
apiVersion: v1
kind: Secret
data:
  DB_USERNAME: YXBwX3VzZXI=              # app_user (base64)
  DB_PASSWORD: TWFudWFsbHlTZXRQYXNzd29yZA==  # ManuallySetPassword (base64)
  API_KEY: bWFudWFsbHktc2V0LWFwaS1rZXk=  # manually-set-api-key (base64)

# After helm upgrade with useLookup=true:
# Same exact values ↑ (NOT overwritten with "CHANGE_ME" from values.yaml)
```

**Security benefit:**
```bash
# Operator creates secret with strong password
kubectl create secret generic app-creds \
  --from-literal=DB_PASSWORD=$(openssl rand -base64 32)

# Helm upgrade DOES NOT overwrite it
helm upgrade app . --set secrets.useLookup=true

# Password remains: h8Kq3Lp9... (not "CHANGE_ME")
```

**Already base64-encoded:**
- Values from existing secret are already base64
- We copy them as-is (no re-encoding)
- Secret data is always base64 in Kubernetes

### Lines 35-39: Create from Values (FALSE branch)

```yaml
# Creating secret from values (no existing secret found or lookup disabled)
data:
  DB_USERNAME: {{ .Values.secrets.dbUsername | b64enc | quote }}
  DB_PASSWORD: {{ .Values.secrets.dbPassword | b64enc | quote }}
  API_KEY: {{ .Values.secrets.apiKey | b64enc | quote }}
```

**What it does:** Create secret from values.yaml (or --set overrides)

**Executed when:**
- useLookup = false (default), OR
- Secret doesn't exist yet (first install)

**Pipeline syntax:**
```yaml
{{ .Values.secrets.dbPassword | b64enc | quote }}
#  └─ Input                    └─ Fn1   └─ Fn2
```

**Step-by-step transformation:**

**Step 1:** Access value from values.yaml
```yaml
.Values.secrets.dbPassword  →  "CHANGE_ME"
```

**Step 2:** Base64 encode with `b64enc`
```yaml
"CHANGE_ME" | b64enc  →  Q0hBTkdFX01F
```

**Step 3:** Quote the result
```yaml
Q0hBTkdFX01F | quote  →  "Q0hBTkdFX01F"
```

**Final rendered YAML:**
```yaml
data:
  DB_USERNAME: "YXBwX3VzZXI="      # "app_user" base64-encoded
  DB_PASSWORD: "Q0hBTkdFX01F"      # "CHANGE_ME" base64-encoded
  API_KEY: "Q0hBTkdFX01F"          # "CHANGE_ME" base64-encoded
```

**Why base64 encoding:**
- Kubernetes Secret data must be base64-encoded
- Allows binary data (not just text)
- NOT encryption (easily decoded)

**Decoding:**
```bash
echo "Q0hBTkdFX01F" | base64 -d
# Output: CHANGE_ME
```

**Why quote function:**
```yaml
# Without quote (may break YAML):
DB_PASSWORD: Q0hBTkdFX01F  # Could be interpreted as unquoted string

# With quote (always safe):
DB_PASSWORD: "Q0hBTkdFX01F"  # Guaranteed valid YAML string
```

**Security warning:**
```yaml
# ⚠️ This is INSECURE in production!
# "CHANGE_ME" from values.yaml is now in:
# 1. The Secret resource
# 2. Helm release history (helm get values)
# 3. Possibly Git repository (if values.yaml committed)
# 4. CI/CD logs (if values passed through pipeline)
```

### Line 42: End of Conditional Block

```yaml
{{- end }}
```

**Closes the `if` from line 28**

**Template structure:**
```yaml
{{- if CONDITION }}
  # TRUE branch
{{- else }}
  # FALSE branch
{{- end }}  ← Closes the if/else block
```

### Line 43: End of External Secret Check

```yaml
{{- end }}
```

**Closes the `if not .Values.externalSecret.enabled` from line 1**

**Effect:**
- If externalSecret.enabled = true, entire secret.yaml is skipped
- No Secret resource created by Helm
- Application must reference externally-created secret

---

## 📄 templates/deployment.yaml - Detailed Explanation

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "secrets-demo.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "secrets-demo.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "secrets-demo.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "secrets-demo.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 80
              protocol: TCP
          env:
            {{- if .Values.externalSecret.enabled }}
            # Using externally managed secret (sealed-secrets pattern)
            - name: DB_USERNAME
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.externalSecret.secretName }}
                  key: DB_USERNAME
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.externalSecret.secretName }}
                  key: DB_PASSWORD
            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.externalSecret.secretName }}
                  key: API_KEY
            {{- else }}
            # Using Helm-managed secret
            - name: DB_USERNAME
              valueFrom:
                secretKeyRef:
                  name: {{ include "secrets-demo.fullname" . }}-credentials
                  key: DB_USERNAME
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "secrets-demo.fullname" . }}-credentials
                  key: DB_PASSWORD
            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "secrets-demo.fullname" . }}-credentials
                  key: API_KEY
            {{- end }}
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

### Lines 26-61: Environment Variables (The Key Part)

This section demonstrates the two patterns for injecting secrets into pods.

### Lines 27-43: External Secret Pattern

```yaml
{{- if .Values.externalSecret.enabled }}
# Using externally managed secret (sealed-secrets pattern)
- name: DB_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ .Values.externalSecret.secretName }}
      key: DB_USERNAME
```

**What it does:** Reference a secret created outside of Helm

**Executed when:** externalSecret.enabled = true

**Environment variable structure:**
- `name: DB_USERNAME` = Environment variable name in container
- `valueFrom` = Get value from external source (not hardcoded)
- `secretKeyRef` = Source is a Kubernetes Secret

**secretKeyRef fields:**
- `name: app-sealed-secret` = Secret name to read from
- `key: DB_USERNAME` = Which key in the secret's data map

**How it works at runtime:**
```bash
# 1. Sealed secret exists in cluster
kubectl get secret app-sealed-secret -o yaml
# data:
#   DB_USERNAME: YXBwX3VzZXI=
#   DB_PASSWORD: U2VjdXJlUGFzc3dvcmQ=

# 2. Deployment references it
secretKeyRef:
  name: app-sealed-secret
  key: DB_PASSWORD

# 3. Kubelet injects as environment variable
# Container sees:
# DB_PASSWORD=SecurePassword (automatically base64-decoded)
```

**Advantages:**
- ✅ Secrets managed independently from Helm
- ✅ Can be encrypted with sealed-secrets
- ✅ Rotation doesn't require Helm upgrade
- ✅ GitOps-friendly (encrypted secrets in Git)

**Sealed-secrets workflow:**
```bash
# 1. Create regular secret (do NOT commit this!)
cat > secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: app-sealed-secret
  namespace: helm-scenarios
stringData:
  DB_USERNAME: app_user
  DB_PASSWORD: $(openssl rand -base64 32)
  API_KEY: $(uuidgen)
EOF

# 2. Encrypt it with kubeseal
kubeseal -f secret.yaml -w sealed-secret.yaml

# 3. Commit sealed-secret.yaml to Git (SAFE!)
git add sealed-secret.yaml
git commit -m "Add encrypted secrets"

# 4. Apply to cluster
kubectl apply -f sealed-secret.yaml

# 5. Install Helm chart
helm install app . --set externalSecret.enabled=true
```

### Lines 44-60: Helm-Managed Secret Pattern

```yaml
{{- else }}
# Using Helm-managed secret
- name: DB_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ include "secrets-demo.fullname" . }}-credentials
      key: DB_USERNAME
```

**What it does:** Reference the secret created by secret.yaml template

**Executed when:** externalSecret.enabled = false (default)

**Secret name:**
```yaml
name: {{ include "secrets-demo.fullname" . }}-credentials
# Example: myapp-secrets-demo-credentials
```

**Why this matches:**
- secret.yaml creates: `$secretName := printf "%s-credentials" ...`
- deployment.yaml references: `{{ include "secrets-demo.fullname" . }}-credentials`
- Same naming formula = guaranteed match

**Workflow:**
```bash
# 1. Helm renders secret.yaml
# Creates: myapp-secrets-demo-credentials

# 2. Helm renders deployment.yaml
# References: myapp-secrets-demo-credentials

# 3. Both applied together (atomic)
# Deployment can immediately use the secret
```

**Limitation:**
- ⚠️ Secret values come from values.yaml or --set
- ⚠️ Stored in Helm release history
- ⚠️ Not suitable for production
- ✅ Fine for development/testing

### Lines 62-75: Health Probes and Resources

**livenessProbe** (lines 62-66):
- Checks if container is alive
- Restarts container if failing
- httpGet on path `/` every 10 seconds

**readinessProbe** (lines 67-72):
- Checks if container is ready for traffic
- Removes from Service endpoints if failing
- httpGet on path `/` every 5 seconds

**resources** (lines 74-75):
- Injects CPU/memory limits from values.yaml
- `toYaml` preserves structure
- `nindent 12` indents to correct level

---

## 📄 templates/_helpers.tpl - Template Functions

```yaml
{{/*
Expand the name of the chart.
*/}}
{{- define "secrets-demo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "secrets-demo.fullname" -}}
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
{{- define "secrets-demo.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "secrets-demo.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "secrets-demo.selectorLabels" -}}
app.kubernetes.io/name: {{ include "secrets-demo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

### secrets-demo.fullname Function

**Purpose:** Generate unique resource names

**Logic:**
1. If fullnameOverride set → use it
2. Else if release name contains chart name → use release name
3. Else → combine release-name + chart-name

**Examples:**
```bash
# Release: myapp, Chart: secrets-demo
→ myapp-secrets-demo

# Release: secrets-demo, Chart: secrets-demo
→ secrets-demo (no duplicate)

# Release: prod, Chart: secrets-demo, fullnameOverride: "app"
→ app
```

**Why truncate to 63 chars:**
- Kubernetes resource names max 63 characters
- DNS-1123 subdomain format requirement
- Prevents validation errors

### secrets-demo.labels Function

**Purpose:** Standard labels for all resources

**Returns:**
```yaml
helm.sh/chart: secrets-demo-0.1.0
app.kubernetes.io/name: secrets-demo
app.kubernetes.io/instance: myapp
app.kubernetes.io/managed-by: Helm
```

**Usage:**
- Organizational (find all resources for this chart)
- Monitoring (Prometheus label filtering)
- Policies (NetworkPolicy selectors)

### secrets-demo.selectorLabels Function

**Purpose:** Labels for pod selection (immutable)

**Returns:**
```yaml
app.kubernetes.io/name: secrets-demo
app.kubernetes.io/instance: myapp
```

**Why separate from common labels:**
- Pod selectors are immutable after creation
- Can't include version (changes with upgrades)
- Must be stable across chart versions

---

## 🔐 The Helm lookup Function Deep Dive

### What is lookup?

**lookup** is a Helm template function that queries the Kubernetes cluster for existing resources during rendering.

**Signature:**
```
lookup <apiVersion> <kind> <namespace> <name>
```

**Returns:**
- If resource exists: Full resource object (as map/dict)
- If resource doesn't exist: `nil` (empty)
- If name omitted: List of all resources of that kind

### Example Usage

```yaml
# Check if ConfigMap exists
{{- $cm := lookup "v1" "ConfigMap" "default" "my-config" -}}
{{- if $cm }}
  # ConfigMap exists, use its data
  config: {{ $cm.data.setting }}
{{- else }}
  # ConfigMap doesn't exist, use default
  config: "default-value"
{{- end }}
```

### Accessing Returned Data

```yaml
{{- $secret := lookup "v1" "Secret" "default" "db-creds" -}}

# Access metadata
{{- $secret.metadata.name }}           # "db-creds"
{{- $secret.metadata.namespace }}      # "default"
{{- $secret.metadata.creationTimestamp }}

# Access spec/data
{{- $secret.data }}                    # Map of all keys
{{- index $secret.data "password" }}   # Specific key
{{- $secret.type }}                    # "Opaque"
```

### Critical Limitations

**1. Does NOT work with `helm template`**
```bash
# ❌ lookup returns empty
helm template myapp . --set secrets.useLookup=true

# Why: No cluster connection, can't query resources
# Result: Falls back to values.yaml (may leak secrets in output)
```

**2. Requires cluster access at render time**
```bash
# ✅ Works
helm install myapp . --set secrets.useLookup=true

# ❌ Breaks GitOps
# ArgoCD/FluxCD render templates client-side
# No cluster access during render = lookup fails
```

**3. Timing issues with first install**
```bash
# First install: secret doesn't exist yet
helm install myapp . --set secrets.useLookup=true
# lookup returns nil → creates from values.yaml

# Second install: secret exists
helm upgrade myapp . --set secrets.useLookup=true
# lookup returns existing secret → preserves it
```

**4. Breaks `--dry-run`**
```bash
helm upgrade myapp . --dry-run --set secrets.useLookup=true
# lookup may or may not execute (depending on Helm version)
# Output may differ from actual install
```

### When to Use lookup

**✅ Good use cases:**
- Preserving manually-rotated secrets during upgrades
- Checking if resources exist before creating
- Conditional logic based on cluster state
- Migrations from manual to Helm-managed resources

**❌ Avoid when:**
- Using GitOps tools (ArgoCD, FluxCD)
- Need predictable `helm template` output
- Auditing/compliance requires reproducible renders
- CI/CD pipeline renders templates client-side

### Alternatives to lookup

**Instead of lookup for secrets:**
```yaml
# ❌ Avoid: lookup-based secrets
secrets:
  useLookup: true

# ✅ Better: External secret reference
externalSecret:
  enabled: true
  secretName: "app-sealed-secret"
```

**For conditional resources:**
```yaml
# ❌ Avoid: lookup to check if resource exists
{{- if lookup "v1" "ConfigMap" .Release.Namespace "existing-cm" }}

# ✅ Better: Explicit values.yaml flag
{{- if .Values.useExistingConfigMap }}
```

---

## 🏭 Production Secrets Management Approaches

### 1. Sealed Secrets (Recommended for GitOps)

**How it works:**
1. Install sealed-secrets controller in cluster
2. Encrypt secrets with `kubeseal` CLI (uses cluster public key)
3. Commit encrypted `SealedSecret` to Git
4. Controller decrypts and creates normal Secret in cluster

**Setup:**
```bash
# Install controller
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system

# Create secret (do NOT commit)
cat > secret.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
  namespace: default
stringData:
  password: SuperSecure123
EOF

# Encrypt it (SAFE to commit)
kubeseal -f secret.yaml -w sealed-secret.yaml

# Result: sealed-secret.yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: app-secret
  namespace: default
spec:
  encryptedData:
    password: AgBHv8... (long encrypted string)
```

**Helm chart integration:**
```yaml
# values.yaml
externalSecret:
  enabled: true
  secretName: "app-secret"

# Install chart
helm install app . -f values.yaml
# Deployment references app-secret (created by SealedSecret controller)
```

**Advantages:**
- ✅ Safe to commit to Git
- ✅ GitOps-friendly (ArgoCD, FluxCD)
- ✅ No cluster access needed during render
- ✅ Decryption happens in-cluster only

**Disadvantages:**
- ⚠️ Encrypted per-cluster (can't share between clusters)
- ⚠️ Backup sealed-secrets controller private key!
- ⚠️ Re-seal if cluster changes

**Best for:** GitOps workflows, small teams, Kubernetes-native approach

### 2. External Secrets Operator

**How it works:**
1. Store secrets in external vault (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager)
2. Create `ExternalSecret` resource pointing to external secret
3. Operator syncs external secret → Kubernetes Secret
4. Pods reference the synced Secret

**Example:**
```yaml
# ExternalSecret resource
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-db-secret
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: app-db-secret  # Kubernetes Secret to create
  data:
    - secretKey: password
      remoteRef:
        key: prod/db/password  # Path in AWS Secrets Manager
```

**Helm chart integration:**
```yaml
# values.yaml
externalSecret:
  enabled: true
  secretName: "app-db-secret"

# ExternalSecret created separately (or in chart if desired)
```

**Advantages:**
- ✅ Single source of truth (external vault)
- ✅ Centralized secret management
- ✅ Automatic rotation (refreshInterval)
- ✅ Works with existing vaults (AWS, Azure, GCP)

**Disadvantages:**
- ⚠️ Requires external vault infrastructure
- ⚠️ Network dependency (cluster must reach vault)
- ⚠️ More complex setup

**Best for:** Enterprise environments, multi-cloud, existing vault infrastructure

### 3. CSI Secret Store Driver

**How it works:**
1. Secrets stored in external provider (Vault, AWS, Azure)
2. CSI driver mounts secrets as volumes (not env vars)
3. Secrets appear as files in pod
4. Automatically rotated without pod restart

**Example:**
```yaml
# Pod using CSI secret volumes
spec:
  volumes:
    - name: secrets-store
      csi:
        driver: secrets-store.csi.k8s.io
        readOnly: true
        volumeAttributes:
          secretProviderClass: "app-secrets"
  containers:
    - name: app
      volumeMounts:
        - name: secrets-store
          mountPath: "/mnt/secrets"
          readOnly: true
      # Read password from file
      env:
        - name: DB_PASSWORD
          value: /mnt/secrets/db-password
```

**Advantages:**
- ✅ Automatic rotation without restart
- ✅ No secrets in environment variables
- ✅ Works with all major cloud providers
- ✅ Secrets never stored in etcd

**Disadvantages:**
- ⚠️ More complex than env vars
- ⚠️ App must read from files
- ⚠️ Requires CSI driver installation

**Best for:** High-security requirements, frequent rotation, cloud-native apps

### 4. HashiCorp Vault + Sidecar Injector

**How it works:**
1. Secrets stored in Vault
2. Vault Agent Injector mutates pods (adds sidecar)
3. Sidecar authenticates with Vault
4. Secrets rendered to shared volume
5. App reads secrets from files

**Example:**
```yaml
# Pod annotations trigger injection
metadata:
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "myapp"
    vault.hashicorp.com/agent-inject-secret-db: "database/creds/readonly"
    vault.hashicorp.com/agent-inject-template-db: |
      {{- with secret "database/creds/readonly" -}}
      username={{ .Data.username }}
      password={{ .Data.password }}
      {{- end }}
spec:
  containers:
    - name: app
      # Secrets available at /vault/secrets/db
```

**Advantages:**
- ✅ Dynamic secrets (generated on-demand)
- ✅ Automatic renewal
- ✅ Centralized audit log
- ✅ Fine-grained access policies

**Disadvantages:**
- ⚠️ Complex Vault setup
- ⚠️ Sidecar resource overhead
- ⚠️ Steeper learning curve

**Best for:** Enterprise with existing Vault, dynamic secrets, compliance requirements

---

## 🔍 How Helm Stores Release Data (Including Secrets!)

### The Hidden Secret Storage

**Every Helm release stores ALL values as a Kubernetes Secret!**

```bash
# Install with secret
helm install myapp . --set secrets.password=SuperSecret123

# Helm creates TWO secrets:
kubectl get secrets -n default
# 1. myapp-credentials (your application secret)
# 2. sh.helm.release.v1.myapp.v1 (Helm release metadata)
```

### Inspecting Helm Release Secrets

```bash
# List Helm release secrets
kubectl get secrets -l owner=helm

# NAME                        TYPE                DATA   AGE
# sh.helm.release.v1.myapp.v1  helm.sh/release.v1   1      5m

# Decode the release data
kubectl get secret sh.helm.release.v1.myapp.v1 -o jsonpath='{.data.release}' \
  | base64 -d \
  | base64 -d \
  | gunzip \
  | jq .

# Output includes:
# {
#   "name": "myapp",
#   "info": {...},
#   "config": {
#     "secrets": {
#       "password": "SuperSecret123"  ← YOUR SECRET IN PLAINTEXT!
#     }
#   },
#   "manifest": "...",
#   "version": 1
# }
```

### Security Implications

**Problem 1: Secrets in Helm history**
```bash
# Even after upgrading with new password
helm upgrade myapp . --set secrets.password=NewPassword456

# OLD password still in revision 1:
helm get values myapp --revision 1
# secrets:
#   password: SuperSecret123  ← Still there!
```

**Problem 2: Accessible to anyone with kubectl**
```bash
# Any user with Secret read access can see Helm values
kubectl get secrets -n default -l owner=helm -o yaml
# All historical passwords exposed
```

**Problem 3: etcd backup contains secrets**
```bash
# Cluster backup includes all Secrets
# Including Helm release secrets
# Including all historical password values
```

### How to Avoid This

**❌ Never do this:**
```bash
helm install app . --set secrets.password=RealPassword
helm install app . -f values-with-secrets.yaml
```

**✅ Always do this:**
```bash
# 1. Create secret outside Helm
kubectl create secret generic app-secret \
  --from-literal=password=$(openssl rand -base64 32)

# 2. Install chart with lookup
helm install app . --set secrets.useLookup=true

# 3. Or reference external secret
helm install app . --set externalSecret.enabled=true
```

---

## 🐛 Troubleshooting Secrets Management

### Problem 1: Secret not found

**Error:**
```
Error: Secret "app-credentials" not found
```

**Causes:**
1. externalSecret.enabled=true but secret not created externally
2. Secret in wrong namespace
3. Secret name mismatch

**Solution:**
```bash
# Check if secret exists
kubectl get secret app-credentials -n <namespace>

# Create it if missing
kubectl create secret generic app-credentials \
  --from-literal=DB_PASSWORD=test123 \
  -n <namespace>

# Or disable external secret
helm upgrade app . --set externalSecret.enabled=false
```

### Problem 2: lookup function returns empty

**Symptom:**
- helm install works fine
- helm template shows values.yaml secrets

**Cause:**
- helm template doesn't connect to cluster
- lookup always returns empty/nil

**Solution:**
```bash
# Use helm install instead of helm template
helm install app . --dry-run --debug

# Or test with actual install
helm install app . --set secrets.useLookup=true
```

### Problem 3: Secret overwritten on upgrade

**Symptom:**
- Manually rotated password
- helm upgrade reverted to "CHANGE_ME"

**Cause:**
- useLookup=false (default)
- Helm overwrites secret from values

**Solution:**
```bash
# Enable lookup before upgrade
helm upgrade app . --set secrets.useLookup=true

# Verify preserved
kubectl get secret app-credentials -o jsonpath='{.data.DB_PASSWORD}' | base64 -d
```

### Problem 4: Helm history leaks old passwords

**Symptom:**
- Changed password via --set
- Old password visible in `helm history`

**Cause:**
- Helm stores all revisions with full values

**Solution:**
```bash
# 1. Stop using --set for secrets!

# 2. Delete release (keeps secrets with resource-policy: keep)
helm uninstall app

# 3. Delete Helm release secrets
kubectl delete secrets -l owner=helm,name=app

# 4. Reinstall with proper secret management
kubectl create secret generic app-secret --from-literal=password=newpass
helm install app . --set externalSecret.enabled=true
```

### Problem 5: Base64 decode fails

**Error:**
```
invalid base64 data
```

**Causes:**
1. Secret not base64-encoded in values
2. Double base64 encoding (encoding already-encoded value)

**Solution:**
```bash
# Verify secret data
kubectl get secret app-credentials -o yaml

# Should be valid base64
echo "Q0hBTkdFX01F" | base64 -d  # ✅ Works → "CHANGE_ME"
echo "CHANGE_ME" | base64 -d     # ❌ Error (not base64)

# In templates, use b64enc:
data:
  PASSWORD: {{ .Values.password | b64enc }}  # ✅ Correct
  PASSWORD: {{ .Values.password }}           # ❌ Wrong (not encoded)
```

---

## 📚 Best Practices Summary

### 1. Never Store Secrets in Values

**❌ Don't do this:**
```yaml
# values-prod.yaml (committed to Git)
secrets:
  dbPassword: "MyProductionPassword123"
```

**✅ Do this:**
```yaml
# values.yaml (committed to Git)
secrets:
  dbPassword: ""  # Empty placeholder

externalSecret:
  enabled: true
  secretName: "app-sealed-secret"  # Managed by sealed-secrets
```

### 2. Use Resource Policy to Prevent Loss

**Always add to secrets:**
```yaml
metadata:
  annotations:
    helm.sh/resource-policy: keep
```

**Prevents:**
- Accidental deletion during `helm uninstall`
- Loss of manually-rotated passwords

### 3. Separate Secret Lifecycle from App Lifecycle

**❌ Tightly coupled:**
```yaml
# Helm manages everything
helm install app .
# Creates: Deployment + Secret (from values)

helm uninstall app
# Deletes: Deployment + Secret (password lost!)
```

**✅ Decoupled:**
```yaml
# Secrets managed separately
kubectl create secret generic app-secret ...

# Helm only manages app
helm install app . --set externalSecret.enabled=true

# Uninstall app, secret persists
helm uninstall app
kubectl get secret app-secret  # Still there!
```

### 4. Use lookup Only as Interim Solution

**lookup is NOT a production solution:**
- Breaks GitOps
- Breaks helm template
- Cluster-dependent rendering

**Use for:**
- Migration from manual to automated secrets
- Temporary workaround during refactoring

**Migrate to:**
- Sealed Secrets (GitOps)
- External Secrets Operator (cloud vaults)
- CSI Secret Store (file-based)

### 5. Audit Helm Release Secrets

**Regularly check:**
```bash
# List Helm release secrets
kubectl get secrets -l owner=helm -A

# Check for leaked passwords
helm get values <release> --all
# Should NOT show real passwords
```

**Remediate leaks:**
```bash
# 1. Rotate compromised passwords
kubectl create secret generic new-secret \
  --from-literal=password=$(openssl rand -base64 32)

# 2. Delete Helm release history
helm uninstall <release>
kubectl delete secrets -l owner=helm,name=<release>

# 3. Reinstall with external secret
helm install <release> . --set externalSecret.enabled=true
```

### 6. Document Secret Management for Your Team

**Include in README:**
```markdown
## Secrets Management

This chart supports two modes:

### Development (not for production)
```bash
helm install app . --set secrets.useLookup=true
```

### Production (sealed-secrets)
```bash
# 1. Create sealed secret
kubeseal -f secret.yaml -w sealed-secret.yaml

# 2. Apply sealed secret
kubectl apply -f sealed-secret.yaml

# 3. Install chart
helm install app . --set externalSecret.enabled=true
```
```

---

## 🔗 Further Reading

### Official Documentation

- **Helm Secrets Best Practices**: https://helm.sh/docs/chart_best_practices/secrets/
- **Helm lookup Function**: https://helm.sh/docs/chart_template_guide/functions_and_pipelines/#using-the-lookup-function
- **Kubernetes Secrets**: https://kubernetes.io/docs/concepts/configuration/secret/
- **Kubernetes Secrets Good Practices**: https://kubernetes.io/docs/concepts/security/secrets-good-practices/

### Tools & Projects

- **Sealed Secrets**: https://github.com/bitnami-labs/sealed-secrets
- **External Secrets Operator**: https://external-secrets.io/
- **CSI Secret Store Driver**: https://secrets-store-csi-driver.sigs.k8s.io/
- **HashiCorp Vault**: https://www.vaultproject.io/docs/platform/k8s

### Security Guides

- **OWASP Secrets Management Cheat Sheet**: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- **CIS Kubernetes Benchmark (Secrets section)**: https://www.cisecurity.org/benchmark/kubernetes
- **NSA/CISA Kubernetes Hardening Guide**: https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF

### Blog Posts & Tutorials

- **Sealed Secrets Tutorial**: https://aws.amazon.com/blogs/opensource/managing-secrets-deployment-in-kubernetes-using-sealed-secrets/
- **External Secrets with AWS**: https://aws.amazon.com/blogs/containers/aws-secrets-controller-for-kubernetes/
- **Vault on Kubernetes**: https://learn.hashicorp.com/tutorials/vault/kubernetes-sidecar

---

## 🎓 Key Takeaways

1. **Kubernetes Secrets are NOT encrypted** - Only base64-encoded, anyone with Secret read access can decode them

2. **Helm stores ALL values in release history** - Including secrets passed via --set, visible with `helm get values`

3. **lookup function is a partial solution** - Works for install/upgrade but breaks helm template and GitOps

4. **Production requires external secret management** - Sealed Secrets, External Secrets Operator, CSI drivers, or Vault

5. **Separate secret lifecycle from app lifecycle** - Don't let `helm uninstall` delete your passwords

6. **Use helm.sh/resource-policy: keep** - Preserves secrets after uninstall, prevents accidental loss

7. **Audit your Helm releases** - Check for leaked secrets in `helm get values` and release secrets

8. **Never commit secrets to Git** - Not in values.yaml, not in --set commands in CI/CD, use sealed-secrets instead

9. **The only GitOps-safe approaches** - Sealed Secrets or External Secrets Operator (not lookup function)

10. **Default to externalSecret.enabled=true** - In production, always reference externally-managed secrets

---

*This comprehensive guide covers everything you need to know about secrets management in Helm, from basic concepts to production-ready patterns. Understanding these security implications is critical for operating Kubernetes safely!*
