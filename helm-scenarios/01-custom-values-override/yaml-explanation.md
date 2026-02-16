# Helm Values Explanation - Custom Values Override Scenario

This guide explains how Helm values work, including the precedence rules and how to override default chart values.

---

## 🎯 What are Helm Values?

**Helm values** are configuration parameters that customize how a Helm chart deploys your application. Instead of hardcoding configuration in YAML files, charts use templates with placeholders that get replaced by values at install/upgrade time.

### Why Values Matter:
- **Reusability**: Same chart can be deployed with different configurations
- **Flexibility**: Change behavior without modifying chart source code
- **Environment-specific**: Different values for dev, staging, production
- **Version control**: Values files can be tracked separately from charts

---

## 📊 Helm Values Precedence (Lowest to Highest)

Understanding precedence is **critical** for troubleshooting "why isn't my value being used?"

```
1. Chart's default values.yaml (built into chart)
   ↓
2. Parent chart's values (if this is a subchart)
   ↓
3. User values file: -f custom-values.yaml or --values
   ↓
4. Individual --set flags
   ↓
5. --set-string flags (highest priority)
```

**Rule**: Higher priority **overwrites** lower priority

**Example:**
```bash
# Chart default: replicaCount: 1
# custom-values.yaml: replicaCount: 3
# Command: helm install -f custom-values.yaml --set replicaCount=5

# Result: replicaCount = 5 (--set wins!)
```

---

## 📄 custom-values.yaml - Field-by-Field Breakdown

### replicaCount: 3

```yaml
replicaCount: 3
```

**What it is:** Number of pod replicas to run

**Default (Bitnami nginx chart):** `replicaCount: 1`

**Our override:** `3` replicas

**Why 3?**
- **High Availability**: If one pod fails, others handle traffic
- **Load Distribution**: 3 pods share incoming requests
- **Zero Downtime Updates**: Can update pods one at a time

**How it works:**
- This value gets injected into the Deployment template
- Template uses: `replicas: {{ .Values.replicaCount }}`
- Kubernetes creates 3 identical pods

**When to use different values:**
- **1 replica**: Development/testing, minimal resources
- **2-3 replicas**: Production baseline
- **5+ replicas**: High-traffic production services

**Check current value:**
```bash
helm get values my-nginx -n helm-scenarios
```

---

### resources

```yaml
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 150m
    memory: 128Mi
```

**What it is:** CPU and memory guarantees and limits for each pod

**Requests vs Limits:**

| Type | Purpose | What Happens |
|------|---------|--------------|
| **requests** | Minimum guaranteed resources | Scheduler only places pod on nodes with this much available |
| **limits** | Maximum allowed resources | Container throttled (CPU) or killed (memory) if exceeded |

**Our values explained:**

**CPU:**
- `requests.cpu: 50m` = 50 millicores = 0.05 CPU cores guaranteed
- `limits.cpu: 150m` = 150 millicores = 0.15 CPU cores max
- **Allows 3x burst**: Pod can use up to 3× its requested CPU during spikes

**Memory:**
- `requests.memory: 64Mi` = 64 Mebibytes = 67 MB guaranteed
- `limits.memory: 128Mi` = 128 Mebibytes = 134 MB max
- **Allows 2x burst**: Pod can use up to 2× its requested memory

**Why these specific values?**
- ✅ **Small enough for Kind cluster**: Won't exhaust laptop resources
- ✅ **Suitable for nginx**: Static web server needs minimal resources
- ✅ **Room to burst**: Can handle traffic spikes without throttling
- ✅ **Prevents resource starvation**: Limits protect other pods

**CPU Units:**
- `1000m` = `1` = 1 full CPU core
- `100m` = 0.1 cores (10% of one core)
- `50m` = 0.05 cores (5% of one core)

**Memory Units:**
- `Mi` = Mebibyte (1024² bytes = 1,048,576 bytes)
- `Gi` = Gibibyte (1024³ bytes)
- **Prefer `Mi`/`Gi`** over `M`/`G` for consistency

**Quality of Service (QoS) Classes:**

Our configuration creates **Burstable** QoS:
- `requests` < `limits`
- Medium priority during resource pressure
- Won't be killed unless memory limit exceeded

**Alternatives:**
- **Guaranteed** (highest priority): `requests` = `limits`
- **BestEffort** (lowest priority): No requests/limits set

**Best Practices:**
```yaml
# Good: Allows bursting
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 200m      # 2x requests
    memory: 256Mi  # 2x requests

# Bad: No burst capacity (QoS Guaranteed but inflexible)
resources:
  requests:
    cpu: 200m
  limits:
    cpu: 200m      # Same as requests

# Bad: Missing requests (HPA won't work, BestEffort QoS)
resources:
  limits:
    cpu: 200m
```

