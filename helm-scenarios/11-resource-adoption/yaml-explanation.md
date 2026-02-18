# Helm Resource Adoption Explanation

This guide explains how to adopt existing Kubernetes resources into Helm management without deleting and recreating them. You'll learn how Helm tracks resource ownership, how to manually annotate resources for adoption, and how to create matching Helm charts for seamless takeover.

---

## 🎯 What is Resource Adoption?

**Resource adoption** is the process of bringing existing Kubernetes resources under Helm's management without disrupting them. This is critical when you have resources deployed via `kubectl apply` and want to transition to Helm-based deployments.

### The Problem

**Common production scenario:**
```bash
# Initially deployed manually
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# Now you want to use Helm
helm install my-app ./chart
# ❌ Error: resources already exist!
```

**Why this fails:**
- Helm tries to create resources
- Finds they already exist
- Refuses to proceed (safety mechanism)
- You're stuck between manual and Helm management

### The Solution: Adoption

**Without adoption (destructive):**
```bash
kubectl delete -f deployment.yaml    # ❌ Downtime!
kubectl delete -f service.yaml       # ❌ Downtime!
helm install my-app ./chart          # ✅ Works but caused downtime
```

**With adoption (zero-downtime):**
```bash
# Annotate existing resources
kubectl annotate deployment my-app meta.helm.sh/release-name=my-app
kubectl annotate deployment my-app meta.helm.sh/release-namespace=default
kubectl label deployment my-app app.kubernetes.io/managed-by=Helm

# Install with matching chart
helm install my-app ./chart          # ✅ Adopts existing resources, no downtime!
```

### Why Adoption Matters

- ✅ **Zero downtime** - Resources keep running during transition
- ✅ **Production-safe** - No service interruption
- ✅ **Gradual migration** - Move from kubectl to Helm incrementally
- ✅ **Brownfield support** - Helm can manage existing infrastructure
- ✅ **Disaster recovery** - Reconstruct Helm releases from existing resources

---

## 🔑 How Helm Tracks Resource Ownership

Helm uses **metadata annotations and labels** to determine which resources it manages.

### Ownership Metadata

#### Annotations (Required)

```yaml
metadata:
  annotations:
    meta.helm.sh/release-name: "adopted-app"
    meta.helm.sh/release-namespace: "helm-scenarios"
```

**meta.helm.sh/release-name**
- **Purpose:** Identifies which Helm release owns this resource
- **Format:** String matching the release name
- **Required:** Yes - Helm won't adopt without this

**meta.helm.sh/release-namespace**
- **Purpose:** Identifies which namespace the release lives in
- **Format:** String matching the namespace
- **Required:** Yes - Prevents cross-namespace conflicts

#### Labels (Required)

```yaml
metadata:
  labels:
    app.kubernetes.io/managed-by: "Helm"
```

**app.kubernetes.io/managed-by**
- **Purpose:** Indicates the tool managing this resource
- **Format:** String "Helm" (case-sensitive)
- **Required:** Yes - Part of Kubernetes recommended labels
- **Standard:** https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/

### How Helm Uses This Metadata

**During `helm install`:**
1. Renders templates to YAML manifests
2. For each resource, checks if it already exists in cluster
3. If exists, checks for ownership annotations
4. If annotations match this release name/namespace:
   - ✅ **Adopts** the resource (patches to match template)
5. If no annotations or different release:
   - ❌ **Fails** with "already exists" error

**During `helm upgrade`:**
- Updates all resources with matching ownership annotations
- Treats adopted resources same as originally-installed ones

**During `helm uninstall`:**
- Deletes all resources with matching ownership annotations
- Adopted resources are removed just like originally-created ones

### Helm's Internal Tracking

**Secret-based release records:**
```bash
kubectl get secrets -n helm-scenarios -l owner=helm
```

Output:
```
NAME                              TYPE                 DATA   AGE
sh.helm.release.v1.adopted-app.v1   helm.sh/release.v1   1      5m
```

**What's stored:**
- Release name and namespace
- Chart metadata
- Rendered manifests
- Values used
- Release status and history

**Adoption creates this Secret:**
- When you run `helm install` on annotated resources
- Helm stores the release record
- From that point on, Helm manages the full lifecycle

---

## 📁 File Structure for Adoption

```
11-resource-adoption/
├── existing-deployment.yaml     # Manual kubectl deployment (no Helm metadata)
├── existing-service.yaml        # Manual kubectl service (no Helm metadata)
├── Chart.yaml                   # Helm chart metadata
├── values.yaml                  # Chart values matching existing resources
├── templates/
│   ├── deployment.yaml          # Template matching existing-deployment.yaml
│   ├── service.yaml             # Template matching existing-service.yaml
│   └── _helpers.tpl             # Template helper functions
└── commands.json                # Scenario commands
```

### Key Principle: Templates Must Match Exactly

**The Helm templates must produce YAML identical to existing resources** (except for Helm-added metadata).

**Example:**

Existing deployment:
```yaml
spec:
  replicas: 2
  template:
    spec:
      containers:
      - image: nginx:1.24-alpine
```

Helm template must produce:
```yaml
spec:
  replicas: {{ .Values.replicaCount }}  # Must be 2
  template:
    spec:
      containers:
      - image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"  # Must be nginx:1.24-alpine
```

