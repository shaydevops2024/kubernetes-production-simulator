# YAML Files Explanation - ConfigMap & Secrets Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 📄 configmap.yaml

### What is a ConfigMap?
A ConfigMap is a Kubernetes object that stores **non-sensitive** configuration data as key-value pairs. It decouples configuration from container images, making applications portable across environments.

### YAML Structure Breakdown:

```yaml
apiVersion: v1
```
**What it is:** The API version for ConfigMap resources
**Options:** `v1` is the stable version for ConfigMaps
**Why:** Kubernetes uses API versioning to maintain backward compatibility

```yaml
kind: ConfigMap
```
**What it is:** Declares this is a ConfigMap resource
**Options:** ConfigMap, Secret, Deployment, Service, etc.
**Why:** Tells Kubernetes what type of object to create

```yaml
metadata:
  name: app-config
  namespace: scenarios
```
**What it is:** Metadata identifying the ConfigMap
- `name`: Unique identifier within the namespace (used to reference in pods)
- `namespace`: The namespace where this ConfigMap lives

**Naming Options:** Use lowercase alphanumeric + hyphens, must be DNS-compliant
**Why:** Pods reference ConfigMaps by name, so it must be unique within the namespace

```yaml
data:
  app.color: "blue"
  app.mode: "production"
  log.level: "info"
```
**What it is:** Simple key-value pairs
**How to use:**
- Keys: Any string (often use dot notation for hierarchy)
- Values: String data (numbers/booleans must be quoted)
**Alternatives:** Can also use `binaryData` for non-UTF8 data
**Why:** Provides configuration that can be injected as environment variables or files

```yaml
  config.json: |
    {
      "environment": "production",
      "debug": false,
      "max_connections": 100
    }
```
**What it is:** Multi-line string data (using YAML `|` literal block scalar)
**How to use:** Great for config files (JSON, YAML, XML, properties files)
**Why:** Pods can mount this as a file at a specific path
**Options:**
- `|` preserves line breaks
- `>` folds newlines into spaces
- `|-` strips trailing newline

### How Pods Use ConfigMaps:
1. **Environment Variables:** `valueFrom.configMapKeyRef`
2. **Volume Mounts:** Mount entire ConfigMap or specific keys as files
3. **Command Arguments:** Reference via `$(KEY_NAME)`

### Best Practices:
✅ Use for non-sensitive data only
✅ Keep ConfigMaps under 1MB (etcd limit)
✅ Use meaningful, hierarchical key names
✅ Consider marking as `immutable: true` for production (better performance, prevents accidental changes)

---

## 🔐 secret.yaml

### What is a Secret?
A Secret is similar to a ConfigMap but designed for **sensitive** data like passwords, tokens, SSH keys, and TLS certificates. Data is base64-encoded (NOT encrypted by default).

### YAML Structure Breakdown:

```yaml
apiVersion: v1
kind: Secret
```
**What it is:** Standard API version and resource type for Secrets
**Why:** Uses the same v1 API as ConfigMaps

```yaml
metadata:
  name: db-credentials
  namespace: scenarios
```
**What it is:** Identifies the Secret
- `name`: Reference this name in pod specs
- `namespace`: Must match the namespace of pods using it

**Why:** Secrets are namespace-scoped for security isolation

```yaml
type: Opaque
```
**What it is:** The type of Secret
**Options:**
- `Opaque` - Generic user-defined data (most common)
- `kubernetes.io/tls` - TLS certificates (requires tls.crt and tls.key)
- `kubernetes.io/dockerconfigjson` - Docker registry credentials
- `kubernetes.io/basic-auth` - Basic authentication credentials
- `kubernetes.io/ssh-auth` - SSH authentication
- `kubernetes.io/service-account-token` - Service account tokens

**Why:** Type determines structure and validation rules
**When to use Opaque:** Default choice for custom data like database credentials

```yaml
data:
  username: YWRtaW4=
  password: c3VwZXJzZWNyZXQxMjM=
```
**What it is:** Base64-encoded key-value pairs
**How to encode:**
```bash
echo -n 'admin' | base64          # YWRtaW4=
echo -n 'supersecret123' | base64 # c3VwZXJzZWNyZXQxMjM=
```
**How to decode:**
```bash
echo 'YWRtaW4=' | base64 -d       # admin
```

**Important:** Base64 is **encoding**, not **encryption**! Anyone with access can decode it.

