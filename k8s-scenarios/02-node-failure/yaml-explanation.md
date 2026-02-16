# YAML Files Explanation - Node Failure Scenario

This scenario uses two Kubernetes configuration files to demonstrate node failure handling and pod rescheduling.

---

## Deployment Configuration (deployment.yaml)

### apiVersion: apps/v1
**What it is:** Specifies which version of the Kubernetes API to use for this resource.

**Why apps/v1:** Deployments belong to the "apps" API group. The "v1" indicates this is a stable, production-ready version.

**Options:**
- `apps/v1` - Stable API for Deployments, StatefulSets, DaemonSets
- `apps/v1beta1` or `apps/v1beta2` - Older beta versions (deprecated)

---

## kind: Deployment
**What it is:** Defines the type of Kubernetes resource being created.

**Why Deployment:** Deployments manage the desired state of ReplicaSets and Pods. They're ideal for stateless applications that need:
- Multiple replicas for high availability
- Rolling updates and rollbacks
- Self-healing (automatic pod replacement)

**Options:**
- `Deployment` - For stateless apps with replica management
- `StatefulSet` - For stateful apps requiring stable network IDs and persistent storage
- `DaemonSet` - For running one pod per node (logging, monitoring agents)
- `Job` - For one-time tasks
- `CronJob` - For scheduled tasks

---

## metadata
**What it is:** Information that uniquely identifies and describes the Deployment.

### metadata.name: node-failure-demo
**Purpose:** The unique name for this Deployment within its namespace.

**Naming rules:**
- Lowercase alphanumeric characters, hyphens, or dots
- Must start and end with alphanumeric character
- Max 253 characters

### metadata.namespace: scenarios
**Purpose:** Logical grouping and isolation of resources.

**Why use namespaces:**
- Organize resources by project, team, or environment
- Enable resource quotas and access controls per namespace
- Avoid naming conflicts

**Default namespaces:**
- `default` - Default namespace if none specified
- `kube-system` - Kubernetes system components
- `kube-public` - Publicly accessible resources
- `kube-node-lease` - Node heartbeat data

### metadata.labels
**Purpose:** Key-value pairs for organizing and selecting resources.

**Common uses:**
- Selecting pods with Services (via selectors)
- Grouping resources for bulk operations
- Organizing resources in dashboards
- Filtering with `kubectl get` commands

**Example labels:**
- `app: node-failure-demo` - Application identifier
- `scenario: "02"` - Scenario number for organization
- `environment: production` - Environment tag
- `tier: frontend` - Application tier

---

## spec (Deployment Spec)
**What it is:** Defines the desired state of the Deployment.

### spec.replicas: 3
**Purpose:** Number of pod copies to maintain at all times.

**Why 3 replicas:**
- **High Availability:** If one pod fails, others continue serving traffic
- **Load Distribution:** Traffic is spread across multiple pods
- **Node Failure Resilience:** Demonstrates rescheduling when nodes fail

**Choosing replica count:**
- **1 replica:** Development/testing, no HA
- **2 replicas:** Basic redundancy, but quorum issues
- **3+ replicas:** Production HA, recommended for critical services
- **Odd numbers:** Preferred for quorum-based systems (3, 5, 7)

---

## spec.selector
**Purpose:** Determines which pods belong to this Deployment.

### spec.selector.matchLabels
**How it works:** The Deployment manages all pods whose labels match ALL the key-value pairs specified here.

**Example:**
```yaml
selector:
  matchLabels:
    app: node-failure-demo
```

This selector matches pods with the label `app: node-failure-demo`.

**IMPORTANT:** The selector must match the labels in `spec.template.metadata.labels`, otherwise the Deployment won't manage the pods.

**Advanced options:**
- `matchExpressions`: More complex selection logic with operators (In, NotIn, Exists, DoesNotExist)

---

## spec.template
**Purpose:** Defines the pod template used to create new pods.

**Structure:** Contains its own `metadata` and `spec` sections that describe the pods.

### spec.template.metadata.labels
**Purpose:** Labels applied to pods created from this template.

**MUST match:** These labels must match the Deployment's `spec.selector.matchLabels`.

**Why:** This is how the Deployment identifies and manages its pods.

---

## spec.template.spec (Pod Spec)
**Purpose:** Defines what runs inside each pod.

### spec.template.spec.containers
**What it is:** List of containers to run in each pod.

