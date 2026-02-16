# Helm Values Explanation - Upgrade and Rollback Scenario

This guide explains how Helm manages release lifecycles, tracks revisions, and enables safe upgrades and rollbacks. You'll learn the differences between values-v1.yaml and values-v2.yaml and how Helm handles configuration changes.

---

## 🎯 What is Helm Release Lifecycle?

**Helm release lifecycle** refers to the stages a Helm release goes through from initial installation to upgrades, rollbacks, and eventual removal.

### Release Lifecycle States

```
INSTALL (Rev 1) → UPGRADE (Rev 2) → ROLLBACK to Rev 1 (Rev 3) → UNINSTALL
```

**Key Concepts:**
- **Release**: A deployed instance of a Helm chart with a unique name
- **Revision**: A numbered snapshot of release configuration (incremental, never reused)
- **History**: Complete audit trail of all revisions and their states
- **Rollback**: Restore a previous configuration by creating a NEW revision

---

## 📊 Helm Revision Tracking

### How Revisions Work

Every change to a Helm release creates a **new revision** with an incremented number.

| Action | Revision Created | Status |
|--------|------------------|--------|
| `helm install` | Revision 1 | deployed |
| `helm upgrade` | Revision 2 | deployed (Rev 1 becomes "superseded") |
| `helm rollback 1` | Revision 3 | deployed (identical to Rev 1) |
| `helm upgrade` again | Revision 4 | deployed |

**IMPORTANT:** Rollback does **NOT** delete history. It creates a new revision with the old configuration.

### Why This Matters

✅ **Full audit trail** - You always know what changed and when
✅ **Can rollback to any previous revision** - Not just the immediate previous one
✅ **Safe experimentation** - Easy to revert if changes cause issues
✅ **Compliance** - Complete history for auditing and compliance

**View history:**
```bash
helm history my-nginx --namespace helm-scenarios
```

**Output example:**
```
REVISION  STATUS      CHART        DESCRIPTION
1         superseded  nginx-15.0.0 Install complete
2         superseded  nginx-15.0.0 Upgrade complete
3         deployed    nginx-15.0.0 Rollback to 1
```

---

## 🔄 Upgrade vs Rollback

### helm upgrade

**Purpose:** Apply new configuration to an existing release

**What happens:**
1. Helm reads new values (from `-f` file or `--set` flags)
2. Merges with chart defaults
3. Renders templates with new values
4. Performs rolling update to Kubernetes resources
5. Creates new revision with status "deployed"
6. Marks previous revision as "superseded"

**Example:**
```bash
helm upgrade my-nginx bitnami/nginx \
  -f values-v2.yaml \
  --namespace helm-scenarios \
  --wait
```

**Rolling Update Behavior:**
- Deployments: Gradually replaces old pods with new ones
- Services: Updated in-place (no downtime if only labels/annotations changed)
- ConfigMaps/Secrets: Updated, pods may need restart
- StatefulSets: Updates pods one at a time in reverse ordinal order

### helm rollback

**Purpose:** Restore a previous configuration