**Alternative - stringData field:**
```yaml
stringData:
  username: admin
  password: supersecret123
```
**What it does:** Kubernetes automatically base64-encodes these for you
**When to use:** Convenience in development; avoid in version control
**Why:** `stringData` is write-only - when you `kubectl get`, you'll see `data` field with base64

### Security Considerations:
⚠️ **Secrets are NOT encrypted by default** in etcd (Kubernetes datastore)
✅ Enable **encryption at rest** in production: `--encryption-provider-config`
✅ Use **RBAC** to restrict who can read Secrets
✅ Consider **external secret managers** (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault)
✅ Never commit Secrets to Git (use `.gitignore` or sealed-secrets)
✅ Use **stringData** for local development only

### How Pods Use Secrets:
1. **Environment Variables:** `valueFrom.secretKeyRef` (less secure - visible in pod spec)
2. **Volume Mounts:** Mount as files (more secure - files are tmpfs, not written to disk)

---

## 🚀 deployment.yaml

### What is a Deployment?
A Deployment manages a set of identical pods, ensuring desired replicas are running, handling rolling updates, and managing rollbacks.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
```
**What it is:** API version for Deployments
**Options:** `apps/v1` is the current stable version
**Why:** Deployments are part of the `apps` API group

```yaml
kind: Deployment
```
**What it is:** Declares this is a Deployment resource
**Alternatives:** StatefulSet (for stateful apps), DaemonSet (one pod per node), Job, CronJob

```yaml
metadata:
  name: configmap-demo-app
  namespace: scenarios
  labels:
    app: configmap-demo
    scenario: "04"
```
**What it is:** Metadata for the Deployment object
- `name`: Unique deployment name (used in `kubectl` commands)
- `namespace`: Where this deployment lives
- `labels`: Key-value pairs for organization and selection

**Why labels?**
- Organize resources (`kubectl get deploy -l app=configmap-demo`)
- Used by Services to select pods
- Used by Helm, monitoring tools, etc.

**Best practices:** Use consistent label keys (`app`, `version`, `environment`, `component`)

```yaml
spec:
  replicas: 2
```
**What it is:** Desired number of pod copies
**Options:** Any integer ≥ 0
**Why:**
- High availability (if one pod fails, traffic routes to others)
- Load distribution
- Zero-downtime deployments (rolling updates)

**When to use 1:** Development, testing, stateful apps (use StatefulSet instead)
**Production:** Usually 2-3+ for critical services

```yaml
  selector:
    matchLabels:
      app: configmap-demo
```
**What it is:** How the Deployment finds its pods
**Critical:** Must match `template.metadata.labels`
**Why:** Deployments don't own pods - they select them by labels
**Options:**
- `matchLabels`: Simple equality-based selection
- `matchExpressions`: Complex logic (In, NotIn, Exists, DoesNotExist)

**⚠️ Common mistake:** Selector and template labels don't match → Deployment can't find pods

```yaml
  template:
    metadata:
      labels:
        app: configmap-demo
```
**What it is:** Template for creating pods
**Why:** This is the actual pod specification
**Labels:** Must include all selector labels (can have more)

```yaml
    spec:
      containers:
      - name: app
        image: nginx:1.21-alpine
```
**What it is:** Container specification
- `name`: Container name within the pod (for `kubectl exec`, logs)
- `image`: Docker image to run

**Image options:**
- `nginx:1.21-alpine` - Specific version + variant (recommended)
- `nginx:1.21` - Version without variant
- `nginx:latest` - Avoid! Not reproducible
- `nginx` - Defaults to :latest (avoid!)

**Best practice:** Always pin versions for reproducibility

```yaml
        ports:
        - containerPort: 80
```
**What it is:** Ports the container exposes
**Why:** Documentation and network policies (doesn't actually open ports)
**Options:**
- `containerPort`: Port number (1-65535)
- `name`: Optional name for the port
- `protocol`: TCP (default) or UDP

```yaml
        env:
        - name: APP_COLOR
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: app.color
```
**What it is:** Environment variable from ConfigMap
**How it works:**
1. Pod starts
2. Kubernetes reads ConfigMap `app-config`
3. Gets value of key `app.color` (currently "blue")
4. Sets `APP_COLOR=blue` in container

**⚠️ Important:** Changes to ConfigMap don't update existing env vars! Must restart pods.

**Alternative - Direct value:**
```yaml
env:
- name: MY_VAR
  value: "hardcoded-value"
