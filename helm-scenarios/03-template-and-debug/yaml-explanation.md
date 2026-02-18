# Helm Template and Debug Explanation

This guide explains Helm's templating system, debugging tools, and the differences between local rendering (`helm template`) and server-side validation (`--dry-run --debug`). You'll understand how Helm transforms templates into Kubernetes manifests.

---

## 🎯 What is Helm Templating?

**Helm templating** is the process of converting Go template files (`.yaml` with `{{ }}` placeholders) into valid Kubernetes manifests by substituting values.

### Why Templates?

Without templates (hard-coded YAML):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx  # FIXED NAME
spec:
  replicas: 3  # FIXED REPLICA COUNT
```

With templates (flexible):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}  # DYNAMIC NAME
spec:
  replicas: {{ .Values.replicaCount }}  # CONFIGURABLE
```

**Benefits:**
- ✅ **Reusability** - Same chart, multiple configurations
- ✅ **Customization** - Override defaults without editing templates
- ✅ **Consistency** - Enforce standards across deployments
- ✅ **Portability** - Share charts with others

---

## 📁 Helm Chart Structure

### Standard Chart Directory Layout

```
debug-app/
├── Chart.yaml          # Chart metadata (name, version, description)
├── values.yaml         # Default configuration values
├── charts/             # Dependencies (subcharts)
├── templates/          # Kubernetes manifests with Go templates
│   ├── NOTES.txt       # Post-install instructions (templated)
│   ├── _helpers.tpl    # Reusable template functions
│   ├── deployment.yaml # Deployment template
│   ├── service.yaml    # Service template
│   ├── serviceaccount.yaml
│   ├── hpa.yaml        # HorizontalPodAutoscaler template
│   ├── ingress.yaml    # Ingress template
│   └── tests/          # Test pods (run with helm test)
└── .helmignore         # Files to ignore (like .gitignore)
```

### Chart.yaml Explained

```yaml
apiVersion: v2           # Helm chart API version (v2 for Helm 3)
name: debug-app          # Chart name (must match directory name)
description: A Helm chart for Kubernetes
type: application        # application or library
version: 0.1.0           # Chart version (SemVer)
appVersion: "1.16.0"     # Application version (informational)
```

**Key fields:**
- **name**: Identifies the chart, must be lowercase alphanumeric + hyphens
- **version**: Chart version (incremented when chart changes)
- **appVersion**: The version of the application being deployed (e.g., nginx:1.16.0)
- **type**:
  - `application` - Standalone chart that deploys an app
  - `library` - Reusable template functions (no deployment)

### values.yaml Explained

**Purpose:** Default values for template variables

