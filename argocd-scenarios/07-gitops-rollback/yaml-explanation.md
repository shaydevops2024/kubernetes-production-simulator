# ArgoCD YAML Explanation - GitOps Rollback

This guide explains how ArgoCD enables rollbacks the GitOps way, and what makes this scenario's YAML significant for understanding rollback strategies.

---

## Why GitOps Rollback is Different

### Traditional rollback:
```bash
kubectl rollout undo deployment/my-app
```
This reverts the Deployment in the cluster, but Git still has the "bad" version. The cluster is now out of sync with Git.

### GitOps rollback:
```bash
git revert <bad-commit>   # OR
git checkout <good-commit> -- manifests/deployment.yaml
git push
```
Git becomes the rollback mechanism. ArgoCD detects the Git change and applies it. Git history = deployment history.

---

## The Application CR (application.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sc07-rollback
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/shaydevops2024/kubernetes-production-simulator.git
    targetRevision: HEAD
    path: argocd-scenarios/07-gitops-rollback/manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd-sc-07
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
```

### No automated: block — intentional!

This scenario uses **manual sync** deliberately. Here's why:

- **Manual sync** lets you control exactly which Git revision to deploy
- You can sync to HEAD, or sync to a specific previous revision
- With `automated:`, ArgoCD always follows HEAD — you'd need to create a new commit to "rollback"
- With manual sync, you can use `argocd app history` and `argocd app rollback` to deploy any previous revision

**Rollback strategies summary:**

| Strategy | auto-sync | Method |
|----------|-----------|--------|
| **Git revert** | Yes/No | `git revert` creates a new commit, ArgoCD syncs it |
| **ArgoCD history rollback** | **No** (manual sync required) | `argocd app rollback <app> <revision-id>` |
| **Branch/tag rollback** | Yes/No | Change `targetRevision` to a stable tag |

---

## The Deployment (manifests/deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rollback-app
  annotations:
    version: "v1"
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: app
          image: nginx:1.20-alpine
```

### annotations: version: "v1"

This annotation marks the current version. In this scenario, you'll simulate a "bad deployment" by patching this annotation to `"v2"` and the image to something broken. The rollback restores it to `"v1"` with the working image.

**Custom annotations** like `version: "v1"` don't affect Kubernetes behavior — they're metadata for humans and tooling. You can add any annotation you like.

### image: nginx:1.20-alpine

**Specific older image version** (1.20, not 1.21). This is intentional — in this scenario:
- v1 = `nginx:1.20-alpine` (the "good" version)
- v2 = a deliberately broken image (you'll patch this during the scenario)

When you rollback, you're restoring the manifest that points to the good image.

### replicas: 3

Three replicas ensure high availability. During a rollout (including rollback), Kubernetes uses the `RollingUpdate` strategy by default:
- Brings up new pods before terminating old ones
- Ensures at least some pods are always running
- `maxUnavailable: 25%` and `maxSurge: 25%` by default

---

## How ArgoCD Tracks Deployment History

Every time ArgoCD syncs, it records:
- **Revision** — the Git commit SHA that was deployed
- **Timestamp** — when the sync happened
- **Deploy info** — who/what triggered the sync

You can view this with:
```bash
argocd app history sc07-rollback
```

Output example:
```
ID  DATE                           REVISION
0   2024-01-15 10:00:00 +0000 UTC  abc123 (HEAD)
1   2024-01-14 15:30:00 +0000 UTC  def456
2   2024-01-13 09:00:00 +0000 UTC  ghi789
```

To rollback to revision 1:
```bash
argocd app rollback sc07-rollback 1
```

ArgoCD re-applies the manifests from that Git commit, not the current HEAD.

---

## GitOps Rollback Patterns

### Pattern 1: ArgoCD History Rollback (this scenario)

```bash
argocd app history sc07-rollback
argocd app rollback sc07-rollback <ID>
```

Pros: Instant, no Git commit needed
Cons: Cluster diverges from HEAD in Git temporarily. Auto-sync would immediately undo it!
**Requires: manual sync (no `automated:` in syncPolicy)**

### Pattern 2: Git Revert (preferred for production)

```bash
git log --oneline
git revert <bad-commit-sha>
git push
```

Pros: Git history shows exactly what happened, cluster stays in sync with Git
Cons: Requires a new commit (but this is actually a feature — it's auditable)

### Pattern 3: targetRevision to a stable tag

```yaml
# Change this in the Application CR:
source:
  targetRevision: v2.1.0   # Known good tag
```

Pros: Clear, versioned rollback point
Cons: Requires updating the Application CR

---

## The Service (manifests/service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: rollback-service
spec:
  type: ClusterIP
  selector:
    app: rollback-app
  ports:
    - port: 80
      targetPort: 80
```

The service is stable across rollbacks — only the Deployment image changes. Traffic continues flowing through the same Service during the rollback rolling update.

---

## Kubernetes Rolling Update During Rollback

When ArgoCD applies the rolled-back Deployment, Kubernetes performs a rolling update:

```
Before rollback: [v2 pod] [v2 pod] [v2 pod]
During rollback: [v2 pod] [v2 pod] [v1 pod]  ← new v1 pod starts
                 [v2 pod] [v1 pod] [v1 pod]  ← v2 pod terminates
After rollback:  [v1 pod] [v1 pod] [v1 pod]  ← all v1, zero downtime
```

This gradual replacement ensures the app stays available during rollback.

---

## Key Takeaways

- **GitOps rollback** means reverting Git, not running `kubectl rollout undo`
- `argocd app rollback` redeploys a previous Git revision — requires **manual sync** (no `automated:`)
- `git revert` + push is the preferred production pattern — keeps Git and cluster in sync
- The `version: "v1"` annotation marks deployment versions for human readability
- Image tags in manifests are your deployment version control — use specific tags, not `latest`
- Kubernetes rolling updates ensure zero downtime even during rollbacks
- ArgoCD keeps full deployment history: `argocd app history <app>`