```

**Alternative - All ConfigMap keys:**
```yaml
envFrom:
- configMapRef:
    name: app-config
```
This creates env vars for ALL keys (app.color → APP_COLOR)

```yaml
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: password
```
**What it is:** Environment variables from Secret
**How it works:** Same as ConfigMap, but reads from Secret
**Security note:** Env vars are visible in:
- Pod spec (`kubectl describe pod`)
- Container inspect
- Process listing inside container
- Application crash dumps

**More secure alternative:** Use volume mounts (see below)

```yaml
        volumeMounts:
        - name: config-volume
          mountPath: /etc/config
```
**What it is:** Mount a volume into the container filesystem
**How it works:**
1. Volume `config-volume` is mounted at `/etc/config`
2. Each ConfigMap key becomes a file: `/etc/config/app.color`, `/etc/config/config.json`
3. File contents = ConfigMap values

**Why use volumes vs env vars?**
✅ Volumes: Auto-update when ConfigMap changes (after kubelet sync delay)
✅ Volumes: More secure for secrets (tmpfs, not visible in pod spec)
✅ Volumes: Supports large files
❌ Env vars: Faster access, no file I/O
❌ Env vars: Limited size, no auto-update

**Advanced options:**
```yaml
volumeMounts:
- name: config-volume
  mountPath: /etc/config
  readOnly: true           # Prevent container from modifying
  subPath: config.json     # Mount only specific file, not entire ConfigMap
```

```yaml
      volumes:
      - name: config-volume
        configMap:
          name: app-config
```
**What it is:** Volume definition - declares a ConfigMap as a volume
**How it works:** References ConfigMap `app-config` by name
**Must match:** `volumeMounts.name` must equal `volumes.name`

**Advanced options:**
```yaml
volumes:
- name: config-volume
  configMap:
    name: app-config
    items:                 # Select specific keys
    - key: config.json
      path: app-config.json  # Rename file
    defaultMode: 0644      # File permissions (octal)
    optional: true         # Don't fail if ConfigMap missing
```

**Volume types:**
- `configMap` - ConfigMap as files
- `secret` - Secret as files (more secure than env vars)
- `emptyDir` - Temporary storage shared between containers
- `persistentVolumeClaim` - Persistent storage
- `hostPath` - Mount host directory (dangerous, avoid)

---

## 🔄 How It All Connects

### Step-by-Step Flow:

1. **Apply ConfigMap** (`kubectl apply -f configmap.yaml`)
   - Creates ConfigMap `app-config` with 4 keys
   - Stored in etcd (Kubernetes database)

2. **Apply Secret** (`kubectl apply -f secret.yaml`)
   - Creates Secret `db-credentials` with 2 base64-encoded keys
   - Stored in etcd (encrypted if encryption-at-rest is enabled)

3. **Apply Deployment** (`kubectl apply -f deployment.yaml`)
   - Deployment controller creates ReplicaSet
   - ReplicaSet creates 2 pods
   - Scheduler assigns pods to nodes
   - Kubelet on each node:
     - Pulls `nginx:1.21-alpine` image
     - Reads ConfigMap and Secret from API server
     - Injects environment variables: `APP_COLOR=blue`, `DB_USER=admin`, `DB_PASSWORD=supersecret123`
     - Mounts ConfigMap as files in `/etc/config/`
     - Starts container

4. **Pod Runtime:**
   - Application code reads `APP_COLOR` env var → gets "blue"
   - Application code reads `DB_USER`, `DB_PASSWORD` → connects to database
   - Application code reads `/etc/config/config.json` → loads JSON config

5. **Update ConfigMap** (`kubectl patch configmap ...`)
   - ConfigMap updated: `app.color: "green"`
   - ❌ Existing pods **still have** `APP_COLOR=blue` (env vars don't update!)
   - ✅ `/etc/config/app.color` file **automatically updates** to "green" (after kubelet sync)

6. **Restart Deployment** (`kubectl rollout restart`)
   - Creates new ReplicaSet with new pods
   - New pods get `APP_COLOR=green`
   - Old pods terminate gradually (rolling update)
   - Zero downtime!

---

## 🎯 Common Patterns & Best Practices

### Pattern 1: Environment-Specific Configuration
```yaml
# configmap-dev.yaml
data:
  app.mode: "development"
  log.level: "debug"