**What happens:**
1. Helm retrieves configuration from target revision
2. Re-renders templates with old values
3. Performs rolling update to restore previous state
4. Creates NEW revision (doesn't delete current)
5. Description shows "Rollback to N"

**Example:**
```bash
helm rollback my-nginx 1 --namespace helm-scenarios --wait
```

**Key Difference from Upgrade:**
- Upgrade: Uses new values you provide
- Rollback: Uses values stored in target revision's history

---

## 📄 values-v1.yaml - Initial Stable Configuration

Let's examine the version 1 configuration field-by-field.

```yaml
# values-v1.yaml
# Version 1: conservative, stable, known-good configuration

replicaCount: 1

resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 100m
    memory: 128Mi

service:
  type: ClusterIP
  port: 80

commonLabels:
  version: v1
  environment: learning

serverBlock: |-
  server {
    listen 0.0.0.0:8080;
    location /version {
      return 200 "Version 1 - Stable Release\n";
    }
    location / {
      return 200 "Hello from v1!\n";
    }
  }
```

### replicaCount: 1

**Why 1 replica for v1:**
- **Conservative start** - Minimal resource usage for initial deployment
- **Testing/validation** - Easier to debug with single replica
- **Resource efficiency** - Good for non-critical initial release
- **Cost-effective** - Lower infrastructure cost during testing

**Trade-offs:**
- ⚠️ **No high availability** - If pod fails, brief downtime
- ⚠️ **No load distribution** - Single pod handles all traffic
- ✅ **Simple** - Easier to reason about and debug
- ✅ **Fast deployment** - Quick rollout for testing

### resources (v1)

```yaml
resources:
  requests:
    cpu: 50m      # 5% of 1 CPU core guaranteed
    memory: 64Mi  # 67 MB guaranteed
  limits:
    cpu: 100m     # 10% of 1 CPU core max
    memory: 128Mi # 134 MB max
```

**Conservative resource allocation:**
- **Small footprint** - Suitable for Kind/Minikube/small clusters
- **2x burst capacity** - Limits are 2× requests
- **Burstable QoS class** - Medium priority for scheduling/eviction

**When to use v1 resources:**
- Initial deployments
- Development/testing environments
- Low-traffic applications
- Resource-constrained clusters

### service (v1)

```yaml
service:
  type: ClusterIP
  port: 80
```

**ClusterIP for v1:**
- **Internal-only access** - Not exposed outside cluster
- **Most common type** - Default Kubernetes service type
- **Secure by default** - No external attack surface
- **DNS discoverable** - Accessible via `my-nginx.helm-scenarios.svc.cluster.local`

**Why ClusterIP for initial release:**
- ✅ Test functionality internally before exposing
- ✅ Validate in safe environment
- ✅ No external port conflicts
- ✅ Production-like for microservices

### commonLabels (v1)

```yaml
commonLabels:
  version: v1
  environment: learning
```

**version: v1** - Critical for tracking which version is deployed

**Why version labels matter:**
- 🏷️ **Identify pods** - `kubectl get pods -l version=v1`
- 📊 **Monitoring** - Track metrics per version (Prometheus queries)
- 🔀 **Blue-Green deployments** - Services can route by version label
- 📈 **Canary releases** - Gradually shift traffic between versions
- 🐛 **Debugging** - Quickly identify which version has issues

### serverBlock (v1)

```nginx
server {
  listen 0.0.0.0:8080;
  location /version {
    return 200 "Version 1 - Stable Release\n";
  }
  location / {
    return 200 "Hello from v1!\n";
  }
}
```

**Simple v1 endpoints:**

#### /version endpoint
- **Purpose:** Version identification
- **Returns:** `"Version 1 - Stable Release\n"`
- **Use case:** Health checks, monitoring dashboards, debugging

#### / endpoint
- **Purpose:** Default route
- **Returns:** `"Hello from v1!\n"`
- **Use case:** Basic functionality test

**Testing:**
```bash
kubectl port-forward -n helm-scenarios svc/my-nginx 8080:80
curl http://localhost:8080/        # "Hello from v1!"
curl http://localhost:8080/version # "Version 1 - Stable Release"
```

---

## 📄 values-v2.yaml - Upgraded Configuration

Version 2 introduces several changes: scaling, external access, more resources, and new features.

```yaml
# values-v2.yaml
# Version 2: scaled up with new features

replicaCount: 3

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi

service:
  type: NodePort
  port: 80
  nodePorts:
    http: "30080"

commonLabels:
  version: v2
  environment: learning

serverBlock: |-
  server {
    listen 0.0.0.0:8080;
    location /version {
      return 200 "Version 2 - New Features\n";
    }
    location /api/health {
      return 200 '{"status":"ok","version":"v2"}\n';
      default_type application/json;
    }
    location / {
      return 200 "Hello from v2 - upgraded!\n";
    }
  }
```

### replicaCount: 3

**Why scale to 3 replicas in v2:**
- ✅ **High availability** - Survives pod failures
- ✅ **Load distribution** - Traffic spread across 3 pods
- ✅ **Rolling updates** - Can update without downtime
- ✅ **Production-ready** - Standard HA baseline

**Impact of upgrade (1 → 3 replicas):**
```
Before (v1):
  1 pod running

During upgrade:
  1 old pod + 1 new pod created
  Once new pod ready, old pod terminated
  2 more new pods created

After (v2):
  3 new pods running (all v2)
```

### resources (v2)

```yaml
resources:
  requests:
    cpu: 100m     # 10% of 1 CPU - DOUBLED from v1
    memory: 128Mi # 134 MB - DOUBLED from v1
  limits:
    cpu: 200m     # 20% of 1 CPU - DOUBLED from v1
    memory: 256Mi # 268 MB - DOUBLED from v1
```

**Changes from v1:**
- **Requests doubled** - More guaranteed resources per pod
- **Limits doubled** - More room for bursting
- **Same 2× ratio** - Limits still 2× requests (consistent burst capacity)

**Why increase resources:**
- More features → more processing needed
- 3 replicas → need adequate resources per pod
- Production workload → need performance headroom
- Prevent throttling under load

**Total cluster resource usage:**

| Version | Pods | CPU Request | Memory Request | Total CPU | Total Memory |
|---------|------|-------------|----------------|-----------|--------------|
| v1 | 1 | 50m | 64Mi | 50m | 64Mi |
| v2 | 3 | 100m | 128Mi | 300m | 384Mi |

**Resource impact:** v2 uses 6× more resources (3 pods × 2× per pod)

### service (v2)

```yaml
service:
  type: NodePort
  port: 80
  nodePorts:
    http: "30080"
```

**Changed from ClusterIP to NodePort:**

**Why NodePort in v2:**
- ✅ **External access** - Can test from outside cluster
- ✅ **No LoadBalancer needed** - Works on Kind/Minikube
- ✅ **Fixed port** - Always accessible on port 30080
- ✅ **Demo-friendly** - Easy to show functionality

**Access after upgrade:**
```bash
# Before (v1 - ClusterIP): only internal
kubectl port-forward svc/my-nginx 8080:80 -n helm-scenarios
curl http://localhost:8080

# After (v2 - NodePort): external access
curl http://<node-ip>:30080
```

**NodePort 30080:**
- In valid range (30000-32767)
- Easy to remember (80 → 30080)
- No conflict with common ports

### commonLabels (v2)

```yaml
commonLabels:
  version: v2
  environment: learning
```

**Changed from v1 to v2:**

**Impact of version label change:**
- All resources get `version: v2` label
- Can distinguish v1 from v2 pods (during rollback)
- Monitoring dashboards can show v1 vs v2 metrics
- Selectors can target specific versions

**During rollback:**
```bash
# After rollback to v1, new pods get version: v1 label again
kubectl get pods -n helm-scenarios -L version
# Shows which pods are v1 vs v2 (during rolling update)
```

### serverBlock (v2)

```nginx
server {
  listen 0.0.0.0:8080;
  location /version {
    return 200 "Version 2 - New Features\n";
  }
  location /api/health {
    return 200 '{"status":"ok","version":"v2"}\n';
    default_type application/json;
  }
  location / {
    return 200 "Hello from v2 - upgraded!\n";
  }
}
```

**New in v2:**

#### /api/health endpoint (NEW)

```nginx
location /api/health {
  return 200 '{"status":"ok","version":"v2"}\n';
  default_type application/json;
}
```

**What's new:**
- **JSON response** - Structured health check data
- **Version in response** - Confirms which version is running
- **API-style endpoint** - Follows REST conventions
- **Content-Type header** - Properly set to `application/json`

**Use cases:**
- Machine-readable health checks
- Monitoring systems (Prometheus, Datadog)
- Load balancer health probes
- Version verification in CI/CD

**Testing:**
```bash
curl http://<node-ip>:30080/api/health
# Output: {"status":"ok","version":"v2"}

curl -I http://<node-ip>:30080/api/health
# Headers include: Content-Type: application/json
```

#### Updated responses

| Endpoint | v1 Response | v2 Response |
|----------|-------------|-------------|
| `/version` | `Version 1 - Stable Release` | `Version 2 - New Features` |
| `/` | `Hello from v1!` | `Hello from v2 - upgraded!` |
| `/api/health` | *(doesn't exist)* | `{"status":"ok","version":"v2"}` |

---

## 🔍 Configuration Comparison: v1 vs v2

### Side-by-Side Comparison

| Configuration | v1 (Stable) | v2 (Upgraded) | Reason for Change |
|---------------|-------------|---------------|-------------------|
| **Replicas** | 1 | 3 | High availability, load distribution |
| **CPU Request** | 50m | 100m | More processing power per pod |
| **CPU Limit** | 100m | 200m | Handle higher load |
| **Memory Request** | 64Mi | 128Mi | More memory for features |
| **Memory Limit** | 128Mi | 256Mi | Prevent OOM under load |
| **Service Type** | ClusterIP | NodePort | External access for testing |
| **NodePort** | N/A | 30080 | Fixed external port |
| **Version Label** | v1 | v2 | Track version in monitoring |
| **Root Response** | `Hello from v1!` | `Hello from v2 - upgraded!` | Confirm upgrade |
| **Version Endpoint** | `Version 1 - Stable Release` | `Version 2 - New Features` | Version identification |
| **/api/health** | *(absent)* | `{"status":"ok","version":"v2"}` | Structured health check |

### Upgrade Strategy Demonstrated

This v1 → v2 → rollback pattern teaches:

1. **Conservative start (v1)** - Small, simple, internal-only
2. **Gradual expansion (v2)** - Scale up, add features, expose externally
3. **Safety net (rollback)** - Easy revert if v2 has issues

**Real-world parallel:**
```
v1 = Beta release (internal testing)
v2 = General Availability (public release)
Rollback = Found critical bug, revert to stable v1
```

---

## 🎓 Upgrade and Rollback Mechanics

### What Happens During Helm Upgrade

**Step-by-step process:**

1. **Helm reads new values**
   ```bash
   helm upgrade my-nginx bitnami/nginx -f values-v2.yaml
   ```

2. **Merges values** (precedence: v2 file > chart defaults)

3. **Renders templates** with new values
   ```yaml
   # Deployment gets updated:
   replicas: 3         # was 1
   labels:
     version: v2       # was v1
   resources:
     requests:
       cpu: 100m       # was 50m
   ```

4. **Applies to Kubernetes** (rolling update)
   ```
   Kubernetes ReplicaSet Controller:
   - Creates ReplicaSet with new pod template (v2)
   - Gradually scales up new RS (0 → 1 → 2 → 3)
   - Gradually scales down old RS (1 → 0)
   - Deletes old ReplicaSet when scale=0
   ```

5. **Creates revision 2**
   ```bash
   helm history my-nginx
   # REVISION  STATUS      DESCRIPTION
   # 1         superseded  Install complete
   # 2         deployed    Upgrade complete
   ```

### What Happens During Helm Rollback

**Step-by-step process:**

1. **Helm retrieves config from revision 1**
   ```bash
   helm rollback my-nginx 1
   ```

2. **Re-renders templates** with v1 values (stored in history)

3. **Applies to Kubernetes** (rolling update in reverse)
   ```
   Kubernetes ReplicaSet Controller:
   - Creates ReplicaSet with old pod template (v1)
   - Scales up new RS (0 → 1)
   - Scales down v2 RS (3 → 2 → 1 → 0)
   - Deletes v2 ReplicaSet when scale=0
   ```

4. **Creates revision 3** (NOT deletes revision 2)
   ```bash
   helm history my-nginx
   # REVISION  STATUS      DESCRIPTION
   # 1         superseded  Install complete
   # 2         superseded  Upgrade complete
   # 3         deployed    Rollback to 1
   ```

5. **Service updated** - Now routes to v1 pods
   ```bash
   kubectl get pods -n helm-scenarios -L version
   # All pods have version=v1 label
   ```

### Rolling Update Visualization

**Upgrade (v1 → v2):**
```
Time →
T0:  [v1-pod]
T1:  [v1-pod] [v2-pod-1] ← new pod starting
T2:  [v2-pod-1] [v2-pod-2] ← v1 terminated, v2-2 starting
T3:  [v2-pod-1] [v2-pod-2] [v2-pod-3] ← all v2 pods running
```

**Rollback (v2 → v1):**
```
Time →
T0:  [v2-pod-1] [v2-pod-2] [v2-pod-3]
T1:  [v2-pod-1] [v2-pod-2] [v1-pod] ← new v1 pod starting
T2:  [v1-pod] ← v2 pods terminated one by one
```

**Zero downtime:** Service always has ready pods during transition

---

## 📚 Helm History and Revisions

### Understanding helm history Output

```bash
helm history my-nginx --namespace helm-scenarios
```

**Sample output:**
```
REVISION  UPDATED                   STATUS      CHART         APP VERSION  DESCRIPTION
1         Mon Jan 15 10:00:00 2024  superseded  nginx-15.0.0  1.25.3       Install complete
2         Mon Jan 15 10:05:00 2024  superseded  nginx-15.0.0  1.25.3       Upgrade complete
3         Mon Jan 15 10:10:00 2024  deployed    nginx-15.0.0  1.25.3       Rollback to 1
```

**Column explanations:**

- **REVISION**: Sequential number (1, 2, 3...) - never reused
- **UPDATED**: Timestamp of the action
- **STATUS**:
  - `deployed` - Currently active revision
  - `superseded` - Previous revision, replaced by newer one
  - `failed` - Deployment failed (can rollback from this)
  - `pending-install/upgrade` - In progress
- **CHART**: Chart name and version used
- **APP VERSION**: Application version (nginx version in this case)
- **DESCRIPTION**: What action created this revision

### Revision Limits

**Default:** Helm keeps last 10 revisions

**Configure with:**
```bash
helm upgrade my-nginx bitnami/nginx \
  --history-max 5 \
  -f values-v2.yaml
```

**Why limit history:**
- **Storage:** Each revision is stored as Kubernetes Secret
- **Performance:** Large history = slower `helm history` commands
- **Clutter:** Old revisions rarely needed

**Best practices:**
- **Development:** 5-10 revisions
- **Production:** 20-50 revisions (compliance, auditing)

### Retrieving Revision Details

**Get user-supplied values from any revision:**
```bash
helm get values my-nginx --revision 1 --namespace helm-scenarios
```

**Get all values (including defaults) from any revision:**
```bash
helm get values my-nginx --revision 2 --all --namespace helm-scenarios
```

**Get rendered manifest from any revision:**
```bash
helm get manifest my-nginx --revision 1 --namespace helm-scenarios
```

**Compare revisions:**
```bash
# Compare values
diff <(helm get values my-nginx --revision 1) \
     <(helm get values my-nginx --revision 2)

# Compare manifests
diff <(helm get manifest my-nginx --revision 1) \
     <(helm get manifest my-nginx --revision 2)
```

---

## 🛠️ Practical Examples

### Example 1: Upgrade with --set flag

```bash
# Override just replica count, keep other v2 values
helm upgrade my-nginx bitnami/nginx \
  -f values-v2.yaml \
  --set replicaCount=5 \
  --namespace helm-scenarios
```

**Result:** v2 config but with 5 replicas instead of 3

### Example 2: Rollback to specific revision

```bash
# If you've upgraded multiple times, rollback to any revision
helm history my-nginx --namespace helm-scenarios
# Choose revision number, e.g., 3
helm rollback my-nginx 3 --namespace helm-scenarios
```

### Example 3: Dry-run upgrade

```bash
# See what would change WITHOUT applying
helm upgrade my-nginx bitnami/nginx \
  -f values-v2.yaml \
  --namespace helm-scenarios \
  --dry-run --debug
```

**Use case:** Validate changes before applying to production

### Example 4: Upgrade with wait and timeout

```bash
# Wait for resources to be ready, fail after 5 minutes
helm upgrade my-nginx bitnami/nginx \
  -f values-v2.yaml \
  --namespace helm-scenarios \
  --wait \
  --timeout 5m
```

**Best practice:** Always use `--wait` in CI/CD pipelines

### Example 5: Force rollback

```bash
# Rollback even if current release is in failed state
helm rollback my-nginx 1 \
  --namespace helm-scenarios \
  --force \
  --wait
```

**When to use:** Current release in bad state, need to force recovery

---

## 🐛 Troubleshooting

### Upgrade is stuck in "pending-upgrade"

**Symptom:**
```bash
helm list --namespace helm-scenarios
# STATUS: pending-upgrade (for a long time)
```

**Causes:**
- Upgrade command timed out
- Pods failing to start
- Insufficient cluster resources

**Solution 1: Check resource status**
```bash
kubectl get pods -n helm-scenarios
kubectl describe pod <pod-name> -n helm-scenarios
```

**Solution 2: Rollback to last good state**
```bash
helm rollback my-nginx --namespace helm-scenarios
```

### Rollback fails with "revision not found"

**Symptom:**
```bash
helm rollback my-nginx 1
# Error: revision 1 not found
```

**Cause:** History was purged or release was uninstalled

**Solution:** Can't rollback without history. Reinstall with desired config:
```bash
helm install my-nginx bitnami/nginx -f values-v1.yaml --namespace helm-scenarios
```

### Values not changing after upgrade

**Symptom:**
```bash
helm upgrade my-nginx bitnami/nginx -f values-v2.yaml
# But pods still show v1 config
```

**Check 1: Verify upgrade happened**
```bash
helm history my-nginx --namespace helm-scenarios
# Should show new revision
```

**Check 2: Check effective values**
```bash
helm get values my-nginx --all --namespace helm-scenarios
# Compare with expected values
```

**Check 3: Check pod spec**
```bash
kubectl get pod <pod-name> -n helm-scenarios -o yaml
# Verify spec matches expected config
```

**Common issue:** Cached values or wrong values file path

### Pods crashing after upgrade

**Symptom:**
```bash
kubectl get pods -n helm-scenarios
# STATUS: CrashLoopBackOff or Error
```

**Check 1: View logs**
```bash
kubectl logs <pod-name> -n helm-scenarios
```

**Check 2: Check resource limits**
```bash
kubectl describe pod <pod-name> -n helm-scenarios
# Look for: Insufficient cpu/memory, OOMKilled
```

**Solution: Rollback immediately**
```bash
helm rollback my-nginx --namespace helm-scenarios --wait
```

### Cannot access service after upgrading to NodePort

**Symptom:**
```bash
curl http://<node-ip>:30080
# Connection refused or timeout
```

**Check 1: Verify service**
```bash
kubectl get svc -n helm-scenarios
# Confirm TYPE: NodePort and PORT(S): 80:30080/TCP
```

**Check 2: Get node IP**
```bash
kubectl get nodes -o wide
# Use INTERNAL-IP or EXTERNAL-IP
```

**Check 3: Check firewall rules**
```bash
# On Kind, may need to map ports in kind-config.yaml
```

**Check 4: Port-forward as alternative**
```bash
kubectl port-forward svc/my-nginx 8080:80 -n helm-scenarios
curl http://localhost:8080
```

---

## 📖 Best Practices

### Upgrade Strategy

✅ **Always use --wait flag** in production upgrades
```bash
helm upgrade my-release chart -f values.yaml --wait --timeout 5m
```

✅ **Test upgrades in staging first**
```bash
# Staging
helm upgrade my-release chart -f staging-values.yaml

# Once validated, production
helm upgrade my-release chart -f prod-values.yaml
```

✅ **Use --dry-run for validation**
```bash
helm upgrade my-release chart -f values.yaml --dry-run --debug | less
```

✅ **Monitor during and after upgrade**
```bash
# Watch pod status during upgrade
watch kubectl get pods -n helm-scenarios

# Check application metrics after upgrade
curl http://service/health
```

✅ **Document changes in commit messages**
```bash
git commit -m "Upgrade nginx from v1 to v2: scaled to 3 replicas, added /api/health endpoint"
```

### Rollback Strategy

✅ **Know your last good revision before upgrading**
```bash
helm history my-release --namespace helm-scenarios
# Note the current deployed revision
```

✅ **Have rollback command ready**
```bash
# Before upgrade, prepare:
helm rollback my-release <last-good-revision> --namespace helm-scenarios
```

✅ **Set rollback time limits**
```bash
# If upgrade isn't healthy after 5 min, rollback
helm rollback my-release <revision> --wait --timeout 2m
```

✅ **Automated rollback in CI/CD**
```bash
#!/bin/bash
helm upgrade my-release chart -f values.yaml --wait --timeout 5m || \
  helm rollback my-release --wait
```

### Configuration Management

✅ **Version your values files in git**
```
values/
├── values-v1.yaml
├── values-v2.yaml
└── production.yaml
```

✅ **Use descriptive values file names**
```
# Good
values-stable.yaml
values-high-availability.yaml
values-production-us-east.yaml

# Bad
values1.yaml
values2.yaml
new-values.yaml
```

✅ **Keep production values encrypted**
```bash
# Use tools like SOPS, sealed-secrets, or Helm secrets plugin
helm secrets upgrade my-release chart -f secrets://values-prod.yaml
```

✅ **Comment your values files**
```yaml
# values-v2.yaml
# Version 2: Production-ready configuration with HA
# Last updated: 2024-01-15
# Changes from v1: scaled to 3 replicas, added NodePort, new /api/health endpoint

replicaCount: 3  # HA requirement: minimum 3 for production
```

### Revision Management

✅ **Set appropriate history limits**
```bash
# Production: keep more history for compliance
helm upgrade my-release chart --history-max 50

# Development: keep less history to save space
helm upgrade my-release chart --history-max 5
```

✅ **Document major revisions**
```bash
# Add annotations to track important revisions
helm upgrade my-release chart \
  -f values.yaml \
  --description "Major release: added new API endpoints, upgraded to v2.0"
```

✅ **Regularly review old revisions**
```bash
helm history my-release --namespace helm-scenarios
# Clean up old releases if needed (uninstall and reinstall)
```

---

## 🔗 Related Concepts

### Helm Diff Plugin

**Install:**
```bash
helm plugin install https://github.com/databus23/helm-diff
```

**Preview changes before upgrade:**
```bash
helm diff upgrade my-nginx bitnami/nginx -f values-v2.yaml --namespace helm-scenarios
```

**Output:** Shows exact changes that will be applied (like `git diff`)

### Blue-Green Deployments with Helm

**Concept:** Install v2 alongside v1, switch traffic, uninstall v1

```bash
# Install v1 (blue)
helm install nginx-blue bitnami/nginx -f values-v1.yaml

# Install v2 (green)
helm install nginx-green bitnami/nginx -f values-v2.yaml

# Switch service selector to green
kubectl patch service nginx -p '{"spec":{"selector":{"version":"v2"}}}'

# Once validated, uninstall blue
helm uninstall nginx-blue
```

### Canary Deployments

**Concept:** Gradually shift traffic from v1 to v2

**Using Istio:**
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
spec:
  http:
  - route:
    - destination:
        host: nginx-v1
      weight: 90  # 90% traffic to v1
    - destination:
        host: nginx-v2
      weight: 10  # 10% traffic to v2 (canary)
```

---

## 🎯 Key Takeaways

1. **Revisions are immutable** - Each change creates a new revision
2. **Rollback creates new revision** - History is never deleted
3. **Full audit trail** - Always know what changed and when
4. **Zero-downtime updates** - Rolling updates ensure availability
5. **Safety net** - Easy to revert to any previous configuration
6. **Test before production** - Use staging environments and --dry-run
7. **Monitor and validate** - Always verify upgrade success
8. **Keep values in version control** - Track configuration changes over time

---

## 🔗 Further Reading

- **Helm Upgrade Documentation**: https://helm.sh/docs/helm/helm_upgrade/
- **Helm Rollback Documentation**: https://helm.sh/docs/helm/helm_rollback/
- **Helm History Documentation**: https://helm.sh/docs/helm/helm_history/
- **Kubernetes Rolling Updates**: https://kubernetes.io/docs/tutorials/kubernetes-basics/update/update-intro/
- **Blue-Green Deployments**: https://martinfowler.com/bliki/BlueGreenDeployment.html

---

*This guide provides a comprehensive understanding of Helm release lifecycle management. Mastering upgrades and rollbacks is critical for safe, reliable application deployments in Kubernetes!*
