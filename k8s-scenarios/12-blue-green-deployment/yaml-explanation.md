# YAML Files Explanation - Blue-Green Deployment Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 🔵 deployment-blue.yaml (Blue Environment)

### What is Blue-Green Deployment?
Blue-Green deployment is a release strategy where you run two identical production environments called **Blue** (current version) and **Green** (new version). You switch traffic instantly between them with zero downtime.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
kind: Deployment
```
**What it is:** Standard Deployment resource
**Same as:** Regular Deployment (apps/v1 API group)

```yaml
metadata:
  name: bluegreen-blue
  namespace: scenarios
  labels:
    app: bluegreen
    version: blue
```
**What it is:** Deployment metadata
- `name: bluegreen-blue` - Deployment name (identifies the Blue environment)
- `namespace: scenarios` - Logical grouping
- `labels`:
  - `app: bluegreen` - Application identifier (shared with Green)
  - `version: blue` - **CRITICAL** - Identifies this as Blue environment

**Why two labels?**
- `app: bluegreen` - Groups all deployments for this application
- `version: blue` - Distinguishes Blue from Green

**Label strategy is key to Blue-Green:**
```
Both Blue and Green share:
- app: bluegreen

But differ on:
- version: blue  vs  version: green

Service selector uses BOTH labels to choose which environment gets traffic
```

```yaml
spec:
  replicas: 3
```
**What it is:** Number of pod replicas
**Why 3?**
- High availability (can lose 1-2 pods)
- Enough for load testing
- Demonstrates scaling

**Production:** Usually same number of replicas for Blue and Green (ensures equal capacity)

```yaml
  selector:
    matchLabels:
      app: bluegreen
      version: blue
```
**What it is:** How Deployment finds its pods
**Critical:** Must match BOTH labels in `template.metadata.labels`

**Why both labels?**
- `app: bluegreen` - Identifies application
- `version: blue` - Ensures Blue Deployment only manages Blue pods

**Important:** Green Deployment will use `version: green` here

**Pod separation:**
```
Blue Deployment manages pods with:
  app: bluegreen AND version: blue

Green Deployment manages pods with:
  app: bluegreen AND version: green

No overlap! Each Deployment manages its own set of pods.
```

```yaml
  template:
    metadata:
      labels:
        app: bluegreen
        version: blue
```
**What it is:** Labels applied to pods created by this Deployment
**Must match:** Deployment's `selector.matchLabels`

**Service selection:**
- Service selector will match `version: blue` to route traffic here
- Changing Service selector to `version: green` switches all traffic instantly

```yaml
    spec:
      containers:
      - name: app
        image: nginx:1.20-alpine
```
**What it is:** Container specification
**Image:** `nginx:1.20-alpine` - **Older version** (represents current production)

**Why 1.20?**
- Represents "current" version in production
- Will compare against Green (1.21) to demonstrate versioning

**In real scenarios:**
```yaml
# Blue (current production)
image: myapp:v1.2.3

# Green (new version)
image: myapp:v1.3.0
```

**Image versioning best practices:**
- ✅ Pin exact versions: `nginx:1.20-alpine`
- ✅ Use semantic versioning: `myapp:2.1.0`
- ❌ Never use `:latest` (unpredictable, breaks Blue-Green)

```yaml
        ports:
        - containerPort: 80
```
**What it is:** Port the container exposes
**Standard:** HTTP port 80 for Nginx

```yaml
        env:
        - name: VERSION
          value: "blue"
```
**What it is:** Environment variable passed to container
**Purpose:** Identify which environment this pod is in

**How to use:**
- Application can display version (Blue or Green)
- Logs can show which environment handled request
- Debugging and testing

**Real-world example:**
```yaml
env:
- name: VERSION
  value: "v2.1.0"
- name: ENVIRONMENT
  value: "production-green"
- name: RELEASE_DATE
  value: "2024-01-15"
```

**Testing the environment variable:**
```bash
# Inside container
echo $VERSION
# Output: blue
```

---

## 🟢 deployment-green.yaml (Green Environment)

### YAML Structure Breakdown:

**Almost identical to Blue, with key differences:**

```yaml
metadata:
  name: bluegreen-green  # Different name
  labels:
    app: bluegreen
    version: green  # Different version label
```
**What changed:**
- Deployment name: `bluegreen-green`
- Version label: `green` (vs `blue`)

```yaml
spec:
  selector:
    matchLabels:
      app: bluegreen
      version: green  # Selects Green pods