**Single vs Multiple containers:**
- **Single container:** Most common, one app per pod
- **Multiple containers:** Sidecar pattern (logging, proxies, init tasks)

### Container Definition

#### name: nginx
**Purpose:** Unique name for the container within the pod.

**Uses:**
- Referencing in logs: `kubectl logs pod-name -c nginx`
- Distinguishing containers in multi-container pods

#### image: nginx:1.21-alpine
**Purpose:** Specifies which container image to run.

**Format:** `[registry/][repository/]image[:tag|@digest]`

**Breakdown:**
- `nginx` - Image name (official NGINX web server)
- `1.21` - Version number
- `alpine` - Variant (Alpine Linux base, smaller image)

**Image tag best practices:**
- ✅ **Specific version:** `nginx:1.21-alpine` (reproducible, recommended)
- ⚠️ **Major version:** `nginx:1.21` (allows patch updates)
- ❌ **Latest tag:** `nginx:latest` (non-deterministic, avoid in production)

**Image sources:**
- Docker Hub (default): `nginx:1.21`
- Google Container Registry: `gcr.io/project/image:tag`
- Amazon ECR: `123456.dkr.ecr.region.amazonaws.com/image:tag`
- Private registry: `registry.company.com/image:tag`

#### ports
**Purpose:** Documents which ports the container exposes.

**IMPORTANT:** This is **declarative documentation**, not a security mechanism. Containers can still bind to any port.

```yaml
ports:
- containerPort: 80
```

**containerPort: 80** - The port NGINX listens on inside the container.

**When to specify:**
- Makes ports discoverable by Services
- Required for some network plugins
- Self-documenting configuration

#### resources
**Purpose:** Defines CPU and memory limits for the container.

**Two types:**
1. **requests** - Minimum resources guaranteed to the container
2. **limits** - Maximum resources the container can use

```yaml
resources:
  requests:
    cpu: 100m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 128Mi
```

**CPU Units:**
- `100m` = 0.1 CPU core (100 millicores)
- `1` = 1 full CPU core
- `2000m` = 2 CPU cores

**Memory Units:**
- `64Mi` = 64 Mebibytes (67,108,864 bytes)
- `128Mi` = 128 Mebibytes
- `1Gi` = 1 Gibibyte (1,073,741,824 bytes)

**Why set resources:**
- **Requests:** Kubernetes uses this for pod scheduling decisions
- **Limits:** Prevents one pod from consuming all node resources
- **Quality of Service (QoS):**
  - **Guaranteed:** requests = limits (highest priority)
  - **Burstable:** requests < limits (medium priority)
  - **BestEffort:** no requests/limits (lowest priority, evicted first)

**Setting appropriate values:**
- Monitor actual usage: `kubectl top pods`
- Start conservative, adjust based on metrics
- Set limits 1.5-2x higher than requests for bursting

---

## Service Configuration (service.yaml)

### apiVersion: v1
**What it is:** Core API version for basic Kubernetes resources.

**Why v1:** Services are part of the core API, which uses `v1` (not grouped like `apps/v1`).

---

## kind: Service
**Purpose:** Provides stable network endpoint for accessing pods.

**Why Services are needed:**
- Pods have dynamic, ephemeral IP addresses
- Pods are created/destroyed frequently (scaling, updates, failures)
- Services provide stable DNS name and IP for pod access
- Services load-balance traffic across multiple pod replicas

---

## Service metadata
```yaml
metadata:
  name: node-failure-service
  namespace: scenarios
  labels:
    app: node-failure-demo
```

**name:** DNS name for the Service (accessible as `node-failure-service.scenarios.svc.cluster.local`)

**namespace:** Must match the namespace of the pods it selects