**If they don't match:**
- Helm will update the resource during adoption
- May cause rolling restart
- Could break functionality if changes are significant

---

## 📄 existing-deployment.yaml - Manual Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adopted-app
  namespace: helm-scenarios
  labels:
    app: adopted-app
    version: "v1"
spec:
  replicas: 2
  selector:
    matchLabels:
      app: adopted-app
  template:
    metadata:
      labels:
        app: adopted-app
        version: "v1"
    spec:
      containers:
        - name: nginx
          image: nginx:1.24-alpine
          ports:
            - containerPort: 80
              protocol: TCP
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 100m
              memory: 128Mi
```

### Field-by-Field Breakdown

#### metadata.name: adopted-app

**What it is:** Resource name in Kubernetes

**Critical for adoption:**
- Helm chart templates **MUST** produce this exact name
- If names don't match, Helm creates a new resource instead of adopting
- Chart template: `name: {{ include "adopted-app.fullname" . }}`
- Helper must return: `"adopted-app"` (not `"release-name-app"`)

#### metadata.namespace: helm-scenarios

**What it is:** Kubernetes namespace

**Adoption requirements:**
- Helm install must target same namespace: `-n helm-scenarios`
- Annotation must match: `meta.helm.sh/release-namespace: helm-scenarios`
- Cross-namespace adoption is **not possible**

#### metadata.labels

```yaml
labels:
  app: adopted-app
  version: "v1"
```

**What they are:** Key-value pairs for organization and selection

**Existing labels:**
- `app: adopted-app` - Application identifier
- `version: "v1"` - Application version

**After adoption, Helm adds:**
```yaml
labels:
  app: adopted-app
  version: "v1"
  app.kubernetes.io/name: adopted-app
  app.kubernetes.io/instance: adopted-app
  app.kubernetes.io/version: "v1"
  app.kubernetes.io/managed-by: Helm
  helm.sh/chart: adopted-app-1.0.0
```

**Label compatibility:**
- Existing labels are preserved
- Helm adds recommended Kubernetes labels
- `app.kubernetes.io/managed-by: Helm` is required for adoption

#### spec.replicas: 2

**What it is:** Number of pod replicas

**Adoption requirement:**
- Helm values must specify: `replicaCount: 2`
- Template renders: `replicas: {{ .Values.replicaCount }}`
- If different, Helm will scale during adoption

**Example mismatch:**
```yaml
# Existing: 2 replicas
# Helm values: replicaCount: 3
# Result: Helm scales to 3 during adoption (rolling update)
```

#### spec.selector.matchLabels

```yaml
selector:
  matchLabels:
    app: adopted-app
```

**What it is:** How Deployment finds its Pods

**Critical importance:**
- **MUST match exactly** between existing resource and Helm template
- Changing selectors causes Deployment recreation
- Helm template: `{{- include "adopted-app.selectorLabels" . | nindent 6 }}`
- Helper must return exactly: `app: adopted-app`

**Why this matters:**
```yaml
# If Helm template produces different selector:
selector:
  matchLabels:
    app.kubernetes.io/name: adopted-app  # ❌ Different from existing!
    app.kubernetes.io/instance: adopted-app
# Kubernetes will reject the update - selectors are immutable
```

#### spec.template.spec.containers

```yaml
containers:
  - name: nginx
    image: nginx:1.24-alpine
    ports:
      - containerPort: 80
        protocol: TCP
```

**Container name:** `nginx`
- Helm template must use same name
- Referenced in kubectl logs/exec commands

**Image:** `nginx:1.24-alpine`
- Helm values: `image.repository: nginx`, `image.tag: "1.24-alpine"`
- Template: `image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"`
- Must match exactly for seamless adoption

**Ports:**
- `containerPort: 80` - Where nginx listens inside container
- Must match service `targetPort`

#### resources

```yaml
resources:
  requests:
    cpu: 25m
    memory: 32Mi
  limits:
    cpu: 100m
    memory: 128Mi
```

**Requests:**
- `cpu: 25m` - Guaranteed 2.5% of 1 CPU core
- `memory: 32Mi` - Guaranteed 33.5 MB RAM

**Limits:**
- `cpu: 100m` - Max 10% of 1 CPU core
- `memory: 128Mi` - Max 134 MB RAM (OOM kill if exceeded)

**Adoption consideration:**
- If Helm values specify different resources, Pods will restart
- Use `--dry-run --debug` to verify template matches

---

## 📄 existing-service.yaml - Manual Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: adopted-app
  namespace: helm-scenarios
  labels:
    app: adopted-app
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 80
      protocol: TCP
      name: http
  selector:
    app: adopted-app
```

### Field-by-Field Breakdown

#### spec.type: ClusterIP

**What it is:** Service type (how it's exposed)

**Options:**
- `ClusterIP` - Internal cluster access only (default)
- `NodePort` - External access via Node IP:Port
- `LoadBalancer` - Cloud provider load balancer
- `ExternalName` - DNS CNAME alias

**Current:** ClusterIP (internal only)

**Adoption requirement:**
- Helm values: `service.type: ClusterIP`
- Changing type during adoption may cause brief connection disruption

#### spec.ports

```yaml
ports:
  - port: 80
    targetPort: 80
    protocol: TCP
    name: http
