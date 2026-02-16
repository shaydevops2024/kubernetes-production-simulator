# YAML Files Explanation - Liveness & Readiness Probes Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write health probes in Kubernetes.

---

## 🏥 deployment.yaml

### What are Health Probes?
Health probes are Kubernetes' way of monitoring container health. They answer two critical questions:
1. **Liveness**: Is the container alive? (If not, restart it)
2. **Readiness**: Is the container ready to serve traffic? (If not, remove from service)

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
kind: Deployment
```
**What it is:** Standard Deployment resource
**Why:** Deployments manage pods and provide declarative updates

```yaml
metadata:
  name: probes-demo-app
  namespace: scenarios
  labels:
    app: probes-demo
    scenario: "08"
```
**What it is:** Deployment metadata
- `name`: Unique identifier for the deployment
- `namespace`: Logical grouping (keeps demo resources isolated)
- `labels`: Key-value pairs for organization and selection

**Why labels matter:**
- Services use labels to find pods
- kubectl commands can filter by labels
- Monitoring tools group resources by labels

```yaml
spec:
  replicas: 2
```
**What it is:** Desired number of pod copies
**Why 2 replicas?**
- High availability - if one pod fails, service continues
- Demonstrates how readiness affects traffic distribution
- Shows multiple pods experiencing probe failures

```yaml
  selector:
    matchLabels:
      app: probes-demo
```
**What it is:** How Deployment finds its pods
**Critical:** Must match `template.metadata.labels` exactly
**Why:** Tells the Deployment which pods it manages

```yaml
  template:
    metadata:
      labels:
        app: probes-demo
```
**What it is:** Pod template labels
**Note:** These labels must match the selector above

```yaml
    spec:
      containers:
      - name: app
        image: k8s.gcr.io/liveness
```
**What it is:** Container specification
- `name`: Container name (used in logs, exec commands)
- `image`: Special Kubernetes demo image

**About k8s.gcr.io/liveness:**
- Designed specifically for testing probes
- Serves HTTP on port 8080
- Endpoint `/healthz` returns HTTP 200 for first 10 seconds
- After 10 seconds, returns HTTP 500 (simulates failure)
- Perfect for demonstrating automatic recovery

```yaml
        args:
        - /server
```
**What it is:** Command arguments passed to container
**Why:** Starts the HTTP server that responds to health checks

```yaml
        ports:
        - containerPort: 8080
```
**What it is:** Port the container exposes
**Why 8080:** The liveness image's HTTP server listens on this port
**Note:** This is documentation - doesn't actually open the port

---

## 💓 Liveness Probe Configuration

```yaml
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
```

### What is a Liveness Probe?
Checks if the container is alive and functioning. If the probe fails repeatedly, Kubernetes **restarts the container**.

### Probe Type: httpGet
**What it is:** HTTP GET request to a specified endpoint
**How it works:**
1. Kubernetes sends: `GET http://<pod-ip>:8080/healthz`
2. Expects: HTTP 200-399 status code
3. If 400+, 500+, or timeout: probe fails

**Alternative probe types:**
```yaml
# TCP Socket (just check if port is open)
livenessProbe:
  tcpSocket:
    port: 8080

# Command execution (check exit code)
livenessProbe:
  exec:
    command:
    - cat
    - /tmp/healthy

# gRPC (for gRPC services)
livenessProbe:
  grpc:
    port: 9090
```

**When to use each:**
- `httpGet`: Web servers, REST APIs (most common)
- `tcpSocket`: Databases, TCP services without HTTP
- `exec`: Custom health logic, file-based checks
- `grpc`: gRPC services

```yaml
          initialDelaySeconds: 3
```
**What it is:** Wait time before first probe
**Why 3 seconds?**
- Gives container time to start up
- The liveness image starts immediately (3s is enough)
- Too short: false failures during startup
- Too long: delays detecting real failures

**Production values:**
- Fast-starting apps: 5-10 seconds
- Spring Boot / JVM apps: 30-60 seconds
- Large applications: 60-120 seconds

```yaml
          periodSeconds: 10
```
**What it is:** How often to probe (every 10 seconds)
**Why 10 seconds?**
- Reasonable balance between responsiveness and overhead
- Catches failures within 10-30 seconds (with failureThreshold)
- Doesn't overwhelm the application with checks

**Production values:**
- Standard: 10 seconds
- Critical services: 5 seconds (faster detection)
- Low-priority: 15-30 seconds (less overhead)

```yaml
          failureThreshold: 3
```
**What it is:** Number of consecutive failures before restart
**Why 3 failures?**
- Prevents restart from transient issues (temporary network blip)
- With 10s period: 30 seconds of failures before restart
- Balances quick recovery vs stability