---

### service

```yaml
service:
  type: NodePort
  port: 80
  nodePorts:
    http: "30080"
```

**What it is:** Configuration for the Kubernetes Service that exposes nginx

#### service.type: NodePort

**Default (Bitnami nginx):** `ClusterIP`

**Our override:** `NodePort`

**Service Types Comparison:**

| Type | Access | Use Case | Example |
|------|--------|----------|---------|
| **ClusterIP** | Internal only | Microservices, databases | `http://my-service.namespace.svc` |
| **NodePort** | External via Node IP:Port | Development, testing | `http://192.168.1.100:30080` |
| **LoadBalancer** | External via cloud LB | Production (AWS, GCP, Azure) | `http://a1b2c3...elb.amazonaws.com` |
| **ExternalName** | DNS alias | External service abstraction | `mysql.external.com` |

**Why NodePort for this scenario?**
- ✅ **Easy access**: Can test from browser outside cluster
- ✅ **No cloud needed**: Works on Kind/Minikube locally
- ✅ **Learning**: See how NodePort exposes services
- ⚠️ **Not production**: Use LoadBalancer or Ingress in production

**Port Range:** NodePort must be in range `30000-32767`

#### service.port: 80

**What it is:** Port the Service listens on (inside cluster)

**How it works:**
```
Inside cluster: http://my-nginx:80
Outside cluster: http://<node-ip>:30080
```

**Port vs TargetPort:**
- `port: 80` - Service port (what clients connect to)
- `targetPort: 8080` - Container port (where nginx listens)

#### nodePorts.http: "30080"

**What it is:** External port on each cluster node

**Why 30080?**
- Easy to remember (80 → 30080)
- No conflict with common ports
- In valid NodePort range (30000-32767)

**Accessing the service:**
```bash
# Get node IP
kubectl get nodes -o wide

# Access via NodePort
curl http://<node-ip>:30080
```

**Production alternative:**
```yaml
service:
  type: LoadBalancer  # Cloud provider creates external LB
  port: 80
```

---

### commonLabels

```yaml
commonLabels:
  environment: learning
  scenario: custom-values-override
```

**What it is:** Key-value pairs added to ALL resources created by this chart

**Applied to:**
- Deployment
- Service
- Pods
- ConfigMaps
- Secrets
- Any other resources in the chart

**Why labels?**
- 🏷️ **Organization**: Group related resources
- 🔍 **Filtering**: `kubectl get all -l environment=learning`
- 📊 **Monitoring**: Prometheus/Grafana queries by label
- 🎯 **Policies**: NetworkPolicies, PodSecurityPolicies target labels

**Example usage:**
```bash
# Get all resources for this scenario
kubectl get all -n helm-scenarios -l scenario=custom-values-override

# Get all learning environment resources
kubectl get all -n helm-scenarios -l environment=learning

# Filter pods by multiple labels
kubectl get pods -l environment=learning,scenario=custom-values-override
```

**Best practices:**
```yaml
commonLabels:
  app: nginx                          # Application name
  version: "1.21"                     # App version
  environment: production             # Environment
  team: platform                      # Owning team
  cost-center: engineering            # Billing
  app.kubernetes.io/name: nginx       # Recommended label
  app.kubernetes.io/instance: my-app  # Release name
```

**Recommended Kubernetes labels:**
- `app.kubernetes.io/name` - Application name
- `app.kubernetes.io/instance` - Unique instance name
- `app.kubernetes.io/version` - App version
- `app.kubernetes.io/component` - Component role (frontend, backend)
- `app.kubernetes.io/part-of` - Parent application name
- `app.kubernetes.io/managed-by` - Tool managing the resource (Helm)

---

### serverBlock

```yaml
serverBlock: |-
  server {
    listen 0.0.0.0:8080;
    location /healthz {
      return 200 "healthy\n";
    }
    location / {
      return 200 "Hello from Helm custom values!\n";
    }
  }
```

**What it is:** Custom nginx configuration block

**Syntax: `|-`**
- `|` = Literal block scalar (preserves line breaks)
- `-` = Strip trailing newlines
- This is YAML multi-line string syntax

**nginx server block breakdown:**

#### listen 0.0.0.0:8080

**What it does:** nginx listens on all interfaces, port 8080

**Why 8080?**
- Non-privileged port (ports < 1024 require root)
- Safe for containers running as non-root user
- Common convention for HTTP alt-port

#### location /healthz

```nginx
location /healthz {
  return 200 "healthy\n";
}
```

**What it does:** Health check endpoint