```
**What changed:** Selector matches `version: green`

```yaml
  template:
    metadata:
      labels:
        app: bluegreen
        version: green  # Pods labeled as Green
```
**What changed:** Pod labels use `version: green`

```yaml
    spec:
      containers:
      - name: app
        image: nginx:1.21-alpine  # Newer version
```
**What changed:** **NEWER** image version (1.21 vs 1.20)
**Key difference:** This represents the new code/version being deployed

```yaml
        env:
        - name: VERSION
          value: "green"  # Different env var
```
**What changed:** Environment variable says "green"

---

## 🌐 service.yaml (Traffic Router)

### What is the Service's Role in Blue-Green?
The Service acts as the **traffic switch**. By changing its selector labels, you instantly route ALL traffic from Blue to Green (or vice versa) with **zero downtime**.

### YAML Structure Breakdown:

```yaml
apiVersion: v1
kind: Service
```
**What it is:** Standard Kubernetes Service
**Type:** ClusterIP (default - internal access)

```yaml
metadata:
  name: bluegreen-service
  namespace: scenarios
```
**What it is:** Service metadata
**Name:** `bluegreen-service` - Single service for both Blue and Green

**Key concept:** One service, multiple deployments
- Service stays the same
- Only selector changes
- Applications always connect to same service name

```yaml
spec:
  selector:
    app: bluegreen
    version: blue  # Initially points to blue
```
**What it is:** **THE CRITICAL PART** - Which pods receive traffic

**How it works:**
- Service routes to pods matching **ALL** selector labels
- `app: bluegreen` AND `version: blue`
- Only Blue pods match → All traffic goes to Blue

**Switching to Green (zero-downtime):**
```yaml
# Change one line:
selector:
  app: bluegreen
  version: green  # Now points to green
```

**Instant traffic switch:**
```
Before patch:
  Service → Blue pods (nginx:1.20)

kubectl patch service bluegreen-service -p '{"spec":{"selector":{"version":"green"}}}'

After patch:
  Service → Green pods (nginx:1.21)

Downtime: 0 seconds!
```

**Why both labels in selector?**
- `app: bluegreen` - Prevents routing to unrelated apps
- `version: blue/green` - Selects specific environment

**What happens during switch:**
1. Service selector updated in etcd
2. kube-proxy on each node updates iptables rules (milliseconds)
3. New connections route to Green pods
4. Existing connections to Blue drain naturally
5. No connection failures, no downtime!

```yaml
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
```
**What it is:** Port configuration
**Standard:** Port 80 (HTTP)

**Same for both environments:**
- Blue and Green must expose same ports
- Allows seamless switching
- Applications connect to Service port 80 regardless of version

---

## 🔄 How Blue-Green Deployment Works - Complete Flow

### Initial State (Blue in Production):

```
1. Deploy Blue environment:
   kubectl apply -f deployment-blue.yaml

   Creates:
   - Deployment: bluegreen-blue
   - Pods: bluegreen-blue-xxx-1, bluegreen-blue-xxx-2, bluegreen-blue-xxx-3
   - Labels: app=bluegreen, version=blue
   - Image: nginx:1.20-alpine

2. Deploy Service (pointing to Blue):
   kubectl apply -f service.yaml

   Creates:
   - Service: bluegreen-service
   - Selector: app=bluegreen, version=blue
   - Routes to: Blue pods only

   Traffic flow:
   Client → bluegreen-service → Blue pods (nginx:1.20)
```

### Deploying Green (New Version):

```
3. Deploy Green environment (no traffic yet):
   kubectl apply -f deployment-green.yaml

   Creates:
   - Deployment: bluegreen-green
   - Pods: bluegreen-green-xxx-1, bluegreen-green-xxx-2, bluegreen-green-xxx-3
   - Labels: app=bluegreen, version=green
   - Image: nginx:1.21-alpine

   State:
   - Blue pods: Running, receiving traffic ✅
   - Green pods: Running, NO traffic ⭕
   - Service: Still pointing to Blue

   Both environments running simultaneously!