**Calculation:**
```
Time to restart = periodSeconds × failureThreshold
Example: 10s × 3 = 30 seconds of unhealthy state before restart
```

**Production considerations:**
- Higher threshold (5-10): Tolerates temporary issues
- Lower threshold (1-2): Faster restart, but may restart unnecessarily
- For databases: Use higher threshold (data consistency important)

**Default values (if not specified):**
```yaml
initialDelaySeconds: 0      # Starts immediately
periodSeconds: 10           # Check every 10s
failureThreshold: 3         # 3 failures trigger action
successThreshold: 1         # 1 success = healthy (liveness only)
timeoutSeconds: 1           # 1s timeout per probe
```

---

## ✅ Readiness Probe Configuration

```yaml
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8080
```

### What is a Readiness Probe?
Checks if the container is ready to serve traffic. If the probe fails, Kubernetes **removes the pod from service endpoints** (but doesn't restart it).

### Key Difference: Liveness vs Readiness

| Aspect | Liveness Probe | Readiness Probe |
|--------|---------------|-----------------|
| **Question** | Is it alive? | Is it ready? |
| **Failure Action** | Restart container | Remove from service |
| **Use Case** | Detect deadlocks, crashes | Control traffic flow |
| **Recovery** | Fresh container | Same container recovers |
| **Example Failure** | App deadlocked | Loading data, warming up |

**When both fail:**
- Liveness fails → Container restarts
- Readiness fails → No traffic sent (but container runs)
- Both can fail independently

**Real-world example:**
```
Startup sequence:
1. Container starts
2. Readiness fails (app warming up, loading cache)
3. No traffic sent yet (good!)
4. App finishes startup
5. Readiness passes
6. Traffic starts flowing

If app crashes:
1. Liveness fails after 3 checks
2. Container restarts
3. Cycle repeats
```

```yaml
          initialDelaySeconds: 5
```
**What it is:** Wait 5 seconds before first readiness check
**Why 5 seconds (vs 3 for liveness)?**
- App may start but not be ready to serve traffic
- Gives extra time for initialization
- Common pattern: readiness delay ≥ liveness delay

**Production pattern:**
```yaml
livenessProbe:
  initialDelaySeconds: 30    # Conservative - avoid killing during startup
readinessProbe:
  initialDelaySeconds: 10    # Less conservative - just delays traffic
```

```yaml
          periodSeconds: 5
```
**What it is:** Check readiness every 5 seconds
**Why 5 seconds (vs 10 for liveness)?**
- More frequent checks for faster traffic recovery
- Readiness probes are less "dangerous" (don't restart)
- Quicker to add pod back to service after recovery

**Common pattern:**
- Readiness: Check more often (5s)
- Liveness: Check less often (10s)

```yaml
          failureThreshold: 3
```
**What it is:** 3 consecutive failures before removing from service
**Why 3?**
- Same as liveness - prevents removing from service due to blip
- With 5s period: 15 seconds of failures before traffic stops

**Production optimization:**
```yaml
readinessProbe:
  periodSeconds: 5
  failureThreshold: 1        # Remove from service immediately on failure
  successThreshold: 3        # Require 3 consecutive successes to add back
```
**Why this pattern?**
- Fail fast: Protect users from broken pods
- Recover slowly: Ensure pod is truly stable before adding back

**successThreshold (readiness only):**
```yaml
readinessProbe:
  successThreshold: 3        # Need 3 consecutive passes
```
- **Liveness:** Always 1 (can't be changed)
- **Readiness:** Can be > 1 (default is 1)
- **Use case:** Prevent flapping (rapid add/remove from service)

---

## 🔄 How Probes Work Together

### Startup Sequence:
```
1. Pod created
2. Container starts (initialDelaySeconds begins)
3. Liveness: Wait 3s, then check every 10s
4. Readiness: Wait 5s, then check every 5s
5. If readiness passes: Add to service endpoints
6. Pod receives traffic
7. If liveness fails 3x: Restart container (back to step 2)
8. If readiness fails 3x: Remove from endpoints (pod still runs)
```

### Timeline Example:
```
t=0s:    Container starts
t=3s:    First liveness check (passes)
t=5s:    First readiness check (passes)
         → Pod added to service, receives traffic
t=10s:   App starts returning HTTP 500 (liveness image behavior)
t=13s:   Liveness check fails (1st failure)
t=15s:   Readiness check fails (1st failure)
         → Still in service (needs 3 failures)
t=20s:   Readiness fails again (2nd)
t=23s:   Liveness fails again (2nd)
t=25s:   Readiness fails (3rd) → Removed from service (no more traffic)
t=33s:   Liveness fails (3rd) → Container restart triggered
t=33s+:  Container restarts, cycle begins again
```

### What You'll See:
```bash
$ kubectl get pods -n scenarios
NAME                              READY   STATUS    RESTARTS   AGE
probes-demo-app-xxx               1/1     Running   0          20s   ← Healthy
probes-demo-app-xxx               0/1     Running   0          30s   ← Not ready (readiness failed)
probes-demo-app-xxx               0/1     Running   1          45s   ← Restarted (liveness failed)
probes-demo-app-xxx               1/1     Running   1          50s   ← Back to ready after restart
```

**READY column:**
- `1/1`: Readiness passed, receiving traffic
- `0/1`: Readiness failed, no traffic

**RESTARTS column:**
- Increments each time liveness probe triggers restart
- High restart count = app unhealthy or probes misconfigured

---

## 🌐 service.yaml

### What is a Service?
Provides stable networking for pods. Routes traffic only to pods that pass readiness probes.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: probes-demo-service
  namespace: scenarios
```
**What it is:** Service metadata
**DNS name:** `probes-demo-service.scenarios.svc.cluster.local`

```yaml
spec:
  selector:
    app: probes-demo
```
**What it is:** Finds pods with label `app: probes-demo`
**How readiness affects this:**
1. Service continuously watches matching pods
2. Queries each pod's readiness status
3. Only includes Ready pods in endpoints
4. Traffic only goes to pods in endpoints list

**Check endpoints:**
```bash
kubectl get endpoints probes-demo-service -n scenarios
```
**Output:**
```
NAME                  ENDPOINTS                     AGE
probes-demo-service   10.244.1.5:8080,10.244.2.3:8080   5m
```
- Shows pod IPs that are Ready
- Missing IPs = pods failed readiness

```yaml
  ports:
  - protocol: TCP
    port: 8080
    targetPort: 8080
```
**What it is:** Port mapping
- `port`: Service listens on 8080
- `targetPort`: Forwards to pod port 8080
- `protocol`: TCP (default)

**Traffic flow:**
```
Client → Service:8080 → Only Ready Pods:8080
```

---

## 🎯 Best Practices & Production Recommendations

### 1. Always Use Both Probes

✅ **DO:**
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

❌ **DON'T:**
```yaml
# Only liveness (no control over traffic)
livenessProbe:
  httpGet:
    path: /healthz

# No probes at all (no automatic recovery)
```

### 2. Use Different Endpoints

**Best practice:** Separate health checks
```yaml
livenessProbe:
  httpGet:
    path: /healthz      # Deep check: app alive?

readinessProbe:
  httpGet:
    path: /ready        # Shallow check: ready for traffic?
```

**Why different?**
- `/healthz`: Check core functionality (database connection, critical services)
- `/ready`: Check if can serve requests (cache loaded, dependencies available)

**Example implementation (Go):**
```go
// Liveness: Check if app is alive
http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
    if dbConnection.Ping() != nil {
        w.WriteHeader(500)  // Unhealthy - restart needed
        return
    }
    w.WriteHeader(200)  // Healthy
})

// Readiness: Check if ready for traffic
http.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
    if !cacheWarmedUp || dbConnectionPool.Available() == 0 {
        w.WriteHeader(503)  // Not ready - don't send traffic
        return
    }
    w.WriteHeader(200)  // Ready
})
```

### 3. Set Appropriate Delays

✅ **Production values:**
```yaml
livenessProbe:
  initialDelaySeconds: 60    # Conservative - avoid killing during startup
  periodSeconds: 10
  failureThreshold: 3        # 30s of failures before restart

