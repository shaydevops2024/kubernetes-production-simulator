# ArgoCD YAML Explanation - Resource Health and Health Checks

This guide explains how ArgoCD assesses resource health, what Kubernetes probes do, and how initContainers affect the health lifecycle.

---

## How ArgoCD Determines Health

ArgoCD tracks the health of every resource it manages. Health status affects:
- When sync waves advance to the next wave
- Whether a PostSync hook runs
- The overall application health displayed in the UI

ArgoCD has **built-in health checks** for standard Kubernetes resources:

| Resource | Healthy When |
|----------|-------------|
| `Deployment` | All desired replicas are Available |
| `Pod` | Running and all containers Ready |
| `Service` | Endpoints exist (pods are backing it) |
| `Job` | Completed successfully |
| `PersistentVolumeClaim` | Bound to a PersistentVolume |

---

## The Application CR (application.yaml)

```yaml
syncPolicy:
  automated:
    selfHeal: true
  syncOptions:
    - CreateNamespace=true
```

`selfHeal: true` here is particularly interesting with health checks. If a pod's health check fails and the Deployment goes into a degraded state, selfHeal will attempt to reconcile. But it can't fix a broken app — it can only ensure the manifest is applied correctly. This scenario intentionally creates a slow initialization to demonstrate ArgoCD's health tracking.

---

## The Deployment (manifests/deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: health-app
spec:
  replicas: 2
  template:
    spec:
      initContainers:
        - name: slow-init
          image: busybox:1.36
          command: ['sh', '-c', 'echo "Initializing..." && sleep 30 && echo "Init complete"']
      containers:
        - name: app
          image: nginx:1.21-alpine
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
```

---

## initContainers — Setup Before the App Starts

```yaml
initContainers:
  - name: slow-init
    image: busybox:1.36
    command: ['sh', '-c', 'echo "Initializing..." && sleep 30 && echo "Init complete"']
```

### What is an initContainer?

An **init container** runs to completion before the main app containers start. Common uses:
- Waiting for a database to be ready (`wait-for-db`)
- Running database migrations before the app starts
- Downloading configuration files
- Setting up filesystem permissions

### This specific initContainer

`sleep 30` — waits 30 seconds. This simulates a slow initialization (like waiting for a dependency). During these 30 seconds:
- The pod is in `Init:0/1` state
- ArgoCD shows the Deployment as `Progressing` (not yet `Healthy`)
- No traffic goes to the pod

**ArgoCD's reaction:** ArgoCD waits for the Deployment to become healthy before marking the sync as complete. With 2 replicas and a 30-second init, the total wait is significant — ArgoCD won't move to the next sync wave until all pods are Running + Ready.

### busybox:1.36

A minimal Linux image (~1MB) with basic shell utilities. Perfect for init containers that just need to run shell scripts. Always specify a version tag (`1.36`), not `latest`.

---

## readinessProbe — "Is this pod ready for traffic?"

```yaml
readinessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 5
```

### What it does

Kubernetes continuously checks: "Should I send traffic to this pod?"
- **Probe passes** → Pod is in the Service's endpoints → gets traffic
- **Probe fails** → Pod is removed from the Service's endpoints → no traffic

### httpGet

Makes an HTTP GET request to `http://pod-ip:80/`. If it returns 2xx or 3xx, the probe passes. For nginx, this returns 200 (the default page).

### initialDelaySeconds: 5

Wait 5 seconds after the container starts before running the first probe. This prevents false failures during startup. Set this higher for slow-starting apps.

### periodSeconds: 5

Check every 5 seconds. If the probe fails 3 consecutive times (default `failureThreshold: 3`), the pod is marked Not Ready and removed from load balancing.

**Why readinessProbe matters for ArgoCD:**

ArgoCD's Deployment health check waits for all replicas to be **Available** (which requires readiness). If readiness probes fail:
- ArgoCD health shows `Degraded`
- Auto-sync sync waves won't advance
- The Application shows `Progressing` for a long time

---

## livenessProbe — "Is this pod still alive?"

```yaml
livenessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 10
  periodSeconds: 10
```

### What it does

Kubernetes continuously checks: "Should I restart this pod?"
- **Probe passes** → Pod stays alive
- **Probe fails 3 times** → Kubernetes kills and restarts the container

### Difference: Liveness vs Readiness

| Probe | Failure Action | Purpose |
|-------|---------------|---------|
| **Readiness** | Remove from load balancer | "Not ready for traffic" |
| **Liveness** | Restart the container | "Pod is stuck/dead" |

**Order matters:** `initialDelaySeconds` for liveness (10s) > readiness (5s). You don't want the liveness probe to kill the container before the readiness probe has even had a chance to check if it's ready.

### When liveness probe fails

Example: nginx crashes internally but the process is still running (zombie state). The readiness probe might still pass (returning 200), but the liveness probe could detect the zombie state if configured to check a health endpoint that the app itself updates.

### Best practice: separate endpoints

Production apps should expose:
- `/health/ready` — readiness (checked by readinessProbe)
- `/health/live` — liveness (checked by livenessProbe)

This lets you control each independently. For example, you might mark a pod as "not ready" (stop traffic) while keeping it "alive" (don't restart) during a graceful shutdown.

---

## ArgoCD Health Status Lifecycle

For this Deployment with initContainers and probes, ArgoCD shows:

```
Sync triggered
     ↓
Pod state: Init:0/1 (running slow-init, 30 seconds)
ArgoCD: Progressing
     ↓
Init complete, main container starts
Pod state: 0/1 Running (readiness probe checking...)
ArgoCD: Progressing
     ↓
readinessProbe passes after initialDelaySeconds + probe success
Pod state: 1/1 Running (Ready)
     ↓
Both replicas Ready → Deployment Available
ArgoCD: Healthy ✓
```

---

## The Service (manifests/service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: health-service
spec:
  type: ClusterIP
  selector:
    app: health-app
  ports:
    - port: 80
      targetPort: 80
```

The Service only receives traffic from pods that pass their readiness probe. During the initContainer phase and early startup, the Service has no endpoints. Kubernetes automatically manages this — no configuration needed.

---

## Key Takeaways

- **ArgoCD health** is determined by Kubernetes resource conditions (Available, Ready, etc.)
- **initContainers** run before app containers — used for prerequisites and migrations
- **readinessProbe** controls traffic: failing pods are removed from load balancer endpoints
- **livenessProbe** controls restarts: failing pods are killed and restarted
- `initialDelaySeconds` prevents false failures during startup
- `periodSeconds` sets the check frequency
- ArgoCD waits for Deployment to be **Available** (all readiness probes passing) before marking sync complete
- Set `initialDelaySeconds` for liveness > readiness to avoid killing pods that are just "not ready yet"