```

**port: 80**
- **What it is:** Port the Service listens on (cluster-internal)
- **Usage:** `curl http://adopted-app.helm-scenarios.svc:80`
- **Must match:** Helm values `service.port: 80`

**targetPort: 80**
- **What it is:** Port on the Pod/container to forward to
- **Must match:** Container's `containerPort: 80`
- **Helm values:** `service.targetPort: 80`

**name: http**
- **What it is:** Named port reference
- **Usage:** Can reference by name in other resources
- **Adoption:** Name must match template or be omitted

#### spec.selector

```yaml
selector:
  app: adopted-app
```

**What it is:** How Service finds backend Pods

**Critical importance:**
- Routes traffic to Pods with matching labels
- Must match Deployment's `spec.template.metadata.labels`
- Helm template must produce identical selector

**Traffic flow:**
```
Request → Service (adopted-app:80)
        ↓ Selector: app=adopted-app
        → Pod 1 (labels: app=adopted-app)
        → Pod 2 (labels: app=adopted-app)
```

**If selector changes during adoption:**
- Traffic may route to wrong Pods
- Could cause downtime if no Pods match new selector

---

## 📄 Chart.yaml - Chart Metadata

```yaml
apiVersion: v2
name: adopted-app
description: Chart for adopting existing Kubernetes resources into Helm management
type: application
version: 1.0.0
appVersion: "1.0.0"
maintainers:
  - name: k8s-simulator
```

### Field-by-Field Breakdown

#### apiVersion: v2

**What it is:** Helm chart API version

**Version history:**
- `v1` - Helm 2 (deprecated, legacy)
- `v2` - Helm 3 (current, required)

**Why v2:**
- Helm 3 requires v2
- Supports improved dependency management
- Better template functions

#### name: adopted-app

**What it is:** Chart name

**NOT used for resource naming:**
- Resource names come from templates (`{{ include "adopted-app.fullname" . }}`)
- Chart name is for Helm repository identification
- Can differ from release name and resource names

**Example:**
```bash
helm install my-release adopted-app/  # Chart name: adopted-app, Release: my-release
```

#### type: application

**What it is:** Chart purpose

**Options:**
- `application` - Deploys workloads (this scenario)
- `library` - Provides shared templates only

**Library charts:**
```yaml
type: library  # Cannot be installed, only used as dependency
```

#### version: 1.0.0

**What it is:** Chart version (not app version)

**Semantic versioning:**
- `1.0.0` - Major.Minor.Patch
- `1.0.1` - Bug fix (backwards compatible)
- `1.1.0` - New feature (backwards compatible)
- `2.0.0` - Breaking change

**When to increment:**
- Changed templates: bump patch or minor
- Changed default values: bump minor
- Breaking changes: bump major

#### appVersion: "1.0.0"

**What it is:** Version of the application being deployed

**Separate from chart version:**
- Chart `1.0.0` might deploy app `v1.24`
- Chart `1.0.1` might still deploy app `v1.24` (chart bug fix)
- Chart `1.1.0` might deploy app `v1.25` (app upgrade)

**Best practice:**
```yaml
appVersion: "1.24"  # Match application version
```

**Used in labels:**
```yaml
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
```

---

## 📄 values.yaml - Chart Values

```yaml
replicaCount: 2

image:
  repository: nginx
  tag: "1.24-alpine"

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

appVersion: "v1"
```

### Field-by-Field Breakdown

#### replicaCount: 2

**What it is:** Number of Pod replicas

**Critical requirement:**
- **MUST match** existing Deployment's `spec.replicas: 2`
- If different, Helm scales Deployment during adoption

**Verification:**
```bash
kubectl get deployment adopted-app -n helm-scenarios -o jsonpath='{.spec.replicas}'
# Output: 2
```

**What happens with mismatch:**
```yaml
# Existing: replicas: 2
# Helm values: replicaCount: 3
# During adoption: Helm scales from 2 → 3 replicas (rolling update)
```

#### image

```yaml
image:
  repository: nginx
  tag: "1.24-alpine"
```

**repository:** `nginx`
- Docker Hub repository
- Used in template: `{{ .Values.image.repository }}`
- Must match existing: `nginx`

**tag:** `"1.24-alpine"`
- Image tag/version
- **Quoted** to preserve YAML string type
- Used in template: `{{ .Values.image.tag }}`
- Must match existing: `1.24-alpine`

**Combined in template:**
```yaml
image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
# Renders to: nginx:1.24-alpine
```

**Why exact match matters:**
- Different image triggers Pod restart
- May pull new image (network traffic)
- Could break if image doesn't exist

#### service

```yaml
service:
  type: ClusterIP
  port: 80
  targetPort: 80
```

**type:** `ClusterIP`
- Must match existing Service type
- Changing type can cause connection disruption

**port:** `80`
- Service listens on port 80
- Must match existing `spec.ports[].port`

**targetPort:** `80`
- Forward to container port 80
- Must match container `containerPort`

**Helm template usage:**
```yaml
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
```

#### resources

```yaml
resources:
  requests:
    cpu: 25m
    memory: 32Mi
  limits:
    cpu: 100m
    memory: 128Mi
```

**Structure must match exactly:**

Existing deployment:
```yaml
resources:
  requests:
    cpu: 25m
    memory: 32Mi
```

