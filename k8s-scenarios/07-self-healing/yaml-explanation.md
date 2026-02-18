# YAML Configuration Explanation - Self-Healing Scenario

This guide explains each part of the YAML files used in this scenario, helping you understand how they enable Kubernetes self-healing capabilities.

---

## Step 2: Deployment Configuration (deployment.yaml)

### apiVersion and Kind
```yaml
apiVersion: apps/v1
kind: Deployment
```
**What it means:** Declares this is a Deployment resource from the apps/v1 API group.

**Why Deployment?** Deployments manage ReplicaSets, which ensure the desired number of pod replicas are always running - the foundation of self-healing.

**Other options:** StatefulSet (for stateful apps), DaemonSet (one pod per node), or Job (run-to-completion tasks).

---

### Metadata Section
```yaml
metadata:
  name: selfheal-demo-app
  namespace: scenarios
  labels:
    app: selfheal-demo
    scenario: "08"
```
**What it means:**
- `name`: Unique identifier for this deployment
- `namespace`: Logical grouping to isolate resources
- `labels`: Key-value pairs for organizing and selecting resources

**Why labels matter:** Labels like `app: selfheal-demo` are used by Services and selectors to identify which pods belong to this deployment.

**Best practices:** Use consistent naming conventions and meaningful labels for easy management.

---

### Spec - Replicas
```yaml
spec:
  replicas: 3
```
**What it means:** The **desired state** - Kubernetes will maintain exactly 3 pod replicas at all times.

**How self-healing works:** When you delete a pod (Steps 4 & 7), the ReplicaSet controller detects `current state (2 pods) ≠ desired state (3 pods)` and immediately creates a replacement.

**You can change:** Set replicas to 1, 5, 10, or any number. Kubernetes will scale up or down to match.

---

### Spec - Selector
```yaml
  selector:
    matchLabels:
      app: selfheal-demo
```
**What it means:** Tells the Deployment which pods it manages. Only pods with label `app: selfheal-demo` are controlled by this Deployment.

**Why it's critical:** Without a matching selector, the Deployment won't know which pods to monitor or recreate.

**Must match:** The `matchLabels` must match the labels in the pod template below.

---

### Spec - Template (Pod Definition)
```yaml
  template:
    metadata:
      labels:
        app: selfheal-demo
```
**What it means:** This is the blueprint for creating new pods. When Kubernetes recreates a deleted pod, it uses this template.

**Labels here:** Must match the `selector.matchLabels` above so the Deployment can manage these pods.

---

### Container Specification
```yaml
    spec:
      containers:
      - name: nginx
        image: nginx:1.21-alpine
        ports:
        - containerPort: 80
```
**What it means:**
- `name`: Container name (can have multiple containers per pod)
- `image`: Docker image to run (nginx web server, alpine variant for small size)
- `containerPort`: Port the container listens on

**Image options:** You can use any container image from Docker Hub or private registries (e.g., `nginx:latest`, `redis:6.2`, `myapp:v1.0`).

---

### Resource Requests
```yaml
        resources:
          requests:
            cpu: 100m
            memory: 64Mi
```
**What it means:**
- `cpu: 100m`: Requests 100 millicores (0.1 CPU core) - minimum CPU needed
- `memory: 64Mi`: Requests 64 Mebibytes of RAM - minimum memory needed

**Why it matters:** Helps Kubernetes scheduler place pods on nodes with available resources. Also used for horizontal pod autoscaling.

**Best practices:** Set requests to typical usage, set limits (not shown here) to prevent resource hogging.

---

## Step 2: Service Configuration (service.yaml)

### Service Basics
```yaml
apiVersion: v1
kind: Service
metadata:
  name: selfheal-demo-service
  namespace: scenarios
```
**What it means:** Declares a Service resource that provides stable networking for pods.

**Why Services matter:** Even when pods are deleted and recreated with new IPs (Steps 4-8), the Service maintains a stable endpoint (ClusterIP) for accessing them.

---

