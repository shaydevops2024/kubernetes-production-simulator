# ArgoCD YAML Explanation - RBAC and Project Isolation

This guide explains ArgoCD AppProjects, how they enforce multi-tenancy, and what the YAML configuration means for security boundaries.

---

## The Problem: Multi-Tenancy in ArgoCD

Without projects, any ArgoCD Application can:
- Deploy to any namespace
- Use any Git repository
- Deploy any Kubernetes resource type

In a real organization, you need to ensure:
- Team A can only deploy to their namespaces
- Team B cannot accidentally (or maliciously) deploy to Team A's namespaces
- Applications can only use approved Git repositories
- Sensitive resource types (ClusterRoles, etc.) are restricted

**AppProjects** are ArgoCD's solution.

---

## AppProject: team-backend (project-backend.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-backend
  namespace: argocd
spec:
  description: Backend team project - restricted to backend namespace
  sourceRepos:
    - 'https://github.com/shaydevops2024/kubernetes-production-simulator.git'
  destinations:
    - namespace: argocd-sc-10-be
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: ''
      kind: Namespace
  namespaceResourceWhitelist:
    - group: ''
      kind: '*'
    - group: 'apps'
      kind: '*'
```

---

## Field-by-Field: AppProject

### apiVersion: argoproj.io/v1alpha1, kind: AppProject

A Custom Resource provided by ArgoCD. Must be in the `argocd` namespace (same as Application CRs).

### spec.description

Human-readable description of the project's purpose. Shown in the ArgoCD UI.

### spec.sourceRepos

```yaml
sourceRepos:
  - 'https://github.com/shaydevops2024/kubernetes-production-simulator.git'
```

**Whitelist of allowed Git repositories.** Applications in this project can ONLY use repos listed here.

- If an Application tries to use a different `repoURL`, ArgoCD rejects it
- Use `'*'` to allow any repository (equivalent to no restriction — not recommended)
- Can list multiple repos for teams that use several repositories

**Security value:** Prevents someone from creating an Application that pulls manifests from an untrusted repository to deploy malicious workloads.

### spec.destinations

```yaml
destinations:
  - namespace: argocd-sc-10-be
    server: https://kubernetes.default.svc
```

**Whitelist of allowed deployment targets.** Applications in `team-backend` can ONLY deploy to `argocd-sc-10-be` namespace on this cluster.

- `namespace: argocd-sc-10-be` — only this namespace is allowed
- `namespace: '*'` — allow any namespace (no restriction)
- `server: https://kubernetes.default.svc` — only this cluster
- Can list multiple destination entries

**Security value:** Backend team cannot accidentally deploy to frontend namespace or any other namespace. This is the primary isolation mechanism.

---

## spec.clusterResourceWhitelist

```yaml
clusterResourceWhitelist:
  - group: ''
    kind: Namespace
```

**Cluster-scoped resources** (not namespace-scoped) that Applications in this project are allowed to create.

- `group: ''` — core Kubernetes API group (empty string = core group)
- `kind: Namespace` — only allowed to create Namespace resources

**Why only Namespace?** Cluster-scoped resources (ClusterRole, ClusterRoleBinding, StorageClass, etc.) have cluster-wide impact. Restricting them to just `Namespace` prevents teams from granting themselves elevated permissions.

**If empty/omitted:** No cluster-scoped resources can be created at all.

---

## spec.namespaceResourceWhitelist

```yaml
namespaceResourceWhitelist:
  - group: ''
    kind: '*'
  - group: 'apps'
    kind: '*'
```

**Namespace-scoped resources** that Applications can create/manage.

- `group: '', kind: '*'` — ALL core resources (Pods, Services, ConfigMaps, Secrets, etc.)
- `group: 'apps', kind: '*'` — ALL apps resources (Deployments, StatefulSets, DaemonSets, ReplicaSets)

This allows the standard app deployment resources but excludes:
- `networking.k8s.io` — NetworkPolicies, Ingresses
- `rbac.authorization.k8s.io` — Roles, RoleBindings
- `batch` — Jobs, CronJobs

To allow RBAC resources, you'd add:
```yaml
- group: 'rbac.authorization.k8s.io'
  kind: '*'
```

---

## AppProject: team-frontend (project-frontend.yaml)

```yaml
spec:
  description: Frontend team project - restricted to frontend namespace
  sourceRepos:
    - 'https://github.com/shaydevops2024/kubernetes-production-simulator.git'
  destinations:
    - namespace: argocd-sc-10-fe    # ← Different namespace!
      server: https://kubernetes.default.svc
```

Nearly identical to the backend project, but destination namespace is `argocd-sc-10-fe` instead of `argocd-sc-10-be`. This is the key isolation: each team's project restricts where they can deploy.

---

## The Applications

### app-backend.yaml (correct project)

```yaml
spec:
  project: team-backend              # References the AppProject
  destination:
    namespace: argocd-sc-10-be       # Matches project's allowed destination
```

This works — the application references `team-backend` project, deploys to the allowed namespace.

### app-frontend.yaml (correct project)

```yaml
spec:
  project: team-frontend
  destination:
    namespace: argocd-sc-10-fe       # Matches project's allowed destination
```

This works — frontend project, frontend namespace.

### app-frontend-wrong-ns.yaml (RBAC violation demo)

```yaml
spec:
  project: team-frontend
  destination:
    namespace: argocd-sc-10-be       # ← Backend's namespace! VIOLATION!
```

This intentionally violates the project restrictions. `team-frontend` project only allows deploying to `argocd-sc-10-fe`. Trying to deploy to `argocd-sc-10-be` triggers an ArgoCD error:

```
ComparisonError: application destination {https://kubernetes.default.svc argocd-sc-10-be}
is not permitted in project 'team-frontend'
```

This demonstrates that AppProjects actually enforce the restrictions — it's not just advisory.

---

## The Workload Manifests

### Backend Deployment

```yaml
metadata:
  labels:
    team: backend
containers:
  - image: httpd:2.4-alpine
```

Uses Apache httpd (instead of nginx) to differentiate backend from frontend visually. Labels `team: backend` for organization.

### Frontend Deployment

```yaml
metadata:
  labels:
    team: frontend
containers:
  - image: nginx:1.21-alpine
```

Standard nginx. Labels `team: frontend`. Both teams can have `app: backend-app` / `app: frontend-app` in their own namespaces without conflict.

---

## AppProject RBAC Summary

| Restriction | Field | What It Controls |
|------------|-------|-----------------|
| Source repos | `sourceRepos` | Which Git repos Applications can use |
| Target namespaces | `destinations[].namespace` | Where apps can deploy |
| Target clusters | `destinations[].server` | Which clusters apps can use |
| Cluster resources | `clusterResourceWhitelist` | Cluster-scoped resource types allowed |
| Namespace resources | `namespaceResourceWhitelist` | Namespace-scoped resource types allowed |

---

## Key Takeaways

- **AppProject** is ArgoCD's primary multi-tenancy boundary — essential for shared clusters
- `sourceRepos` whitelists trusted Git repositories — prevents using untrusted manifests
- `destinations` restricts which namespaces and clusters apps can deploy to
- `clusterResourceWhitelist` controls powerful cluster-scoped resources (should be minimal)
- `namespaceResourceWhitelist` controls what resource types teams can create
- The `default` project (used in all previous scenarios) has no restrictions — not for production
- Violations are actively rejected with a `ComparisonError` — the enforcement is real, not advisory
- Create one AppProject per team or application domain for proper isolation