Helm values:
```yaml
resources:
  requests:
    cpu: 25m      # ✅ Match
    memory: 32Mi  # ✅ Match
```

**Template usage:**
```yaml
resources:
  {{- toYaml .Values.resources | nindent 12 }}
# Renders entire resources block
```

**Mismatch impact:**
- Different requests: Pod rescheduled
- Different limits: Pod restarted
- Use dry-run to verify before adoption

#### appVersion: "v1"

**What it is:** Application version label

**Used in template:**
```yaml
labels:
  version: {{ .Values.appVersion | quote }}
```

**Must match existing:**
```yaml
# existing-deployment.yaml
labels:
  version: "v1"  # ← Must match values.yaml appVersion
```

**During upgrade:**
```bash
helm upgrade adopted-app ./chart --set appVersion=v2
# Changes label from v1 → v2
# Triggers rolling update
```

---

## 📄 templates/deployment.yaml - Helm Template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "adopted-app.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "adopted-app.labels" . | nindent 4 }}
    version: {{ .Values.appVersion | quote }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "adopted-app.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "adopted-app.selectorLabels" . | nindent 8 }}
        version: {{ .Values.appVersion | quote }}
    spec:
      containers:
        - name: nginx
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          ports:
            - containerPort: {{ .Values.service.targetPort }}
              protocol: TCP
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

### Template Functions Explained

#### {{ include "adopted-app.fullname" . }}

**What it does:** Generates resource name

**Defined in:** `_helpers.tpl`

**Returns:** `"adopted-app"` (hardcoded for adoption)

**Critical for adoption:**
```yaml
# _helpers.tpl
{{- define "adopted-app.fullname" -}}
adopted-app  # ← Hardcoded to match existing resource name
{{- end -}}
```

**Normal Helm charts use:**
```yaml
{{- define "chart.fullname" -}}
{{ .Release.Name }}-{{ .Chart.Name }}  # Dynamic naming
{{- end -}}
```

**Why hardcoded for adoption:**
- Existing resource has fixed name: `adopted-app`
- Template must produce exact same name
- Dynamic naming would create new resource

#### {{ .Release.Namespace }}

**What it is:** Namespace where Helm release is installed

**Set by:** `helm install ... -n helm-scenarios`

**Renders to:** `helm-scenarios`

**Must match:**
- Existing resource namespace
- Adoption annotation: `meta.helm.sh/release-namespace: helm-scenarios`

#### {{ include "adopted-app.labels" . | nindent 4 }}

**What it does:** Inserts common labels with 4-space indent

**Defined in:** `_helpers.tpl`

**Renders to:**
```yaml
app: adopted-app
app.kubernetes.io/name: adopted-app
app.kubernetes.io/instance: adopted-app
app.kubernetes.io/version: "v1"
app.kubernetes.io/managed-by: Helm
helm.sh/chart: adopted-app-1.0.0
```

**Includes Kubernetes recommended labels:**
- `app.kubernetes.io/name` - Application name
- `app.kubernetes.io/instance` - Release instance
- `app.kubernetes.io/version` - Application version
- `app.kubernetes.io/managed-by` - "Helm" (required for adoption)

#### {{ include "adopted-app.selectorLabels" . | nindent 6 }}

**What it does:** Inserts selector labels

**Defined in:** `_helpers.tpl`

**Renders to:**
```yaml
app: adopted-app
```

**Critical importance:**
- **MUST match** existing Deployment selector
- Selectors are immutable in Deployments
- Changing selector requires Deployment deletion/recreation

**Why minimal selector:**
- Only `app: adopted-app`
- Does NOT include version-specific labels
- Allows label changes without Deployment recreation

#### {{ toYaml .Values.resources | nindent 12 }}

**What it does:** Converts values to YAML and indents

**Input (.Values.resources):**
```yaml
requests:
  cpu: 25m
  memory: 32Mi
limits:
  cpu: 100m
  memory: 128Mi
```

**Output (rendered):**
```yaml
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 100m
              memory: 128Mi
```

**Why use toYaml:**
- Preserves complex YAML structure
- Handles nested values correctly
- Simpler than manual templating

---

## 📄 templates/service.yaml - Service Template

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "adopted-app.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "adopted-app.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      protocol: TCP
      name: http
  selector:
    {{- include "adopted-app.selectorLabels" . | nindent 4 }}
```

### Template Breakdown

#### metadata.name

**Template:** `{{ include "adopted-app.fullname" . }}`

**Renders to:** `adopted-app`

**Must match:** Existing Service name

**Why critical:**
- DNS name for service: `adopted-app.helm-scenarios.svc.cluster.local`
- Clients connect via this name
- Different name = new service = new DNS entry

#### spec.selector

**Template:** `{{- include "adopted-app.selectorLabels" . | nindent 4 }}`

**Renders to:**
```yaml
selector:
  app: adopted-app
```

**Routes traffic to Pods with:** `labels: { app: adopted-app }`

**Must match existing:**
- Existing Service selector
- Deployment Pod labels
- Otherwise traffic routes incorrectly

---

## 📄 templates/_helpers.tpl - Template Helpers

```yaml
{{/*
Generate the full name for resources.
Must match the existing resource names exactly for adoption to work.
*/}}
{{- define "adopted-app.fullname" -}}
adopted-app
{{- end -}}

{{/*
Common labels applied to all resources.
*/}}
{{- define "adopted-app.labels" -}}
app: adopted-app
app.kubernetes.io/name: adopted-app
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.appVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/*
Selector labels -- must match the existing deployment's matchLabels exactly.
*/}}
{{- define "adopted-app.selectorLabels" -}}
app: adopted-app
{{- end -}}
```

### Helper Functions Explained

#### adopted-app.fullname

**Purpose:** Generate resource names

**Standard Helm pattern:**
```yaml
{{- define "chart.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 }}
{{- end -}}
```

**Adoption pattern:**
```yaml
{{- define "adopted-app.fullname" -}}
adopted-app  # Hardcoded to match existing
{{- end -}}
```

**Why hardcoded:**
- Existing resources have fixed names
- Dynamic naming creates new resources
- Adoption requires exact name match

**Example impact:**
```bash
# Standard chart (dynamic naming):
helm install my-release ./chart
# Creates: my-release-nginx

# Adoption chart (hardcoded):
helm install adopted-app ./chart
# Adopts: adopted-app (exact match)
```

#### adopted-app.labels

**Purpose:** Generate common labels for all resources

**Renders to:**
```yaml
app: adopted-app
app.kubernetes.io/name: adopted-app
app.kubernetes.io/instance: adopted-app
app.kubernetes.io/version: "v1"
app.kubernetes.io/managed-by: Helm
helm.sh/chart: adopted-app-1.0.0
```

**Breakdown:**

**app: adopted-app**
- Custom label (from existing deployment)
- Used for selector matching

**app.kubernetes.io/name: adopted-app**
- Kubernetes recommended label
- Application name
- Useful for grouping: `kubectl get all -l app.kubernetes.io/name=adopted-app`

**app.kubernetes.io/instance: {{ .Release.Name }}**
- Helm release name
- Distinguishes multiple deployments of same chart
- Value: `adopted-app` (release name)

**app.kubernetes.io/version: {{ .Values.appVersion | quote }}**
- Application version
- From `values.yaml` appVersion
- Value: `"v1"`

**app.kubernetes.io/managed-by: {{ .Release.Service }}**
- **CRITICAL for adoption**
- `.Release.Service` is always `"Helm"`
- Required for Helm to recognize ownership

**helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}**
- Full chart identifier
- Format: `chart-name-version`
- Value: `adopted-app-1.0.0`

#### adopted-app.selectorLabels

**Purpose:** Generate selector labels (subset of common labels)

**Renders to:**
```yaml
app: adopted-app
```

**Why minimal:**
- **Selectors are immutable** in Deployments and Services
- Adding labels to selector requires resource recreation
- Minimal selector allows label evolution

**Anti-pattern (too many selector labels):**
```yaml
{{- define "chart.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.appVersion }}  # ❌ BAD: version in selector
{{- end -}}
```

**Problem:**
- Changing app version requires Deployment deletion
- Prevents rolling updates
- Breaks Helm upgrade workflow

**Best practice (minimal selector):**
```yaml
{{- define "chart.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
```

---

## 🔄 Adoption Workflow

### Step-by-Step Process

#### 1. Deploy Resources Manually

```bash
kubectl apply -f existing-deployment.yaml
kubectl apply -f existing-service.yaml
```

**State:**
- Resources exist in cluster
- No Helm annotations/labels
- Deployed via kubectl (not Helm)

**Verify:**
```bash
kubectl get deployment,service adopted-app -n helm-scenarios
```

#### 2. Verify Resources Have No Helm Metadata

```bash
kubectl get deployment adopted-app -n helm-scenarios -o jsonpath='{.metadata.annotations}' | python3 -m json.tool
```

**Expected output:**
```json
{
  "kubectl.kubernetes.io/last-applied-configuration": "..."
}
```

**No Helm annotations:**
- No `meta.helm.sh/release-name`
- No `meta.helm.sh/release-namespace`
- No `app.kubernetes.io/managed-by: Helm` label

#### 3. Attempt Helm Install (Fails Without Annotations)

```bash
helm install adopted-app ./chart -n helm-scenarios
```

**Error:**
```
Error: rendered manifests contain a resource that already exists.
Unable to continue with install: Deployment "adopted-app" in namespace
"helm-scenarios" exists and cannot be imported into the current release
```

**Why it fails:**
- Helm tries to create Deployment
- Kubernetes says it already exists
- Helm refuses to overwrite (safety mechanism)

#### 4. Annotate Deployment for Adoption

```bash
kubectl annotate deployment adopted-app -n helm-scenarios \
  meta.helm.sh/release-name=adopted-app \
  meta.helm.sh/release-namespace=helm-scenarios \
  --overwrite

kubectl label deployment adopted-app -n helm-scenarios \
  app.kubernetes.io/managed-by=Helm \
  --overwrite
```

**What this does:**
- Adds `meta.helm.sh/release-name: adopted-app`
- Adds `meta.helm.sh/release-namespace: helm-scenarios`
- Adds `app.kubernetes.io/managed-by: Helm` label

**Annotations must match:**
- Release name: `adopted-app` (from `helm install adopted-app`)
- Namespace: `helm-scenarios` (from `-n helm-scenarios`)

#### 5. Annotate Service for Adoption

```bash
kubectl annotate service adopted-app -n helm-scenarios \
  meta.helm.sh/release-name=adopted-app \
  meta.helm.sh/release-namespace=helm-scenarios \
  --overwrite

kubectl label service adopted-app -n helm-scenarios \
  app.kubernetes.io/managed-by=Helm \
  --overwrite
```

**Every resource needs annotations:**
- Deployment: ✅ Annotated
- Service: ✅ Annotated
- ConfigMaps: Need annotation if in chart
- Secrets: Need annotation if in chart

**Missed resource = adoption fails for that resource**

#### 6. Verify Annotations Applied

```bash
kubectl get deployment adopted-app -n helm-scenarios -o jsonpath='{.metadata.annotations}' | python3 -m json.tool
```

**Expected output:**
```json
{
  "meta.helm.sh/release-name": "adopted-app",
  "meta.helm.sh/release-namespace": "helm-scenarios",
  "kubectl.kubernetes.io/last-applied-configuration": "..."
}
```

**Check labels:**
```bash
kubectl get deployment adopted-app -n helm-scenarios -o jsonpath='{.metadata.labels}' | python3 -m json.tool
```

**Expected:**
```json
{
  "app": "adopted-app",
  "app.kubernetes.io/managed-by": "Helm",
  "version": "v1"
}
```

#### 7. Install Chart to Adopt Resources

```bash
helm install adopted-app ./chart -n helm-scenarios --wait
```

**What happens:**
1. Helm renders templates
2. Checks if Deployment exists
3. Finds ownership annotations matching this release
4. **Adopts** Deployment (patches to match template)
5. Repeats for Service
6. Creates release Secret

**No downtime:**
- Resources continue running
- Helm updates in-place
- Pods may restart if template differs

**Verify adoption:**
```bash
helm list -n helm-scenarios
```

Output:
```
NAME         NAMESPACE       REVISION  STATUS    CHART
adopted-app  helm-scenarios  1         deployed  adopted-app-1.0.0
```

#### 8. Verify Helm Management

```bash
helm status adopted-app -n helm-scenarios --show-resources
```

**Output:**
```
NAME: adopted-app
LAST DEPLOYED: ...
NAMESPACE: helm-scenarios
STATUS: deployed
REVISION: 1

RESOURCES:
==> v1/Service
NAME          TYPE        CLUSTER-IP     PORT(S)
adopted-app   ClusterIP   10.96.100.50   80/TCP

==> v1/Deployment
NAME          READY  UP-TO-DATE  AVAILABLE
adopted-app   2/2    2           2
```

**Helm now tracks:**
- Deployment
- Service
- Release history
- Rendered manifests

#### 9. Prove Control: Upgrade via Helm

```bash
helm upgrade adopted-app ./chart -n helm-scenarios \
  --set replicaCount=3 \
  --set appVersion=v2 \
  --set image.tag=1.25-alpine \
  --wait
```

**What this does:**
- Scales from 2 → 3 replicas
- Changes version label from v1 → v2
- Updates image from 1.24-alpine → 1.25-alpine

**Why this proves control:**
- Helm can modify adopted resources
- Performs rolling update
- Tracks revision history
- Full lifecycle management restored

#### 10. Verify Upgrade

```bash
kubectl get pods -n helm-scenarios -l app=adopted-app
```

**Expected:** 3 pods running (up from 2)

**Check image:**
```bash
kubectl get deployment adopted-app -n helm-scenarios -o jsonpath='{.spec.template.spec.containers[0].image}'
```

**Expected:** `nginx:1.25-alpine` (updated from 1.24)

**Check Helm history:**
```bash
helm history adopted-app -n helm-scenarios
```

**Output:**
```
REVISION  UPDATED                   STATUS      CHART             DESCRIPTION
1         Mon Jan 15 10:00:00 2024  superseded  adopted-app-1.0.0 Install complete
2         Mon Jan 15 10:05:00 2024  deployed    adopted-app-1.0.0 Upgrade complete
```

**Adoption complete:**
- ✅ Resources under Helm management
- ✅ Can upgrade via Helm
- ✅ Full revision history
- ✅ Can rollback via Helm

---

## 🎓 Real-World Adoption Scenarios

### Scenario 1: Migrating kubectl-based Infrastructure

**Problem:**
```bash
# 50 microservices deployed via kubectl
kubectl apply -f service-1/
kubectl apply -f service-2/
# ... manually managed, no standardization
```

**Solution: Gradual Helm adoption**

1. **Audit existing resources:**
```bash
kubectl get all -n production -o yaml > current-state.yaml
```

2. **Create Helm chart matching first service:**
```bash
helm create service-1-chart
# Edit templates to match existing resources
```

3. **Dry-run to verify match:**
```bash
helm template service-1 ./service-1-chart > rendered.yaml
diff <(kubectl get deployment service-1 -o yaml) rendered.yaml
# Ensure minimal differences (only Helm metadata)
```

4. **Annotate and adopt:**
```bash
kubectl annotate deployment service-1 \
  meta.helm.sh/release-name=service-1 \
  meta.helm.sh/release-namespace=production
kubectl label deployment service-1 app.kubernetes.io/managed-by=Helm

helm install service-1 ./service-1-chart -n production
```

5. **Repeat for remaining services**

### Scenario 2: Disaster Recovery

**Problem:**
- Helm release secret deleted
- Resources still running
- Cannot upgrade/rollback via Helm

**Solution: Re-adopt resources**

1. **Reconstruct values from running resources:**
```bash
kubectl get deployment my-app -o jsonpath='{.spec.replicas}'  # 3
kubectl get deployment my-app -o jsonpath='{.spec.template.spec.containers[0].image}'  # nginx:1.24
```

2. **Create values.yaml:**
```yaml
replicaCount: 3
image:
  repository: nginx
  tag: "1.24"
```

3. **Annotate resources:**
```bash
for resource in deployment service configmap; do
  kubectl annotate $resource my-app \
    meta.helm.sh/release-name=my-app \
    meta.helm.sh/release-namespace=default
  kubectl label $resource my-app app.kubernetes.io/managed-by=Helm
done
```

4. **Reinstall release:**
```bash
helm install my-app ./chart --values values.yaml
# Recreates Helm release secret
# Restores lifecycle management
```

### Scenario 3: Brownfield Kubernetes Adoption

**Problem:**
- Inherited cluster with 100+ manually-deployed resources
- No documentation
- Need Helm management for standardization

**Solution: Systematic adoption**

1. **Discovery:**
```bash
kubectl get all --all-namespaces -o json | \
  jq -r '.items[] | select(.metadata.labels."app.kubernetes.io/managed-by" != "Helm") |
  "\(.kind) \(.metadata.namespace) \(.metadata.name)"'
```

2. **Group by application:**
```bash
# Find related resources by labels
kubectl get all -n production -l app=webapp -o name
```

3. **Reverse-engineer chart:**
```bash
# Export current state
kubectl get deployment webapp -o yaml --export > deployment.yaml
kubectl get service webapp -o yaml --export > service.yaml

# Create chart templates
helm create webapp-chart
# Copy exported YAMLs to templates/, parameterize with values
```

4. **Bulk annotation script:**
```bash
#!/bin/bash
RELEASE="webapp"
NAMESPACE="production"
RESOURCES=("deployment/webapp" "service/webapp" "configmap/webapp-config")

for resource in "${RESOURCES[@]}"; do
  kubectl annotate $resource -n $NAMESPACE \
    meta.helm.sh/release-name=$RELEASE \
    meta.helm.sh/release-namespace=$NAMESPACE
  kubectl label $resource -n $NAMESPACE \
    app.kubernetes.io/managed-by=Helm
done

helm install $RELEASE ./webapp-chart -n $NAMESPACE
```

---

## 🐛 Troubleshooting Adoption

### Error: "cannot re-use a name that is still in use"

**Full error:**
```
Error: cannot re-use a name that is still in use
```

**Cause:** Resource exists but has no Helm ownership annotations

**Solution:**
```bash
# Annotate the resource
kubectl annotate <kind> <name> -n <namespace> \
  meta.helm.sh/release-name=<release> \
  meta.helm.sh/release-namespace=<namespace>

kubectl label <kind> <name> -n <namespace> \
  app.kubernetes.io/managed-by=Helm
```

### Error: "rendered manifests contain a resource that already exists"

**Full error:**
```
Error: rendered manifests contain a resource that already exists.
Unable to continue with install: Deployment "app" in namespace "default"
exists and cannot be imported into the current release
```

**Cause:** Same as above - missing ownership annotations

**Solution:** Add annotations as shown above

### Adoption Succeeds But Pods Restart

**Symptom:**
```bash
helm install my-app ./chart -n default
# Pods immediately restart
```

**Cause:** Template output differs from existing resource

**Debug:**
```bash
# Compare existing resource
kubectl get deployment my-app -o yaml > existing.yaml

# Compare template output
helm template my-app ./chart > rendered.yaml

# Find differences
diff existing.yaml rendered.yaml
```

**Common differences:**
- Image tag mismatch
- Resource limits different
- Environment variables changed
- Labels/annotations added

**Fix:** Adjust `values.yaml` to match existing resource exactly

### Some Resources Adopted, Others Failed

**Symptom:**
```bash
helm install my-app ./chart
# Deployment adopted ✅
# Service failed ❌
```

**Cause:** Forgot to annotate all resources

**Solution:** Annotate every resource in the chart

**Find unannotated resources:**
```bash
kubectl get all -n default -o json | \
  jq -r '.items[] |
  select(.metadata.annotations."meta.helm.sh/release-name" == null) |
  "\(.kind) \(.metadata.name)"'
```

### Selector Immutability Error

**Error:**
```
The Deployment "app" is invalid: spec.selector: Invalid value:
selector is immutable after creation
```

**Cause:** Chart template produces different selector than existing Deployment

**Existing:**
```yaml
selector:
  matchLabels:
    app: my-app
```

**Template produces:**
```yaml
selector:
  matchLabels:
    app.kubernetes.io/name: my-app
    app.kubernetes.io/instance: release-name
```

**Solution 1: Fix template to match existing**
```yaml
# _helpers.tpl
{{- define "chart.selectorLabels" -}}
app: my-app  # Match existing exactly
{{- end -}}
```

**Solution 2: Delete and recreate (downtime)**
```bash
kubectl delete deployment my-app
helm install my-app ./chart
# ❌ Causes downtime
```

**Best practice:** Always match existing selector exactly

---

## ✅ Best Practices for Resource Adoption

### Before Adoption

**1. Audit Existing Resources**

```bash
# List all resources for the application
kubectl get all -n <namespace> -l app=<app-name>

# Export current state for reference
kubectl get deployment <name> -n <namespace> -o yaml > backup-deployment.yaml
kubectl get service <name> -n <namespace> -o yaml > backup-service.yaml
```

**2. Create Matching Chart**

```bash
# Create chart skeleton
helm create my-chart

# Compare template output with existing
helm template test my-chart > rendered.yaml
diff <(kubectl get deployment my-app -o yaml) rendered.yaml
```

**3. Verify with Dry-Run**

```bash
# Render templates without installing
helm install my-app ./chart --dry-run --debug

# Check for differences
helm diff upgrade my-app ./chart  # (requires helm-diff plugin)
```

### During Adoption

**1. Annotate All Resources**

```bash
# Create script for consistency
cat > annotate.sh << 'EOF'
#!/bin/bash
RELEASE=$1
NAMESPACE=$2
RESOURCE_TYPE=$3
RESOURCE_NAME=$4

kubectl annotate $RESOURCE_TYPE $RESOURCE_NAME -n $NAMESPACE \
  meta.helm.sh/release-name=$RELEASE \
  meta.helm.sh/release-namespace=$NAMESPACE \
  --overwrite

kubectl label $RESOURCE_TYPE $RESOURCE_NAME -n $NAMESPACE \
  app.kubernetes.io/managed-by=Helm \
  --overwrite
EOF

chmod +x annotate.sh
./annotate.sh my-app default deployment my-app
./annotate.sh my-app default service my-app
```

**2. Use --wait Flag**

```bash
helm install my-app ./chart -n default --wait --timeout 5m
# Waits for resources to be ready
# Rolls back on failure
```

**3. Test Before Production**

```bash
# Adopt in staging first
helm install my-app ./chart -n staging
helm test my-app -n staging

# Then production
helm install my-app ./chart -n production
```

### After Adoption

**1. Verify Helm Management**

```bash
# Check release exists
helm list -n <namespace>

# Verify resources tracked
helm status <release> -n <namespace> --show-resources

# Test upgrade
helm upgrade <release> ./chart -n <namespace> --dry-run
```

**2. Document Adoption**

```markdown
# Adoption Log

## Application: my-app
## Date: 2024-01-15
## Engineer: DevOps Team

### Resources Adopted:
- Deployment: my-app (2 replicas)
- Service: my-app (ClusterIP)
- ConfigMap: my-app-config

### Chart Version: 1.0.0
### Helm Release: my-app
### Namespace: production

### Post-Adoption Tests:
- [x] helm status shows all resources
- [x] helm upgrade dry-run succeeds
- [x] Application functionality verified
- [x] Logs show no errors
```

**3. Enable GitOps (Optional)**

```bash
# Store chart in Git
git add charts/my-app/
git commit -m "Add Helm chart for my-app (adopted from kubectl)"

# Deploy via ArgoCD
argocd app create my-app \
  --repo https://github.com/org/charts \
  --path charts/my-app \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace production
```

### General Best Practices

**1. Match Exactly First, Improve Later**

```bash
# Phase 1: Adopt with exact match (no changes)
helm install my-app ./chart  # Chart matches existing 100%

# Phase 2: Gradual improvements
helm upgrade my-app ./chart --set replicaCount=3  # Scale up
helm upgrade my-app ./chart --set image.tag=v2     # Update version
```

**2. Use Helm Diff Plugin**

```bash
# Install plugin
helm plugin install https://github.com/databus23/helm-diff

# Preview changes before upgrade
helm diff upgrade my-app ./chart
```

**3. Keep Values Separate from Chart**

```bash
# Chart in Git
charts/my-app/
  Chart.yaml
  templates/

# Values in separate repo (with secrets management)
values/
  my-app-dev.yaml
  my-app-staging.yaml
  my-app-prod.yaml.enc  # Encrypted with SOPS

# Deploy
helm install my-app charts/my-app \
  -f <(sops -d values/my-app-prod.yaml.enc)
```

**4. Automate Annotation**

```yaml
# Kubernetes operator or script
apiVersion: batch/v1
kind: Job
metadata:
  name: helm-adoption-annotator
spec:
  template:
    spec:
      containers:
      - name: annotator
        image: bitnami/kubectl:latest
        command:
        - /bin/bash
        - -c
        - |
          kubectl annotate deployment my-app \
            meta.helm.sh/release-name=my-app \
            meta.helm.sh/release-namespace=default
          kubectl label deployment my-app \
            app.kubernetes.io/managed-by=Helm
```

---

## 🔗 Further Reading

- **Helm Resource Adoption**: https://helm.sh/docs/topics/advanced/#adopting-existing-resources
- **Kubernetes Recommended Labels**: https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/
- **Helm Templates Guide**: https://helm.sh/docs/chart_template_guide/
- **Helm Diff Plugin**: https://github.com/databus23/helm-diff
- **Helm Best Practices**: https://helm.sh/docs/chart_best_practices/
- **GitOps with Helm**: https://www.gitops.tech/#helm

---

*This guide provides comprehensive coverage of Helm resource adoption. Mastering adoption enables zero-downtime migration from manual kubectl deployments to Helm-managed infrastructure, a critical skill for production Kubernetes operations!*