### Service Selector
```yaml
spec:
  selector:
    app: selfheal-demo
```
**What it means:** The Service routes traffic to all pods with label `app: selfheal-demo`.

**Self-healing connection:** When pods are recreated, the Service automatically discovers the new pod IPs and includes them in the load balancing pool. No configuration changes needed!

---

### Service Ports
```yaml
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
```
**What it means:**
- `protocol`: TCP (default, can be UDP or SCTP)
- `port: 80`: Port the Service listens on (ClusterIP:80)
- `targetPort: 80`: Port on the pod containers (maps to containerPort in Deployment)

**How it works:** Traffic to `selfheal-demo-service:80` → routed to → pod's port 80 (nginx).

**Service types:**
- **ClusterIP** (default, shown here): Internal cluster access only
- **NodePort**: Exposes service on each node's IP at a static port
- **LoadBalancer**: Creates external load balancer (cloud providers)
- **ExternalName**: Maps to an external DNS name

---

## Steps 3-8: Self-Healing in Action

### What Happens When You Delete a Pod (Steps 4-5):
1. **Delete command executed** → Pod enters `Terminating` state
2. **ReplicaSet detects mismatch:** Current: 2 pods, Desired: 3 pods
3. **Controller creates new pod** → New pod enters `Pending` state
4. **Scheduler assigns node** → Pod enters `ContainerCreating`
5. **Container starts** → Pod enters `Running` state
6. **Service updates endpoints** → New pod IP added to load balancing

**Time:** Usually 10-30 seconds, depends on image pull and container startup time.

---

### What Happens When You Delete All Pods (Steps 7-8):
Same process, but for all 3 pods simultaneously! Kubernetes parallelizes pod creation for faster recovery.

---

## Key YAML Concepts Summary

| YAML Field | Purpose | Self-Healing Role |
|------------|---------|-------------------|
| `replicas: 3` | Desired state declaration | Defines how many pods should exist |
| `selector.matchLabels` | Pod identification | Links Deployment to pods it manages |
| `template` | Pod blueprint | Used to create replacement pods |
| `resources.requests` | Resource requirements | Ensures new pods can be scheduled |
| Service `selector` | Traffic routing | Auto-discovers new pod IPs |

---

## Try Experimenting!

### Modify replicas:
```bash
kubectl scale deployment selfheal-demo-app --replicas=5 -n scenarios
# Watch 2 more pods get created!
```

### Change the image:
```bash
kubectl set image deployment/selfheal-demo-app nginx=nginx:1.22-alpine -n scenarios
# Watch rolling update replace all pods!
```

### View the YAML in the cluster:
```bash
kubectl get deployment selfheal-demo-app -n scenarios -o yaml
# See the full deployed configuration
```

---

## Real-World Best Practices

1. **Always set resource requests** - Helps scheduler make good placement decisions
2. **Use meaningful labels** - Makes resource management easier (`app`, `version`, `component`)
3. **Set appropriate replica counts** - Balance between availability and resource usage
4. **Add health checks** (not shown) - `livenessProbe` and `readinessProbe` enhance self-healing
5. **Use namespaces** - Isolate environments (dev, staging, prod)
6. **Version your images** - Use specific tags like `nginx:1.21-alpine`, not `nginx:latest`

---

## Common Issues and Solutions

**Issue:** Pod not recreating after deletion
- **Check:** `kubectl get replicaset -n scenarios` - Is ReplicaSet healthy?
- **Check:** `kubectl describe deployment selfheal-demo-app -n scenarios` - Any errors?

**Issue:** New pod stuck in Pending
- **Check:** `kubectl describe pod <pod-name> -n scenarios` - Resource constraints? Node selector issues?

**Issue:** Service not routing to new pods
- **Check:** `kubectl get endpoints selfheal-demo-service -n scenarios` - Are pod IPs listed?
- **Check:** Labels match between Deployment template and Service selector

---

## Additional Resources

- **Kubernetes Deployments:** https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- **ReplicaSets:** https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/
- **Services:** https://kubernetes.io/docs/concepts/services-networking/service/
- **Labels and Selectors:** https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