**Example:**
```yaml
replicaCount: 1

image:
  repository: nginx
  pullPolicy: IfNotPresent
  tag: ""  # Defaults to Chart.appVersion

service:
  type: ClusterIP
  port: 80

resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

**Structure:** Nested YAML that mirrors template variable access

**Access in templates:**
```yaml
replicas: {{ .Values.replicaCount }}
image: {{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}
```

### templates/_helpers.tpl

**Purpose:** Reusable template snippets (like functions)

**Common helpers:**

```go
{{/*
Expand the name of the chart.
*/}}
{{- define "debug-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a fully qualified app name (release-name + chart-name).
*/}}
{{- define "debug-app.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "debug-app.labels" -}}
helm.sh/chart: {{ include "debug-app.chart" . }}
{{ include "debug-app.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
```

**Usage in templates:**
```yaml
metadata:
  name: {{ include "debug-app.fullname" . }}
  labels:
    {{- include "debug-app.labels" . | nindent 4 }}
```

**Why use helpers:**
- **DRY principle** - Define once, use everywhere
- **Consistency** - Same labels across all resources
- **Maintainability** - Change in one place

### templates/NOTES.txt

**Purpose:** Post-install instructions displayed to users

**Example:**
```
1. Get the application URL by running these commands:
{{- if .Values.ingress.enabled }}
{{- range $host := .Values.ingress.hosts }}
  http{{ if $.Values.ingress.tls }}s{{ end }}://{{ $host.host }}{{ .path }}
{{- end }}
{{- else if contains "NodePort" .Values.service.type }}
  export NODE_PORT=$(kubectl get --namespace {{ .Release.Namespace }} -o jsonpath="{.spec.ports[0].nodePort}" services {{ include "debug-app.fullname" . }})
  export NODE_IP=$(kubectl get nodes --namespace {{ .Release.Namespace }} -o jsonpath="{.items[0].status.addresses[0].address}")
  echo http://$NODE_IP:$NODE_PORT
{{- else if contains "ClusterIP" .Values.service.type }}
  export POD_NAME=$(kubectl get pods --namespace {{ .Release.Namespace }} -l "app.kubernetes.io/name={{ include "debug-app.name" . }},app.kubernetes.io/instance={{ .Release.Name }}" -o jsonpath="{.items[0].metadata.name}")
  echo "Visit http://127.0.0.1:8080 to use your application"
  kubectl --namespace {{ .Release.Namespace }} port-forward $POD_NAME 8080:80
{{- end }}
```

**Features:**
- Templated (uses values and conditionals)
- Shown after install/upgrade
- Helpful commands for accessing the app

---

## 🔧 Helm Debugging Tools Comparison

### Tool Matrix

| Tool | Cluster Needed | Server Validation | Local/Remote | Use Case |
|------|---------------|-------------------|--------------|----------|
| **helm lint** | ❌ No | ❌ No | Local | Validate chart structure, YAML syntax |
| **helm template** | ❌ No | ❌ No | Local | Render manifests locally, CI/CD validation |
| **--dry-run --debug** | ✅ Yes | ✅ Yes | Remote | Server-side validation, test API compatibility |
| **helm get manifest** | ✅ Yes | N/A (post-install) | Remote | View deployed manifests |
| **helm get values** | ✅ Yes | N/A (post-install) | Remote | View effective values |

---

## 📝 helm lint

### What It Does

Validates chart structure and templates without rendering or deploying.

**Syntax:**
```bash
helm lint <chart-path>
```

**Checks performed:**
1. **Chart.yaml validation** - Required fields present, valid YAML
2. **values.yaml validation** - Valid YAML syntax
3. **Template rendering** - Templates render with default values
4. **Kubernetes manifest validation** - Output is valid YAML
5. **Best practices** - Recommended conventions followed

**Example output:**
```
==> Linting helm-scenarios/03-template-and-debug/debug-app
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

### Error Levels

**ERROR** (blocks install):
```
[ERROR] templates/deployment.yaml: template: debug-app/templates/deployment.yaml:10:12:
  executing "debug-app/templates/deployment.yaml" at <.Values.replicaCounts>:
  map has no entry for key "replicaCounts"
```

**WARNING** (should fix):
```
[WARNING] templates/deployment.yaml: object name does not conform to Kubernetes naming requirements
```

**INFO** (nice to have):
```
[INFO] Chart.yaml: icon is recommended
```

### When to Use helm lint

✅ **Before committing** - Validate chart changes in Git workflow
✅ **In CI/CD pipelines** - Automated validation on PRs
✅ **After modifying templates** - Catch syntax errors early
✅ **First debugging step** - Quick sanity check

**Example CI/CD:**
```bash
#!/bin/bash
for chart in charts/*; do
  helm lint "$chart" || exit 1
done
```

---

## 📝 helm template

### What It Does

Renders templates **locally** without contacting the Kubernetes API server.

**Syntax:**
```bash
helm template [RELEASE_NAME] <chart-path> [flags]
```

**Example:**
```bash
helm template my-release ./debug-app --namespace prod
```

### Output

Complete Kubernetes YAML ready to apply:

```yaml
---
# Source: debug-app/templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-release-debug-app
  namespace: prod
  labels:
    helm.sh/chart: debug-app-0.1.0
    app.kubernetes.io/name: debug-app
    app.kubernetes.io/instance: my-release
---
# Source: debug-app/templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: my-release-debug-app
  namespace: prod
...
```

### Key Features

**1. Source comments:**
```yaml
# Source: debug-app/templates/deployment.yaml
```
Shows which template file generated each section.

**2. No cluster needed:**
- Works offline
- Fast (no network latency)
- Safe (no actual deployment)

**3. Supports all install flags:**
```bash
helm template my-release ./debug-app \
  --set replicaCount=3 \
  --set service.type=NodePort \
  -f prod-values.yaml \
  --namespace production
```

**4. Can be piped to kubectl:**
```bash
helm template my-release ./debug-app | kubectl apply -f -
```

### Limitations

❌ **No API server validation** - Won't catch:
- Deprecated API versions (e.g., `apps/v1beta1`)
- Invalid resource kinds
- Admission controller rejections
- RBAC permission issues

❌ **No chart hooks execution** - Pre/post-install hooks not run

❌ **No release tracking** - Doesn't create Helm release

### When to Use helm template

✅ **CI/CD validation** - Render in pipeline, inspect before deploy
✅ **Review changes** - See what will be deployed
✅ **GitOps workflows** - Render, commit manifests to Git
✅ **Debugging templates** - Isolate rendering issues
✅ **Manual apply** - Render, then `kubectl apply`

**Example: Review before deploying**
```bash
# Render to file
helm template my-app ./chart -f prod-values.yaml > manifests.yaml

# Review
less manifests.yaml

# Apply manually
kubectl apply -f manifests.yaml
```

---

## 📝 --dry-run --debug

### What It Does

Renders templates and validates against the **Kubernetes API server** without creating resources.

**Syntax:**
```bash
helm install <release-name> <chart> --dry-run --debug [flags]
```

**Example:**
```bash
helm install my-release ./debug-app --namespace prod --dry-run --debug
```

### Output

Detailed debug information + rendered manifests:

```
install.go:178: [debug] Original chart version: ""
install.go:195: [debug] CHART PATH: /path/to/debug-app

NAME: my-release
LAST DEPLOYED: Mon Jan 15 10:00:00 2024
NAMESPACE: prod
STATUS: pending-install
REVISION: 1
USER-SUPPLIED VALUES:
{}

COMPUTED VALUES:
replicaCount: 1
image:
  repository: nginx
  pullPolicy: IfNotPresent
  tag: "1.16.0"
...

HOOKS:
---
# No hooks

MANIFEST:
---
# Source: debug-app/templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
...
```

### Key Features

**1. Server-side validation:**
```bash
helm install test ./chart --dry-run --debug
# ERROR: unable to recognize "": no matches for kind "Deployment" in version "apps/v1beta1"
```

Catches:
- ✅ Deprecated API versions
- ✅ Invalid resource kinds
- ✅ CRDs not installed
- ✅ RBAC permission issues (partially)

**2. Shows computed values:**
```yaml
USER-SUPPLIED VALUES:
replicaCount: 3

COMPUTED VALUES:
replicaCount: 3
image:
  repository: nginx
  pullPolicy: IfNotPresent
  tag: "1.16.0"
```

**3. Displays NOTES.txt:**
```
NOTES:
1. Get the application URL by running these commands:
  export POD_NAME=$(kubectl get pods -l "app=my-app" -o jsonpath="{.items[0].metadata.name}")
  kubectl port-forward $POD_NAME 8080:80
```

**4. Hook visibility:**
Shows pre/post-install hooks (if any):
```yaml
HOOKS:
---
# Source: debug-app/templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    "helm.sh/hook": test
...
```

### Limitations

⚠️ **Requires cluster access** - Must be able to connect to API server
⚠️ **Doesn't test runtime behavior** - Won't catch:
- Pod crash loops
- Missing ConfigMaps/Secrets
- Network connectivity issues
- Resource quota violations (only validates schema)

### When to Use --dry-run --debug

✅ **Before production installs** - Final validation step
✅ **Testing API compatibility** - Ensure versions work on cluster
✅ **Debugging values** - See computed values vs user-supplied
✅ **Validating multi-cluster deploys** - Test on each cluster's API version

**Example: Pre-production validation**
```bash
# Staging cluster
helm install my-app ./chart -f staging.yaml --dry-run --debug | less

# Production cluster
helm install my-app ./chart -f prod.yaml --dry-run --debug | less

# If both pass, deploy for real
helm install my-app ./chart -f prod.yaml --wait
```

---

## 📝 helm get manifest

### What It Does

Retrieves the **actual manifests** stored by a Helm release (post-install/upgrade).

**Syntax:**
```bash
helm get manifest <release-name> --namespace <namespace>
```

**Example:**
```bash
helm get manifest my-release --namespace prod
```

### Output

Exact YAML sent to Kubernetes during install:

```yaml
---
# Source: debug-app/templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-release-debug-app
  namespace: prod
...
```

### Use Cases

**1. Compare planned vs actual:**
```bash
# What we planned
helm template my-release ./chart -f values.yaml > planned.yaml

# What was actually deployed
helm get manifest my-release > actual.yaml

# Compare
diff planned.yaml actual.yaml
```

**2. Debug "what changed":**
```bash
# Get manifest from revision 1
helm get manifest my-release --revision 1 > rev1.yaml

# Get manifest from revision 2
helm get manifest my-release --revision 2 > rev2.yaml

# See changes
diff rev1.yaml rev2.yaml
```

**3. Disaster recovery:**
```bash
# Save manifests before major change
helm get manifest critical-app > backup.yaml

# If upgrade fails, can manually restore
kubectl apply -f backup.yaml
```

**4. Audit trail:**
```bash
# Extract manifests for compliance
for rev in $(helm history my-app --output json | jq '.[].revision'); do
  helm get manifest my-app --revision $rev > manifest-rev${rev}.yaml
done
```

### Difference from helm template

| Aspect | helm template | helm get manifest |
|--------|---------------|-------------------|
| **When** | Before install | After install |
| **Source** | Local chart files | Stored release data |
| **Release name** | Placeholder | Actual release name |
| **Values** | What you specify | What was actually used |
| **Requires cluster** | No | Yes |

---

## 📝 helm get values

### What It Does

Shows the values used for a release (user-supplied or all).

**Syntax:**
```bash
# User-supplied values only
helm get values <release-name> --namespace <namespace>

# All values (including defaults)
helm get values <release-name> --all --namespace <namespace>
```

**Example:**
```bash
helm get values my-release --namespace prod
```

### Output

**User-supplied only:**
```yaml
replicaCount: 3
service:
  type: NodePort
  nodePort: 30080
```

**All values (--all flag):**
```yaml
replicaCount: 3  # USER-SUPPLIED
image:
  repository: nginx  # DEFAULT
  pullPolicy: IfNotPresent  # DEFAULT
  tag: "1.16.0"  # DEFAULT
service:
  type: NodePort  # USER-SUPPLIED
  port: 80  # DEFAULT
  nodePort: 30080  # USER-SUPPLIED
...
```

### Use Cases

**1. Debugging "why isn't my value applying":**
```bash
# Check effective values
helm get values my-release --all | grep replicaCount
# replicaCount: 1  (expected 3?)

# Check user-supplied values
helm get values my-release
# (empty - value was never set!)
```

**2. Compare values across revisions:**
```bash
helm get values my-release --revision 1 > values-rev1.yaml
helm get values my-release --revision 2 > values-rev2.yaml
diff values-rev1.yaml values-rev2.yaml
```

**3. Recreate release config:**
```bash
# Extract values from production
helm get values prod-app > prod-values.yaml

# Replicate in staging
helm install staging-app ./chart -f prod-values.yaml
```

---

## 🎨 Helm Templating Concepts

### Built-in Objects

Helm provides these objects in templates:

| Object | Description | Example |
|--------|-------------|---------|
| `.Release` | Release metadata | `.Release.Name`, `.Release.Namespace` |
| `.Chart` | Chart metadata | `.Chart.Name`, `.Chart.Version` |
| `.Values` | User values | `.Values.replicaCount` |
| `.Files` | Access files in chart | `.Files.Get "config.txt"` |
| `.Capabilities` | Cluster capabilities | `.Capabilities.APIVersions.Has "apps/v1"` |
| `.Template` | Current template | `.Template.Name` |

**Examples:**

```yaml
metadata:
  name: {{ .Release.Name }}-{{ .Chart.Name }}
  namespace: {{ .Release.Namespace }}
  labels:
    version: {{ .Chart.Version }}
    heritage: {{ .Release.Service }}
```

### Template Functions

Helm includes 70+ functions from Sprig library + custom functions.

**Common functions:**

**1. default**
```yaml
image: {{ .Values.image.tag | default "latest" }}
# If tag not set, uses "latest"
```

**2. quote**
```yaml
value: {{ .Values.name | quote }}
# Ensures string is quoted: value: "myname"
```

**3. upper / lower**
```yaml
env: {{ .Values.environment | upper }}
# Converts to uppercase: env: PRODUCTION
```

**4. trunc**
```yaml
name: {{ .Values.longName | trunc 63 }}
# Truncates to 63 characters (Kubernetes limit)
```

**5. trimSuffix / trimPrefix**
```yaml
name: {{ .Values.name | trimSuffix "-" }}
# Removes trailing dash
```

**6. nindent**
```yaml
labels:
  {{- include "app.labels" . | nindent 2 }}
# Indents by 2 spaces
```

**7. toYaml**
```yaml
resources:
  {{- toYaml .Values.resources | nindent 2 }}
# Converts values to YAML with proper indentation
```

### Conditionals

**if/else:**
```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
...
{{- end }}
```

**with (change scope):**
```yaml
{{- with .Values.serviceAccount }}
automountServiceAccountToken: {{ .automount }}
name: {{ .name }}
{{- end }}
```

**range (loop):**
```yaml
{{- range .Values.environments }}
- name: {{ . }}
{{- end }}
```

### Whitespace Control

**`{{-` (trim left whitespace):**
```yaml
labels:
  {{- include "app.labels" . | nindent 2 }}
# No blank line before labels
```

**`-}}` (trim right whitespace):**
```yaml
{{- if .Values.enabled -}}
enabled: true
{{- end -}}
# No blank line after
```

---

## 🐛 Debugging Workflow

### Step-by-Step Debugging Process

**1. Lint first (quickest check):**
```bash
helm lint ./my-chart
```

**2. Render locally:**
```bash
helm template test-release ./my-chart -f values.yaml | less
```

**3. Server-side validation:**
```bash
helm install test-release ./my-chart -f values.yaml --dry-run --debug
```

**4. Install with wait:**
```bash
helm install test-release ./my-chart -f values.yaml --wait --timeout 5m
```

**5. Verify deployed state:**
```bash
helm get manifest test-release
helm get values test-release --all
kubectl get all -n namespace
```

### Common Issues and Solutions

**Issue: "map has no entry for key"**
```
Error: template: chart/templates/deployment.yaml:10:12: executing "chart/templates/deployment.yaml"
  at <.Values.replicaCounts>: map has no entry for key "replicaCounts"
```

**Solution:** Typo in template. Should be `.Values.replicaCount` (singular)

---

**Issue: "unexpected bad character"**
```
Error: unable to build kubernetes objects from release manifest:
  error validating "": error validating data: unexpected bad character (U+000A)
```

**Solution:** Extra newline in template output. Use `{{-` to trim whitespace.

---

**Issue: Rendered template is empty**

**Debug:**
```bash
helm template test-release ./chart --debug | grep -A 20 "MANIFEST"
```

**Common causes:**
- Template wrapped in `{{- if }}` that evaluated to false
- Values not passed correctly
- Template file not in `templates/` directory

**Solution:**
```bash
# Check computed values
helm template test-release ./chart --debug | grep -A 50 "COMPUTED VALUES"

# Check specific value
helm template test-release ./chart --set debug=true --debug | grep -i "your-key"
```

---

**Issue: "API version not found"**
```
Error: unable to recognize "": no matches for kind "Ingress" in version "extensions/v1beta1"
```

**Solution:** Update deprecated API version:
```yaml
# Old (deprecated)
apiVersion: extensions/v1beta1
kind: Ingress

# New
apiVersion: networking.k8s.io/v1
kind: Ingress
```

---

**Issue: Values not overriding defaults**

**Debug:**
```bash
# Check what Helm sees
helm get values my-release --all | grep replicaCount

# Compare with expected
echo "Expected: 3"
echo "Actual: $(helm get values my-release --all | grep replicaCount | awk '{print $2}')"
```

**Common causes:**
- Wrong values file path
- Values file not valid YAML
- `--set` flag overriding `-f` file
- Typo in values.yaml key

---

## 🎓 Practical Examples

### Example 1: Preview changes before upgrade

```bash
# Current deployed manifest
helm get manifest my-app > current.yaml

# Render new manifest
helm template my-app ./chart -f new-values.yaml > new.yaml

# Compare
diff current.yaml new.yaml
```

### Example 2: Validate across multiple clusters

```bash
#!/bin/bash
for context in staging production; do
  echo "Validating on $context..."
  kubectl config use-context $context
  helm install test-app ./chart -f ${context}-values.yaml --dry-run --debug
done
```

### Example 3: Debug specific template

```bash
# Render just deployment
helm template test-release ./chart --show-only templates/deployment.yaml
```

### Example 4: Find which template is failing

```bash
# Render all templates separately
for tpl in templates/*.yaml; do
  echo "Rendering $tpl..."
  helm template test-release ./chart --show-only "$tpl" || echo "FAILED: $tpl"
done
```

### Example 5: Test with different value sets

```bash
# Test configurations
for env in dev staging prod; do
  echo "Testing $env configuration..."
  helm template my-app ./chart -f values-${env}.yaml | kubectl apply --dry-run=client -f -
done
```

---

## 📚 Key Takeaways

1. **helm lint** - Fast local validation (no cluster needed)
2. **helm template** - Local rendering, CI/CD friendly, no API validation
3. **--dry-run --debug** - Server-side validation, catches API version issues
4. **helm get manifest** - View actual deployed resources
5. **Template functions** - Powerful transformations (default, quote, nindent, etc.)
6. **Debugging workflow** - Lint → Template → Dry-run → Install → Verify
7. **Whitespace control** - Use `{{-` and `-}}` to control output formatting
8. **Built-in objects** - .Release, .Chart, .Values, .Capabilities
9. **Always validate** - Use multiple tools before production deploys
10. **Compare outputs** - Diff planned vs actual to catch issues early

---

## 🔗 Further Reading

- **Helm Template Guide**: https://helm.sh/docs/chart_template_guide/
- **Sprig Function Library**: https://masterminds.github.io/sprig/
- **Helm Debugging Tips**: https://helm.sh/docs/chart_template_guide/debugging/
- **Go Template Documentation**: https://pkg.go.dev/text/template
- **Helm Best Practices**: https://helm.sh/docs/chart_best_practices/

---

*This guide provides a comprehensive understanding of Helm templating and debugging. Master these tools to confidently create and troubleshoot Helm charts!*
