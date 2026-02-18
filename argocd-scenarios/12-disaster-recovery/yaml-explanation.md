# ArgoCD YAML Explanation - Disaster Recovery

This guide explains how ArgoCD enables disaster recovery by serving as the single source of truth, and what makes this scenario's YAML configuration ideal for demonstrating auto-recovery.

---

## ArgoCD as Disaster Recovery Tool

Traditional disaster recovery requires:
- Manual runbooks ("run this kubectl command, then that one...")
- Backups that might be out of date
- Human intervention to restore state

**ArgoCD + Git = automatic disaster recovery:**
- Git IS the backup — every manifest, every configuration
- ArgoCD continuously reconciles cluster state with Git
- Deleted namespace? ArgoCD restores it automatically (with `selfHeal: true` + `prune: true`)
- Corrupted resources? ArgoCD replaces them from Git

---

## The Application CR (application.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sc12-disaster-recovery
  namespace: argocd
  labels:
    scenario: "12"
    category: disaster-recovery
spec:
  project: default
  source:
    repoURL: https://github.com/YOURUSER/YOURREPO.git
    targetRevision: HEAD
    path: argocd-scenarios/12-disaster-recovery/manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd-sc-12
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### The critical combination: automated + prune + selfHeal + CreateNamespace

This specific combination of settings is what makes disaster recovery work:

| Setting | Role in Disaster Recovery |
|---------|--------------------------|
| `automated:` | ArgoCD acts automatically without human intervention |
| `selfHeal: true` | Restores modified/deleted resources from Git |
| `prune: true` | Keeps the namespace clean (removes orphaned resources) |
| `CreateNamespace=true` | Recreates the entire namespace if deleted |

**The disaster recovery scenario:**

1. Someone runs `kubectl delete namespace argocd-sc-12` (intentional or accidental)
2. Everything in that namespace is gone: Deployment, Service, ConfigMap, all data
3. ArgoCD detects the drift (namespace missing → resources missing)
4. `CreateNamespace=true` → ArgoCD recreates the namespace
5. `selfHeal: true` → ArgoCD reapplies all manifests from Git
6. Within 3 minutes (or immediately with webhooks): everything is restored

**Without `selfHeal: true`:** ArgoCD detects the deletion and shows `OutOfSync`, but does nothing. Human must manually trigger sync.

**Without `CreateNamespace=true`:** ArgoCD cannot recreate the namespace (which is a cluster-scoped resource) and the sync fails.

---

## The Deployment (manifests/deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dr-app
  namespace: argocd-sc-12
  labels:
    app: dr-app
    scenario: disaster-recovery
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: app
          image: nginx:1.21-alpine
          volumeMounts:
            - name: content
              mountPath: /usr/share/nginx/html
      volumes:
        - name: content
          configMap:
            name: dr-content
```

### replicas: 3

Three replicas provide the base for high availability. With `selfHeal: true`, if someone manually scales this to 0 (accidentally or a misguided "quick fix"), ArgoCD restores it to 3 within minutes.

### namespace: argocd-sc-12 in metadata

The namespace is specified directly in the manifest. This is important for disaster recovery — when the namespace is deleted and ArgoCD recreates it, it needs this explicit namespace in the manifest to know where to place each resource.

### labels: scenario: disaster-recovery

A label marking this deployment as part of the DR scenario. Good practice for filtering and organizing resources: `kubectl get all -l scenario=disaster-recovery`.

### volumeMounts + volumes (ConfigMap mounting)

```yaml
volumeMounts:
  - name: content
    mountPath: /usr/share/nginx/html
volumes:
  - name: content
    configMap:
      name: dr-content
```

The Deployment mounts the ConfigMap as a volume. This means both the Deployment AND the ConfigMap must be restored for the app to work correctly. With `selfHeal: true`, both are restored from Git. This demonstrates that ArgoCD restores the full application state, not just individual resources.

---

## The ConfigMap (manifests/configmap.yaml)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: dr-content
  namespace: argocd-sc-12
  labels:
    app: dr-app
data:
  index.html: |
    <!DOCTYPE html>
    <html>
    <head><title>Disaster Recovery Demo</title></head>
    <body>
      <h1>Disaster Recovery Application</h1>
      <p>This application is managed by ArgoCD.</p>
      <p>Even if this is deleted, ArgoCD will restore it from Git!</p>
    </body>
    </html>
```

### Why a ConfigMap in a DR scenario?

The ConfigMap is intentionally included to demonstrate that ArgoCD restores **all** resources, not just Deployments and Services. After a namespace deletion:
1. ConfigMap is gone (along with everything else)
2. ArgoCD restores the ConfigMap from Git
3. The volume mount works again because `dr-content` ConfigMap exists

The HTML message itself ("Even if this is deleted, ArgoCD will restore it from Git!") is a self-referential comment that makes the scenario's purpose clear to anyone who accesses the app.

### ConfigMap as "stateless state"

This ConfigMap contains static HTML — it's configuration, not user data. Git stores it permanently. Even after a catastrophic cluster failure:
- Restore ArgoCD → Apply the Application CR → ArgoCD restores everything from Git

**What Git-backed DR cannot recover:**
- Database data (PersistentVolumes) — need separate backup strategy
- User-uploaded files — need object storage (S3, GCS)
- Secrets with runtime-generated values — need secrets management (Vault, Sealed Secrets)

Git + ArgoCD is perfect for infrastructure-as-code and stateless applications. Stateful data needs additional DR strategies.

---

## The Service (manifests/service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: dr-service
  namespace: argocd-sc-12
  labels:
    app: dr-app
spec:
  selector:
    app: dr-app
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
```

The Service has a static selector (`app: dr-app`) that doesn't change between deployments. After disaster recovery, the Service is recreated with the same configuration, immediately routing traffic to the restored pods.

---

## Disaster Recovery Scenarios ArgoCD Handles

| Disaster | ArgoCD Response |
|---------|----------------|
| `kubectl delete namespace` | Recreates namespace + all resources |
| `kubectl delete deployment` | Restores deployment from Git |
| `kubectl scale --replicas=0` | Scales back to desired count |
| `kubectl edit deployment` (wrong change) | Reverts to Git version |
| Node failure (pods rescheduled) | Kubernetes handles it; ArgoCD confirms health |
| Accidental ConfigMap deletion | Recreates from Git |
| Bad deployment (broke the app) | Use `argocd app rollback` to previous Git revision |

---

## Building a Complete DR Strategy with ArgoCD

```
Git Repository (permanent backup of all manifests)
    ↓
ArgoCD (continuously reconciles)
    ↓
Kubernetes Cluster

For stateful data:
Velero (cluster backup) + Cloud storage (PV snapshots)
External Secrets Operator (secrets from Vault/AWS SM)
Database backups (automated, outside of ArgoCD)
```

ArgoCD handles the **Kubernetes layer** of DR. Combine it with tools for stateful data.

---

## Key Takeaways

- **`selfHeal: true` + `prune: true` + `CreateNamespace=true`** = complete automated DR
- `selfHeal` restores modified or deleted resources — the core of GitOps DR
- `CreateNamespace=true` enables recovery even after namespace deletion
- ArgoCD restores **all** managed resources: Deployments, Services, ConfigMaps, etc.
- Git = permanent, version-controlled backup of all application configuration
- DR time = however long ArgoCD's reconciliation loop takes (up to 3 minutes, or instant with webhooks)
- ArgoCD DR is ideal for **stateless applications** — stateful data needs separate backup strategies
- The Application CR itself should also be in Git (bootstrap repo) so ArgoCD itself can be restored