readinessProbe:
  initialDelaySeconds: 10    # Faster - just delays traffic
  periodSeconds: 5
  failureThreshold: 3        # 15s of failures before removing
  successThreshold: 2        # Need 2 passes to add back
```

### 4. Startup Probe (Kubernetes 1.16+)

For slow-starting apps:
```yaml
startupProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 0
  periodSeconds: 10
  failureThreshold: 30       # 300 seconds (5 min) to start

livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  periodSeconds: 10
  failureThreshold: 3        # Only 30s after startup
```

**Why startup probe?**
- Allows long startup time (failureThreshold: 30 = 5 minutes)
- Once startup passes, liveness uses shorter threshold
- Prevents killing slow-starting apps

**Without startup probe:**
```yaml
livenessProbe:
  initialDelaySeconds: 300   # 5 min delay (wasteful!)
  # Can't detect failures during startup
```

### 5. Probe Timeouts

```yaml
livenessProbe:
  httpGet:
    path: /healthz
  timeoutSeconds: 3          # Default is 1s
```

**When to increase timeout:**
- Slow endpoints (complex health checks)
- Network latency issues
- Database queries in health check

**Warning:** Don't make health checks too complex!
- Should return quickly (< 1 second ideal)
- Don't run expensive queries
- Don't check external services (use readiness for that)

### 6. Resource Requests/Limits

```yaml
resources:
  requests:
    cpu: 100m
    memory: 64Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

