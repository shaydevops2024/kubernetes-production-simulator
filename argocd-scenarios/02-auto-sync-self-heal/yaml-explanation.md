# ArgoCD YAML Explanation - Auto-Sync and Self-Heal

This guide explains the key YAML configuration that enables ArgoCD's automated sync and self-healing capabilities.

---

## The Application CR with Auto-Sync (application.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sc02-auto-sync
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/shaydevops2024/kubernetes-production-simulator.git
    targetRevision: HEAD
    path: argocd-scenarios/02-auto-sync-self-heal/manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd-sc-02
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## The syncPolicy.automated Block — The Core of This Scenario

This is what makes Scenario 02 fundamentally different from Scenario 01. The `automated` block turns ArgoCD into a true GitOps operator.

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

### automated: (the parent key)

Enables automatic synchronization. Without this, ArgoCD only **detects** drift — it shows `OutOfSync` but waits for you to manually trigger sync. With `automated:`, ArgoCD **acts** on drift automatically (within ~3 minutes by default).

**How it works internally:**
1. ArgoCD runs a reconciliation loop every ~3 minutes (configurable)
2. It compares cluster state with Git state
3. If different AND `automated` is set → auto-trigger sync
4. If same → no action

### automated.prune: true

**What it does:** Automatically delete resources from the cluster that no longer exist in Git.

**Without prune:**
- You add `deployment.yaml` to Git → ArgoCD creates it ✅
- You remove `deployment.yaml` from Git → ArgoCD does NOT delete it from cluster ⚠️
- Old resources accumulate, causing confusion and wasted resources

**With prune: true:**
- Remove a manifest from Git → ArgoCD deletes it from the cluster automatically

**Safety consideration:** Pruning can delete data (e.g., PersistentVolumeClaims). Some teams disable prune and handle deletions manually. For stateless apps like nginx, prune is safe.

### automated.selfHeal: true

**What it does:** When something in the cluster drifts from Git, ArgoCD automatically reverts it back to the Git state.

**Without selfHeal:**
- You manually run `kubectl scale deployment --replicas=5`
- ArgoCD shows `OutOfSync` but does nothing
- The manual change persists

**With selfHeal: true:**
- You manually run `kubectl scale deployment --replicas=5`
- ArgoCD detects drift within ~3 minutes
- ArgoCD reverts to `replicas: 3` (as defined in Git)
- This enforces Git as the **single source of truth**

**Typical scenarios selfHeal catches:**
- Manual kubectl changes
- Admission controllers modifying resources
- Rolling restart changing pod specs temporarily
- Someone running `kubectl edit` in production

---

## Sync Intervals and Timing

ArgoCD doesn't watch in real-time by default. It uses two mechanisms:

### Webhook (immediate)

If you configure a GitHub webhook pointing to ArgoCD, every `git push` triggers an immediate sync check. Most production setups use webhooks.

### Polling (fallback)

Without webhooks, ArgoCD polls Git every **3 minutes** (configurable via `--app-resync-period`). So after a commit, changes appear within 0–3 minutes.

---

## The Deployment (manifests/deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autosync-app
spec:
  replicas: 3
```

### replicas: 3

With selfHeal enabled, this value is **enforced**. Try running `kubectl scale deployment autosync-app --replicas=1 -n argocd-sc-02` — ArgoCD will restore it to 3 replicas within minutes. This demonstrates why self-heal is powerful in production: nobody can accidentally (or maliciously) change replica counts without going through Git.

---

## prune vs selfHeal — What's the Difference?

| Feature | Triggered By | Direction |
|---------|-------------|-----------|
| **selfHeal** | Cluster state differs from Git | Cluster → reverts to Git |
| **prune** | Git manifest removed | Cluster resource → deleted |

- `selfHeal` handles **modifications** to existing resources
- `prune` handles **deletions** of resources from Git

---

## When to Use Each Setting

### Use `automated` when:
- You want true GitOps — Git is the only way to change the cluster
- Your team uses PRs/MRs for all changes
- You have good test coverage and trust your CI pipeline

### Use `prune: true` when:
- You want clean namespaces with no orphaned resources
- Your app is stateless (safe to delete and recreate)
- You trust your Git history as the source of truth

### Disable prune when:
- Resources contain important data (databases, PVCs)
- You want a safety net against accidental manifest deletions

### Use `selfHeal: true` when:
- You want to enforce immutability — no manual kubectl changes
- You're in a regulated environment needing audit trails
- You want to prevent configuration drift

### Disable selfHeal when:
- You need to temporarily patch something in production without a full commit
- You're debugging and making temporary changes
- Operators need manual override capability

---

## The Service (manifests/service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: autosync-service
spec:
  type: ClusterIP
  selector:
    app: autosync-app
  ports:
    - port: 80
      targetPort: 80
```

Same structure as Scenario 01. With auto-sync, if you manually delete this Service via `kubectl delete service autosync-service -n argocd-sc-02`, ArgoCD will recreate it automatically. selfHeal restores deleted resources too, not just modified ones.

---

## Key Takeaways

- **`automated:`** turns ArgoCD from a drift detector into a drift corrector
- **`prune: true`** keeps clusters clean when manifests are removed from Git
- **`selfHeal: true`** enforces Git as single source of truth — reverts manual changes
- Auto-sync checks happen every ~3 minutes (or immediately with webhooks)
- These three settings together implement true **GitOps**: every cluster change must go through Git