```

### Testing Green (Validation):

```
4. Test Green environment before switching:

   Option 1 - Temporary test service:
   kubectl run test -it --rm --image=curlimages/curl -- \
     curl http://bluegreen-green-xxx-1.scenarios.svc.cluster.local

   Option 2 - Port-forward:
   kubectl port-forward deployment/bluegreen-green 8080:80
   # Access http://localhost:8080

   Option 3 - Temporary selector change (limited scope):
   # Create temporary service for testing
   kubectl expose deployment bluegreen-green --name=test-green --port=80

   Validation checklist:
   ✅ Pods are Running
   ✅ Health checks pass
   ✅ Application responds correctly
   ✅ No errors in logs
   ✅ Database migrations successful (if any)
   ✅ Performance is acceptable
```

### The Switch (Instant Cutover):

```
5. Switch traffic to Green (ZERO DOWNTIME):

   kubectl patch service bluegreen-service -n scenarios -p \
     '{"spec":{"selector":{"version":"green"}}}'

   What happens:
   t=0ms:    Command executed
   t=50ms:   etcd updated
   t=100ms:  kube-proxy updates iptables on all nodes
   t=200ms:  All new connections go to Green

   Traffic flow:
   Client → bluegreen-service → Green pods (nginx:1.21) ✅

   Old connections to Blue:
   - Existing TCP connections to Blue continue
   - Drain naturally (finish their requests)
   - New connections go to Green only
```

### Post-Switch Monitoring:

```
6. Monitor Green in production:

   kubectl get pods -n scenarios -l version=green --watch
   kubectl logs -f deployment/bluegreen-green -n scenarios
   kubectl top pods -n scenarios -l version=green

   Check:
   ✅ Error rates normal
   ✅ Response times acceptable
   ✅ No increase in 5xx errors
   ✅ CPU/Memory usage as expected
   ✅ User reports OK

   Blue environment:
   - Still running (no traffic)
   - Ready for instant rollback if needed
   - Keep for safety period (minutes to hours)
```

### Rollback (If Issues Detected):

```
7. Instant rollback to Blue (if Green has issues):

   kubectl patch service bluegreen-service -n scenarios -p \
     '{"spec":{"selector":{"version":"blue"}}}'

   Result:
   t=0ms:    Command executed
   t=100ms:  All new connections go back to Blue

   Traffic flow:
   Client → bluegreen-service → Blue pods (nginx:1.20) ✅

   Rollback time: < 1 second!
   No deployment rebuild needed (Blue still running)
```

### Cleanup (After Successful Green Deployment):

```
8. Remove Blue environment (after safety period):

   # Wait 10-60 minutes to ensure Green is stable
   # Then delete Blue

   kubectl delete deployment bluegreen-blue -n scenarios

   State:
   - Green: Production environment ✅
   - Blue: Deleted

   For next deployment:
   - Update Blue deployment with newer version
   - Deploy Blue (becomes the new "Green")
   - Test, then switch Service to Blue
   - Delete old Green

   Blue-Green cycle continues!
```

---

## 📊 Blue-Green vs Other Deployment Strategies

### Blue-Green vs Rolling Update

| Feature | Blue-Green | Rolling Update |
|---------|------------|----------------|
| **Deployment Speed** | Instant switch | Gradual (pod-by-pod) |
| **Downtime** | Zero | Zero |
| **Rollback Speed** | Instant (<1s) | Slow (minutes) |
| **Resource Usage** | 2x (both running) | ~1.5x (during update) |
| **Risk** | Lower (full test before switch) | Higher (partial rollout) |
| **Validation** | Full environment test | Progressive |
| **Cost** | Higher (double resources) | Lower |
| **Complexity** | Medium (manage 2 environments) | Low (automatic) |

### Blue-Green vs Canary

| Feature | Blue-Green | Canary |
|---------|------------|--------|
| **Traffic Split** | 100% switch | Gradual % increase |
| **Risk** | All-or-nothing | Lower (slow rollout) |
| **Validation** | Before switch | During rollout |
| **Rollback** | Instant | Instant (stop canary) |
| **Use Case** | Critical apps | User-facing apps |
| **Complexity** | Medium | High (need metrics) |

### When to Use Blue-Green:

✅ **Use Blue-Green When:**
- Zero downtime is critical
- Need instant rollback capability
- Can afford 2x resources temporarily
- Want full validation before production traffic
- Deploying critical system changes (database schema, major versions)
- Regulatory/compliance requirements for rollback

❌ **Don't Use Blue-Green When:**
- Resources are constrained (can't run 2 environments)
- Small, low-risk changes (rolling update is fine)
- Need gradual rollout to subset of users (use canary)
- Database changes aren't backward compatible

---

## 🎯 Best Practices & Production Recommendations

### 1. Keep Environments Identical

```yaml
# GOOD - Both use same replica count
# Blue:
replicas: 10
# Green:
replicas: 10