**labels:** Organizational metadata (doesn't affect functionality, unlike selectors)

---

## spec.type: ClusterIP
**Purpose:** Determines how the Service is exposed.

**Service Types:**

| Type | Accessibility | Use Case |
|------|---------------|----------|
| **ClusterIP** (default) | Internal only (within cluster) | Internal microservices, databases |
| **NodePort** | External via `<NodeIP>:<NodePort>` | Development, testing (ports 30000-32767) |
| **LoadBalancer** | External via cloud load balancer | Production external services (AWS ELB, GCP LB) |
| **ExternalName** | DNS CNAME to external service | Abstracting external services |

**Why ClusterIP here:**
- This is a demo scenario for internal testing
- No external access needed
- Most efficient (no extra overhead)

**Accessing ClusterIP Services:**
- From within cluster: `http://node-failure-service.scenarios.svc.cluster.local`
- From same namespace: `http://node-failure-service`
- Via kubectl proxy: `kubectl port-forward svc/node-failure-service 8080:80`

---

## spec.selector
**Purpose:** Matches pods to route traffic to.

```yaml
selector:
  app: node-failure-demo
```

**How it works:**
- Service finds ALL pods with label `app: node-failure-demo`
- Load balances traffic across all matching pods
- Automatically updates when pods are added/removed
- Works across all nodes in the cluster

**IMPORTANT:** The selector must match the pod labels in the Deployment's pod template.

---

## spec.ports
**Purpose:** Defines port mapping for the Service.

```yaml
ports:
- protocol: TCP
  port: 80
  targetPort: 80
```

### protocol: TCP
**Options:**
- `TCP` - Default, most common (HTTP, HTTPS, databases)
- `UDP` - For UDP traffic (DNS, VoIP, streaming)
- `SCTP` - Stream Control Transmission Protocol (less common)

### port: 80
**What it is:** The port the Service listens on (what clients connect to).

**Example:** To access the Service, use `http://node-failure-service:80`

### targetPort: 80
**What it is:** The port on the pod containers where traffic is forwarded.

**Must match:** The `containerPort` in the Deployment (in this case, NGINX's port 80).

**Advanced usage:**
- `targetPort: 8080` - Service port 80 → Container port 8080
- `targetPort: http` - Can reference named ports from pod spec

**Named port example:**
```yaml
# In Deployment:
ports:
- name: http
  containerPort: 80

# In Service:
ports:
- port: 80
  targetPort: http  # References the named port
```

---

## How These Files Work Together

### 1. Deployment Creates Pods
- Deployment creates 3 pod replicas
- Each pod gets label `app: node-failure-demo`
- Pods are distributed across available nodes
- Each pod runs NGINX on port 80

### 2. Service Routes Traffic
- Service selector finds pods with `app: node-failure-demo`
- Service creates stable endpoint: `node-failure-service:80`
- Traffic to Service:80 → load balanced → Pod:80

### 3. Node Failure Scenario
- **Cordon node:** Prevents new pods from being scheduled
- **Drain node:** Evicts existing pods
- **Deployment responds:** Creates new pods on healthy nodes (maintaining replica count of 3)
- **Service updates:** Automatically routes traffic to new pod IPs
- **Result:** No downtime, traffic continues flowing to healthy pods

### 4. Self-Healing in Action
```
Initial State:
  Node1: pod-1, pod-2
  Node2: pod-3

After draining Node1:
  Node1: (drained)
  Node2: pod-3, pod-4, pod-5

Service continues working:
  node-failure-service → [pod-3, pod-4, pod-5]
```

---

## Best Practices & Tips

### Deployment Best Practices
✅ Always set resource requests and limits
✅ Use specific image tags, avoid `latest`
✅ Set replica count ≥ 2 for production
✅ Use readiness and liveness probes (not shown here, but recommended)
✅ Use namespaces for organization
✅ Add meaningful labels for filtering

### Service Best Practices
✅ Use ClusterIP for internal services
✅ Use LoadBalancer for external production services
✅ Match Service selector with Deployment pod labels
✅ Use named ports for clarity
✅ Document port purposes in labels/annotations

### Common Pitfalls
❌ Selector mismatch (Service can't find pods)
❌ Wrong namespace (Service in different namespace than pods)
❌ No resource limits (pods can starve other workloads)
❌ Using `latest` tag (non-reproducible deployments)
❌ Single replica (no high availability)

---

## Further Learning

**Experiment with:**
- Changing replica count: `kubectl scale deployment node-failure-demo --replicas=5`
- Rolling updates: `kubectl set image deployment/node-failure-demo nginx=nginx:1.22-alpine`
- Resource limits: Try setting very low limits and observe behavior
- Service types: Change ClusterIP to NodePort and access externally

**Related Concepts:**
- **Rolling Updates:** Zero-downtime deployments
- **Readiness Probes:** When is a pod ready to receive traffic?
- **Liveness Probes:** Is the container healthy?
- **Pod Disruption Budgets:** Control how many pods can be down during maintenance
- **Affinity/Anti-Affinity:** Control pod scheduling preferences

**Next Steps:**
- Try the HPA (Horizontal Pod Autoscaler) scenario
- Learn about StatefulSets for stateful applications
- Explore Ingress for advanced HTTP routing