**Why important for probes:**
- Without limits: Pod can consume entire node CPU
- High CPU = slow probe responses = false failures
- Set requests to guarantee CPU for health checks

### 7. Handle Probe Overhead

**Each probe = HTTP request**
```
Calculation:
- 2 pods
- Liveness every 10s + Readiness every 5s
- (2 pods × 1 liveness/10s) + (2 pods × 1 readiness/5s)
- = 0.2 + 0.4 = 0.6 requests/second
```

**With 100 pods:**
- 100 × 0.6 = 60 requests/second just for probes!

**Optimization:**
- Keep probe handlers lightweight
- Use in-memory checks (no database queries)
- Cache health status if needed

### 8. Common Mistakes

❌ **Mistake 1: No probes at all**
```yaml
containers:
- name: app
  image: my-app
  # No probes - no automatic recovery!
```

❌ **Mistake 2: Liveness checks external services**
```yaml
livenessProbe:
  httpGet:
    path: /health   # Checks database, Redis, APIs
```
**Problem:** If database is down, all pods restart (doesn't help!)

**Fix:** Use readiness for external dependencies
```yaml
livenessProbe:
  httpGet:
    path: /alive    # Just check if app process is alive

readinessProbe:
  httpGet:
    path: /ready    # Check database, dependencies
```

❌ **Mistake 3: Same probe for liveness and readiness**
```yaml
livenessProbe:
  httpGet:
    path: /health
readinessProbe:
  httpGet:
    path: /health   # Same endpoint!
```
**Problem:** Can cause restart loops
- If `/health` checks database
- Database down → readiness fails (OK, remove from service)
- Also liveness fails → restarts (NOT OK, doesn't help!)

❌ **Mistake 4: initialDelaySeconds too short**
```yaml
livenessProbe:
  initialDelaySeconds: 5    # App takes 30s to start!
```
**Problem:** Pod killed during normal startup

**Fix:**
```yaml
startupProbe:          # Use startup probe for slow starts
  failureThreshold: 30
livenessProbe:
  initialDelaySeconds: 30    # Or set realistic delay
```

❌ **Mistake 5: Ignoring probe failures in logs**
```
Warning  Unhealthy  10s   kubelet  Liveness probe failed: HTTP 500
```
**Don't ignore these!** Investigate root cause, don't just increase thresholds.

---

## 🔍 Debugging Probe Issues

### Check probe configuration:
```bash
kubectl describe pod <pod-name> -n scenarios
```
Look for:
- `Liveness:` section (shows config)
- `Readiness:` section
- `Events:` (shows probe failures)

### Watch probe events:
```bash
kubectl get events -n scenarios --watch
```

### Test health endpoint manually:
```bash
# Port-forward to pod
kubectl port-forward <pod-name> 8080:8080 -n scenarios

# In another terminal, test endpoint
curl http://localhost:8080/healthz
```

### Check pod logs:
```bash
kubectl logs <pod-name> -n scenarios
```
Look for:
- Health check requests in access logs
- Errors during health check handling

### Check endpoints list:
```bash
kubectl get endpoints probes-demo-service -n scenarios
```
- Missing pod IPs = readiness failed
- All IPs present = all pods ready

---

## 🎓 Key Takeaways

1. **Liveness = Restart, Readiness = Traffic Control**
   - Use liveness to detect unrecoverable failures
   - Use readiness to control when pods receive traffic

2. **Different Endpoints for Different Probes**
   - `/healthz`: Is the app alive? (liveness)
   - `/ready`: Can it serve traffic? (readiness)

3. **Conservative Liveness, Aggressive Readiness**
   - Liveness: Higher threshold, longer period (avoid unnecessary restarts)
   - Readiness: Lower threshold, shorter period (quickly stop bad traffic)

4. **Always Set Both Probes**
   - Without liveness: No automatic recovery from failures
   - Without readiness: Traffic sent to pods not ready

5. **Don't Check External Services in Liveness**
   - Liveness: Check if the app process is healthy
   - Readiness: Check if dependencies are available

6. **Use Startup Probes for Slow Starts**
   - Allows long startup without false liveness failures
   - Switches to fast liveness after startup complete

7. **Monitor Probe Failures**
   - High restart count = investigate root cause
   - Don't just increase thresholds to hide problems

8. **Test Your Health Endpoints**
   - Ensure they're fast (< 1 second)
   - Don't do expensive operations
   - Return proper HTTP status codes

---

*Liveness and readiness probes are essential for production Kubernetes deployments. They provide automatic recovery from failures and ensure only healthy pods receive traffic. Master these concepts to build robust, self-healing applications!*