# BAD - Different sizes
# Blue:
replicas: 10
# Green:
replicas: 2  # Not ready for full production load!
```

**Why?**
- Green must handle full production load
- Performance testing must be realistic
- Switching to under-provisioned Green causes outage

### 2. Use Readiness Probes

```yaml
spec:
  template:
    spec:
      containers:
      - name: app
        readinessProbe:
          httpGet:
            path: /health
            port: 80
          initialDelaySeconds: 10
          periodSeconds: 5
```

**Why?**
- Ensures pods are ready before receiving traffic
- Service won't route to non-ready pods
- Prevents errors during deployment

### 3. Implement Health Checks

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 80
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 3
```

**Endpoints:**
- `/health` or `/healthz` - Liveness (is app alive?)
- `/ready` - Readiness (can app serve traffic?)

### 4. Add Deployment Annotations

```yaml
metadata:
  annotations:
    deployment.kubernetes.io/revision: "5"
    app.version: "2.1.0"
    git.commit: "abc123def"
    deployed.by: "jane@example.com"
    deployed.at: "2024-01-15T10:30:00Z"
```

**Why?**
- Track deployment history
- Know who deployed what and when
- Link to source code version

### 5. Use PodDisruptionBudget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: bluegreen-blue-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: bluegreen
      version: blue
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: bluegreen-green-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: bluegreen
      version: green
```

**Why?**
- Prevents node maintenance from disrupting both environments
- Ensures minimum availability during cluster operations

### 6. Database Migrations Strategy

**Problem:** Database changes can break Blue-Green

**Solution: Backward-compatible migrations**

```
Phase 1: Deploy compatible schema
- Add new column (nullable)
- Don't remove old column yet
- Both Blue and Green work

Phase 2: Deploy Green
- Green uses new column
- Blue still uses old column
- Both work simultaneously

Phase 3: After Green stable
- Deploy Blue update to use new column
- Switch to Blue
- Delete Green

Phase 4: Cleanup
- Remove old column (in next deployment)
```

**Three-phase deployment pattern:**
```
Deployment N: Add new field (both versions work)
Deployment N+1: Use new field (stop writing to old)
Deployment N+2: Remove old field
```

### 7. Monitoring During Switch

**Metrics to watch:**
```bash
# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m]))

# Response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Request count
sum(rate(http_requests_total[5m]))

# Pod restarts
sum(kube_pod_container_status_restarts_total)
```

**Alert before switch:**
- Ensure all metrics stable
- No active incidents
- Green metrics == Blue metrics

### 8. Automated Testing Before Switch

```yaml
# Job to validate Green before switching
apiVersion: batch/v1
kind: Job
metadata:
  name: green-validation
spec:
  template:
    spec:
      containers:
      - name: test
        image: curlimages/curl
        command:
        - sh
        - -c
        - |
          # Test Green deployment
          for i in $(seq 1 100); do
            curl -f http://bluegreen-green-svc/health || exit 1
          done
          echo "Green validation passed!"
      restartPolicy: Never
```

### 9. Service Mesh Integration

**With Istio/Linkerd:**
```yaml
# VirtualService for Blue-Green
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bluegreen-vs
spec:
  hosts:
  - bluegreen-service
  http:
  - match:
    - headers:
        x-version:
          exact: green
    route:
    - destination:
        host: bluegreen-service
        subset: green
  - route:
    - destination:
        host: bluegreen-service
        subset: blue
```

**Benefits:**
- Header-based routing (test Green with special header)
- Traffic mirroring (shadow Green with copy of Blue traffic)
- Progressive rollout (10% → 50% → 100%)

---

## 🔧 Advanced Blue-Green Patterns

### Pattern 1: Header-Based Routing (Pre-Switch Testing)

```yaml
# Use Ingress annotations for header-based routing
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bluegreen-ingress
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-by-header: "X-Version"
    nginx.ingress.kubernetes.io/canary-by-header-value: "green"
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: bluegreen-green-service
            port:
              number: 80
```

**Usage:**
```bash
# Normal users go to Blue
curl https://app.example.com

# Testers go to Green
curl -H "X-Version: green" https://app.example.com
```

### Pattern 2: Progressive Blue-Green (Weight-Based)

```yaml
# Service 1: 90% Blue
apiVersion: v1
kind: Service
metadata:
  name: bluegreen-service-blue
