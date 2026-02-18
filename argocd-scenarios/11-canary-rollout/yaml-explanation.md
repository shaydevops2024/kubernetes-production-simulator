# ArgoCD YAML Explanation - Canary Rollout with Argo Rollouts

This guide explains the Argo Rollouts `Rollout` resource, canary deployment strategy, and how ArgoCD integrates with Argo Rollouts for progressive delivery.

---

## The Problem: Standard Kubernetes Deployments Are All-or-Nothing

When you update a Kubernetes Deployment image:
1. New pods start replacing old pods (rolling update)
2. Within minutes, ALL traffic goes to the new version
3. If the new version has a bug: 100% of users are affected

**Canary deployment** solves this by gradually shifting traffic to the new version:
- 25% of traffic → new version (only 25% of users are affected if there's a bug)
- Validate it works → increase to 50%
- Validate again → increase to 100%

---

## Argo Rollouts: What It Is

**Argo Rollouts** is a separate Kubernetes controller (part of the Argo project) that extends Kubernetes with advanced deployment strategies. It replaces the standard `Deployment` resource with a `Rollout` CRD that supports:
- **Canary** — gradual traffic shifting
- **Blue-Green** — instant switch between two environments
- **Automated analysis** — auto-promote or rollback based on metrics

ArgoCD integrates natively with Argo Rollouts — it understands the `Rollout` health status and can display canary progress in the UI.

---

## The Rollout Resource (manifests/rollout.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: canary-app
spec:
  replicas: 4
  selector:
    matchLabels:
      app: canary-app
  template:
    metadata:
      labels:
        app: canary-app
    spec:
      containers:
        - name: app
          image: nginx:1.20-alpine
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "100m"
  strategy:
    canary:
      steps:
        - setWeight: 25
        - pause: {}
        - setWeight: 50
        - pause: {duration: 30s}
        - setWeight: 75
        - pause: {duration: 30s}
```

---

## Field-by-Field: The Rollout

### apiVersion: argoproj.io/v1alpha1, kind: Rollout

This is **not** a standard Kubernetes resource. It's a CRD (Custom Resource Definition) installed by Argo Rollouts. The Argo Rollouts controller watches for `Rollout` resources and manages the canary logic.

### spec.replicas: 4

Total pods across all versions (stable + canary). At 25% canary weight:
- 3 pods serve the stable (old) version
- 1 pod serves the canary (new) version

At 50% weight:
- 2 pods stable
- 2 pods canary

### template (same as Deployment)

The pod template is identical to a standard Deployment's `spec.template`. This is intentional — migrating from Deployment to Rollout is mostly just changing `kind: Deployment` to `kind: Rollout` and adding a `strategy:` block.

### image: nginx:1.20-alpine

The initial "stable" version. When you update this to `nginx:1.21-alpine`, Argo Rollouts starts the canary process — gradually shifting traffic instead of immediately replacing all pods.

---

## spec.strategy.canary — The Canary Steps

```yaml
strategy:
  canary:
    steps:
      - setWeight: 25
      - pause: {}
      - setWeight: 50
      - pause: {duration: 30s}
      - setWeight: 75
      - pause: {duration: 30s}
```

Steps are executed sequentially. The Argo Rollouts controller progresses through them automatically (for timed pauses) or waits for manual promotion (for indefinite pauses).

### setWeight: 25

Shifts 25% of traffic to the canary (new) version. Argo Rollouts adjusts the number of canary pods to achieve this weight. With 4 replicas: 1 canary pod, 3 stable pods.

### pause: {}

**Indefinite pause** — waits forever until you manually promote (approve the next step). Use this when you want human validation:
```bash
# Approve to continue
kubectl argo rollouts promote canary-app -n argocd-sc-11
```

Or in the Argo Rollouts dashboard, click the "Promote" button.

**Why pause indefinitely at 25%?**
- Real users are now hitting the canary
- Check error rates, latency, business metrics
- Only promote if metrics look good
- Rollback if they don't: `kubectl argo rollouts abort canary-app -n argocd-sc-11`

### pause: {duration: 30s}

**Timed pause** — automatically advances after 30 seconds. Used when you trust automated checks or just want a short baking period between weight increases.

In production, you'd use longer durations (5-10 minutes) and integrate with automated analysis tools (Prometheus, Datadog) to automatically promote or rollback based on metrics.

---

## Full Canary Progression

With 4 replicas, here's what happens when you update the image:

```
Step 0: 4 stable pods, 0 canary pods (update triggered)
    ↓ setWeight: 25
Step 1: 3 stable pods, 1 canary pod (25% of traffic → new version)
    ↓ pause: {} (WAIT FOR HUMAN APPROVAL)
Step 2: Manual promote → continue
    ↓ setWeight: 50
Step 3: 2 stable pods, 2 canary pods (50% of traffic → new version)
    ↓ pause: {duration: 30s}
Step 4: Wait 30 seconds automatically
    ↓ setWeight: 75
Step 5: 1 stable pod, 3 canary pods (75% of traffic → new version)
    ↓ pause: {duration: 30s}
Step 6: Wait 30 seconds automatically
    ↓ (no more steps)
Step 7: 0 stable pods, 4 canary pods (100% → new version, becomes new stable)
```

---

## The Service (manifests/service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: canary-service
spec:
  type: ClusterIP
  selector:
    app: canary-app
  ports:
    - port: 80
      targetPort: 80
```

**Important:** Argo Rollouts manages traffic weighting by adjusting the **number of pods**, not by modifying the Service. Since both stable and canary pods have `app: canary-app`, the Service sends traffic to all pods. With more stable pods than canary pods, more traffic statistically hits stable.

For more precise traffic control (exact percentages regardless of replica count), Argo Rollouts integrates with Istio or other service meshes using traffic splitting rules.

---

## The ArgoCD Application (application.yaml)

```yaml
syncPolicy:
  automated:
    selfHeal: true
  syncOptions:
    - CreateNamespace=true
```

ArgoCD syncs the `Rollout` manifest just like any other resource. When ArgoCD detects a change in `image:`, it applies the updated Rollout spec. Argo Rollouts controller then starts the canary process.

**ArgoCD + Argo Rollouts health integration:**
- While a canary is in progress: ArgoCD shows `Progressing` (not Healthy)
- After the canary completes: ArgoCD shows `Healthy`
- If you abort the rollout: ArgoCD shows `Degraded`

---

## Rollback During Canary

If something goes wrong at any step:

```bash
# Rollback to stable version immediately
kubectl argo rollouts abort canary-app -n argocd-sc-11
```

Argo Rollouts immediately scales the canary pods down to 0 and restores the stable pods to full replicas. This is much faster than a Git revert + sync cycle.

For GitOps-style rollback: revert the image tag in Git, push, ArgoCD syncs, Argo Rollouts starts a new canary of the reverted image.

---

## Key Takeaways

- **Argo Rollouts** extends Kubernetes with the `Rollout` CRD — a drop-in replacement for `Deployment`
- **Canary steps** are executed sequentially: `setWeight` shifts traffic, `pause` waits
- `pause: {}` — indefinite pause, requires manual promotion (`kubectl argo rollouts promote`)
- `pause: {duration: 30s}` — automatic progression after the specified time
- Traffic weighting works by adjusting replica counts (25% = 1 of 4 pods is canary)
- ArgoCD integrates natively: tracks `Rollout` health, shows canary progress in UI
- **Abort at any step** to immediately roll back to the stable version
- In production: combine timed pauses with automated metric analysis for fully automated progressive delivery