**Purpose:**
- Kubernetes **readiness probes** check this endpoint
- Returns HTTP 200 if nginx is healthy
- Load balancer only sends traffic to healthy pods

**Testing:**
```bash
curl http://<service-ip>:8080/healthz
# Output: healthy
```

**Production health checks:**
```yaml
# In Deployment spec:
readinessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
```

#### location /

```nginx
location / {
  return 200 "Hello from Helm custom values!\n";
}
```

**What it does:** Catch-all route for all other URLs

**Purpose:**
- Simple response to prove custom values are working
- In production, this would serve actual web content

**Testing:**
```bash
curl http://<service-ip>:8080/
# Output: Hello from Helm custom values!
```

**Production alternative:**
```nginx
location / {
  root /usr/share/nginx/html;
  index index.html;
}
```

---

## 🔄 How Helm Templating Works

When you install/upgrade with custom values:

1. **Helm reads values in order:**
   ```
   chart/values.yaml (defaults)
   → -f custom-values.yaml (your file)
   → --set replicaCount=5 (CLI flag)
   ```

2. **Merges all values into single object:**
   ```yaml
   replicaCount: 5           # from --set (highest priority)
   resources:                # from custom-values.yaml
     requests:
       cpu: 50m
   service:                  # from custom-values.yaml
     type: NodePort
   image:                    # from chart defaults (not overridden)
     repository: bitnami/nginx
   ```

3. **Renders templates with merged values:**
   ```yaml
   # templates/deployment.yaml
   apiVersion: apps/v1
   kind: Deployment
   spec:
     replicas: {{ .Values.replicaCount }}  # ← Replaced with 5
     template:
       spec:
         containers:
         - resources: {{ .Values.resources }}  # ← Replaced with custom-values.yaml
   ```

4. **Applies rendered manifests to cluster:**
   ```bash
   kubectl apply -f <rendered-deployment.yaml>
   ```

---

## 🎓 Practical Examples

### Example 1: Override just one value

```bash
# Install with mostly defaults, but 2 replicas
helm install my-nginx bitnami/nginx \
  --set replicaCount=2 \
  -n helm-scenarios
```

### Example 2: Multiple values files

```bash
# Layer values: base → environment-specific
helm upgrade my-nginx bitnami/nginx \
  -f base-values.yaml \
  -f prod-values.yaml \
  -n helm-scenarios

# prod-values.yaml wins if both files define the same key
```

### Example 3: Override nested values

```bash
# Override deeply nested value
helm upgrade my-nginx bitnami/nginx \
  --set resources.requests.cpu=100m \
  --set service.type=LoadBalancer \
  -n helm-scenarios
```

### Example 4: See rendered output without installing

```bash
# Dry-run to see final YAML
helm install my-nginx bitnami/nginx \
  -f custom-values.yaml \
  --dry-run --debug \
  -n helm-scenarios
```

---

## 🐛 Troubleshooting Values

### My value isn't being applied!

**Check precedence:**
```bash
# See ALL merged values (effective config)
helm get values my-nginx -n helm-scenarios --all

# See only user-supplied values
helm get values my-nginx -n helm-scenarios
```

**Common issues:**
1. ❌ Wrong key name (typo in custom-values.yaml)
2. ❌ Lower precedence (--set flag overriding your file)
3. ❌ Chart doesn't support that value (check chart README)
4. ❌ Wrong YAML indentation (nested wrong)

### How do I know what values are available?

```bash
# Show chart's default values.yaml
helm show values bitnami/nginx

# Download chart to inspect templates
helm pull bitnami/nginx --untar
cd nginx/
cat values.yaml        # Default values
cat templates/*.yaml   # See how values are used
```

### Validate values file syntax

```bash
# Check YAML syntax
yamllint custom-values.yaml

# Lint chart with your values
helm lint bitnami/nginx -f custom-values.yaml
```

---

## 📚 Key Takeaways

1. **Values enable reusability** - Same chart, many configurations
2. **Precedence matters** - `--set` > `-f` > chart defaults
3. **Inspect before applying** - Use `--dry-run --debug`
4. **Check effective values** - Use `helm get values --all`
5. **Use values files for complex config** - Easier than many `--set` flags
6. **Label everything** - `commonLabels` helps organize resources
7. **Start small, override selectively** - Only override what you need to change

---

## 🔗 Further Reading

- **Helm Values Documentation**: https://helm.sh/docs/chart_template_guide/values_files/
- **Bitnami nginx Chart**: https://github.com/bitnami/charts/tree/main/bitnami/nginx
- **Kubernetes Resource Management**: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- **Service Types**: https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types

---

*This guide provides a deep understanding of Helm values and the custom-values.yaml file. Understanding values precedence and how to override chart defaults is fundamental to using Helm effectively!*