# configmap-prod.yaml
data:
  app.mode: "production"
  log.level: "error"
```
**Use case:** Different config per environment, same deployment YAML

### Pattern 2: Immutable ConfigMaps
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-v2  # Version in name
immutable: true        # Can't be changed!
data:
  app.color: "blue"
```
**Benefits:**
- Faster (kubelet doesn't watch for changes)
- Safer (accidental changes prevented)
- Requires pod restart anyway for env vars

**Trade-off:** Must create new ConfigMap + update deployment to change config

### Pattern 3: Secret from File
```bash
kubectl create secret generic db-credentials \
  --from-file=username=./username.txt \
  --from-file=password=./password.txt \
  --dry-run=client -o yaml > secret.yaml
```
**Use case:** Generate Secret YAML from existing files

### Pattern 4: TLS Secret
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tls-secret
type: kubernetes.io/tls
data:
  tls.crt: LS0tLS1CRUdJTi... # Base64 certificate
  tls.key: LS0tLS1CRUdJTi... # Base64 private key
```
**Use case:** HTTPS/TLS termination in Ingress

### Pattern 5: Multi-Container with Shared Config
```yaml
spec:
  containers:
  - name: app
    envFrom:
    - configMapRef:
        name: shared-config
  - name: sidecar
    envFrom:
    - configMapRef:
        name: shared-config
  volumes:
  - name: shared-config-files
    configMap:
      name: shared-config
```
**Use case:** Multiple containers need same configuration

---

## ⚠️ Common Mistakes & Debugging

### Mistake 1: ConfigMap changes not reflected
**Symptom:** Updated ConfigMap but pods still have old values
**Cause:** Environment variables don't auto-update
**Fix:** `kubectl rollout restart deployment <name>`

### Mistake 2: Pod fails with "ConfigMap not found"
**Symptom:** `Error: couldn't find key app.color in ConfigMap scenarios/app-config`
**Cause:** ConfigMap doesn't exist or wrong name
**Fix:**
```bash
kubectl get configmap -n scenarios  # Verify it exists
kubectl describe pod <name>          # Check events for errors
```

### Mistake 3: Secret decodes incorrectly
**Symptom:** Password shows as garbage characters
**Cause:** Forgot `-n` flag in `echo -n` (includes newline)
**Fix:**
```bash
# Wrong (includes newline)
echo 'password' | base64  # cGFzc3dvcmQK

# Correct
echo -n 'password' | base64  # cGFzc3dvcmQ=
```

### Mistake 4: Selector doesn't match pod labels
**Symptom:** Deployment shows 0/2 pods ready
**Cause:** `selector.matchLabels` ≠ `template.metadata.labels`
**Fix:** Ensure labels match exactly

### Debugging Commands:
```bash
# Check if ConfigMap exists and view contents
kubectl get configmap app-config -n scenarios -o yaml

# Check if Secret exists (don't show values)
kubectl get secret db-credentials -n scenarios

# Describe pod to see events (mounting errors, etc.)
kubectl describe pod <pod-name> -n scenarios

# Check env vars in running pod
kubectl exec <pod-name> -n scenarios -- env

# Check mounted files
kubectl exec <pod-name> -n scenarios -- ls -la /etc/config
kubectl exec <pod-name> -n scenarios -- cat /etc/config/config.json

# Check deployment status
kubectl rollout status deployment configmap-demo-app -n scenarios

# View deployment events
kubectl describe deployment configmap-demo-app -n scenarios
```

---

## 📚 Further Learning

### Next Steps:
1. **Kustomize** - Manage ConfigMaps across environments without duplication
2. **Helm** - Template ConfigMaps with values files
3. **External Secrets Operator** - Sync secrets from Vault/AWS/Azure
4. **Sealed Secrets** - Encrypt secrets for safe Git storage
5. **Secret Management** - HashiCorp Vault, AWS Secrets Manager integration

### Related Scenarios:
- **05-services-networking** - How Services use labels to select pods
- **06-volumes-storage** - Persistent volumes vs ConfigMaps
- **09-rolling-updates** - Deep dive into rollout strategies

---

*This explanation file is meant to be a comprehensive reference. Don't feel overwhelmed - start with the basics (ConfigMap/Secret creation and env vars) and gradually explore advanced topics like volumes, immutability, and external secret management!*
