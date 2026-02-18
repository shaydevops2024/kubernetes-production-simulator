# ArgoCD YAML Explanation - Sync Waves and Hooks

This guide explains how sync waves control deployment order and how sync hooks run tasks at specific points during a sync operation.

---

## The Problem: Resource Ordering

Kubernetes applies all resources at roughly the same time. But many apps have dependencies:
- A Deployment needs a ConfigMap to exist first
- A Service should be created before the Deployment that uses it
- A database migration Job should run after the DB is up, but before the app

**Sync waves** solve the ordering problem. **Sync hooks** solve the "run tasks at specific sync lifecycle points" problem.

---

## Sync Waves — The argocd.argoproj.io/sync-wave Annotation

ArgoCD processes resources in **waves** from lowest to highest number. Resources in the same wave are applied together.

### Wave -1: ConfigMap (configmap.yaml)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
data:
  APP_ENV: "production"
```

**Wave -1** is the lowest here — it goes first. The ConfigMap must exist before the Deployment tries to read from it.

**Why negative numbers?** Waves can be any integer, including negative. By convention:
- Negative waves → prerequisites (namespaces, ConfigMaps, Secrets, CRDs)
- Wave 0 → core resources (Deployments, StatefulSets)
- Positive waves → post-deployment resources (Services exposing completed apps, Jobs)

**The data block:**

```yaml
data:
  APP_ENV: "production"
```

Simple key-value data. The Deployment reads `APP_ENV` from this ConfigMap via `configMapKeyRef`. If this ConfigMap doesn't exist when the Deployment starts, the pod crashes. Wave -1 ensures it's there first.

---

## Wave 0: Deployment (deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wave-app
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: wave-app
          image: nginx:1.21-alpine
          env:
            - name: APP_ENV
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: APP_ENV
```

**Wave 0** runs after all wave -1 resources are healthy (ready). ArgoCD waits for wave -1 resources to become healthy before moving to wave 0.

### env.valueFrom.configMapKeyRef

This injects the ConfigMap value as an environment variable:
- `name: app-config` — the ConfigMap to read from
- `key: APP_ENV` — which key to read

The pod gets `APP_ENV=production` in its environment. Because of wave ordering, the ConfigMap is guaranteed to exist when this pod starts.

---

## Wave 1: Service (service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: wave-service
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  type: ClusterIP
  selector:
    app: wave-app
  ports:
    - port: 80
      targetPort: 80
```

**Wave 1** runs after the Deployment (wave 0) is healthy — meaning pods are Running and Ready. Only then does the Service get created to expose them.

**Why not create the Service first?** A Service with no backing pods is harmless, but creating the Service after the Deployment is healthy is a useful pattern to confirm the app is actually running before traffic is routed to it.

---

## Sync Hooks — The post-sync-job.yaml

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: post-deploy-verify
  annotations:
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  template:
    spec:
      containers:
        - name: verify
          image: busybox
          command:
            - /bin/sh
            - -c
            - echo "Post-sync verification complete! Deployment successful." && sleep 5
      restartPolicy: Never
  backoffLimit: 1
```

### argocd.argoproj.io/hook: PostSync

This annotation marks the Job as a **sync hook**, not a regular resource. It's not shown in the application's regular resource tree — it only runs during specific sync lifecycle events.

**Available hook types:**

| Hook | When it runs |
|------|-------------|
| `PreSync` | Before any resources are applied |
| `Sync` | During sync, alongside wave resources |
| `PostSync` | After ALL resources are healthy |
| `SyncFail` | Only if the sync fails |
| `Skip` | Never synced (useful for disabling hooks temporarily) |

`PostSync` is ideal for:
- Smoke tests verifying the deployment works
- Sending notifications (Slack, PagerDuty)
- Running database migrations after the app is ready
- Warming up caches

### argocd.argoproj.io/hook-delete-policy: HookSucceeded

Controls when ArgoCD deletes the hook resource after it runs:

| Policy | Behavior |
|--------|---------|
| `HookSucceeded` | Delete after successful completion |
| `HookFailed` | Delete after failure |
| `BeforeHookCreation` | Delete old hook before creating new one |

`HookSucceeded` keeps the Job around if it fails (so you can `kubectl logs` to debug), and auto-cleans on success. This prevents Job accumulation over many deploys.

### restartPolicy: Never

Jobs use `Never` or `OnFailure`. `Never` means: if the container exits with error, create a new pod (up to `backoffLimit` times). Don't restart the same pod.

### backoffLimit: 1

If the Job fails, try once more (1 retry). After that, the Job is marked Failed and the sync hook is considered failed.

---

## How Waves and Hooks Work Together

Full sync order for this scenario:

```
1. Wave -1: ConfigMap applied → wait for Ready
2. Wave  0: Deployment applied → wait for pods Running+Ready
3. Wave  1: Service applied → wait for Ready
4. PostSync: Job runs → verifies deployment → auto-deleted on success
```

If anything in a wave fails or doesn't become healthy, ArgoCD stops and doesn't proceed to the next wave. This prevents cascading failures.

---

## The Application CR (application.yaml)

```yaml
syncPolicy:
  automated:
    selfHeal: true
  syncOptions:
    - CreateNamespace=true
```

Note: `prune: true` is not set here. This is intentional — the hook Job is meant to be auto-deleted by its hook policy, not pruned by ArgoCD's prune mechanism.

---

## Key Takeaways

- **Sync waves** control resource ordering — lower numbers deploy first
- **Wave -1**: prerequisites (ConfigMaps, Secrets) | **Wave 0**: app | **Wave 1+**: services/post-app
- ArgoCD waits for each wave to be **healthy** before starting the next wave
- **Hooks** run at lifecycle points: PreSync, Sync, PostSync, SyncFail
- `PostSync` hooks are perfect for smoke tests and notifications
- `HookSucceeded` delete policy keeps clean history while debugging failures
- Combine waves + hooks for complex, ordered deployments with validation