spec:
  selector:
    app: bluegreen
    version: blue
  ports:
  - port: 80
---
# Service 2: 10% Green
apiVersion: v1
kind: Service
metadata:
  name: bluegreen-service-green
spec:
  selector:
    app: bluegreen
    version: green
  ports:
  - port: 80
---
# Ingress: Weight distribution
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bluegreen-ingress
  annotations:
    nginx.ingress.kubernetes.io/service-weight: |
      bluegreen-service-blue: 90
      bluegreen-service-green: 10
```

### Pattern 3: Blue-Green with Database per Environment

```yaml
# Blue uses blue-db
env:
- name: DATABASE_HOST
  value: "postgres-blue.scenarios.svc.cluster.local"

# Green uses green-db (replicated from blue)
env:
- name: DATABASE_HOST
  value: "postgres-green.scenarios.svc.cluster.local"
```

**Process:**
1. Replicate Blue DB to Green DB
2. Deploy Green app (using Green DB)
3. Test Green thoroughly
4. Switch traffic to Green
5. Promote Green DB to production

---

## 🔍 Debugging Commands

```bash
# Check current traffic routing
kubectl get svc bluegreen-service -n scenarios -o jsonpath='{.spec.selector}'

# Get all pods (both Blue and Green)
kubectl get pods -n scenarios -l app=bluegreen

# Get only Blue pods
kubectl get pods -n scenarios -l app=bluegreen,version=blue

# Get only Green pods
kubectl get pods -n scenarios -l app=bluegreen,version=green

# Check which pods Service routes to
kubectl get endpoints bluegreen-service -n scenarios

# Test Blue directly (bypass service)
kubectl run test --rm -it --image=curlimages/curl -- \
  curl http://<blue-pod-ip>

# Test Green directly
kubectl run test --rm -it --image=curlimages/curl -- \
  curl http://<green-pod-ip>

# Switch to Green
kubectl patch service bluegreen-service -n scenarios -p \
  '{"spec":{"selector":{"version":"green"}}}'

# Switch back to Blue (rollback)
kubectl patch service bluegreen-service -n scenarios -p \
  '{"spec":{"selector":{"version":"blue"}}}'

# Verify switch
kubectl get svc bluegreen-service -n scenarios -o yaml | grep version
```

---

## 🚨 Common Issues & Solutions

### Issue 1: Service routes to no pods after switch

```bash
$ kubectl get endpoints bluegreen-service
NAME                 ENDPOINTS
bluegreen-service    <none>
```

**Cause:** Selector doesn't match any pods (typo in label)

**Debug:**
```bash
# Check service selector
kubectl get svc bluegreen-service -o jsonpath='{.spec.selector}'

# Check pod labels
kubectl get pods -n scenarios --show-labels | grep bluegreen
```

**Solution:** Fix label mismatch

### Issue 2: Green deployment fails (pods crash)

**Cause:** New version has bugs, not tested properly

**Solution:**
1. Don't switch traffic (Blue still serves traffic)
2. Debug Green deployment
3. Fix and redeploy Green
4. Test again before switching

**This is WHY Blue-Green is safe!** Issues in Green don't affect production.

### Issue 3: Database migration breaks Blue after deploying Green

**Cause:** Non-backward-compatible schema change

**Solution:** Use three-phase migrations (see Best Practices #6)

### Issue 4: Both Blue and Green receiving traffic

**Cause:** Service selector missing `version` label

```yaml
# WRONG
selector:
  app: bluegreen  # Routes to BOTH Blue and Green!

# CORRECT
selector:
  app: bluegreen
  version: blue  # Routes to Blue only
```

---

## 🎓 Key Takeaways

1. **Blue-Green = Two identical environments** - Only one receives production traffic
2. **Service selector is the switch** - Change `version` label to route traffic
3. **Zero-downtime deployment** - Instant cutover (< 1 second)
4. **Instant rollback** - Switch selector back to Blue
5. **Test before switch** - Validate Green while Blue serves traffic
6. **Double resources temporarily** - Both environments run during deployment
7. **Database compatibility** - Schema must work with both versions
8. **Perfect for critical apps** - High-stakes deployments with instant rollback

---

*This explanation provides deep insights into Blue-Green deployment strategy for zero-downtime releases and instant rollback capability!*
