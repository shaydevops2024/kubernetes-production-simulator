# ArgoCD YAML Explanation - App-of-Apps Pattern

This guide explains the App-of-Apps pattern — one of the most powerful ArgoCD patterns for managing multiple applications at scale.

---

## The Problem: Managing Many Applications

In real organizations, you might have dozens or hundreds of applications. Managing each ArgoCD Application CR individually is tedious and error-prone. The **App-of-Apps** pattern solves this by using ArgoCD to manage ArgoCD Applications themselves.

---

## The Parent Application (parent-application.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sc04-parent-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/shaydevops2024/kubernetes-production-simulator.git
    targetRevision: HEAD
    path: argocd-scenarios/04-app-of-apps/children
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### What makes this a "parent"?

Three things:
1. `destination.namespace: argocd` — deploying **into** the argocd namespace
2. `path: .../children` — pointing to a directory containing Application CRs (not app manifests)
3. The files at that path are ArgoCD `Application` resources, not Deployments/Services

When ArgoCD syncs the parent, it deploys Application CRs into the `argocd` namespace. ArgoCD then picks up those new Application CRs and starts managing them. This creates a hierarchy.

### destination.namespace: argocd

This is the key distinction. The parent app deploys **Application resources** into the `argocd` namespace (where ArgoCD manages them), not into application namespaces. The children then deploy their actual workloads wherever they specify.

### automated with prune: true + selfHeal: true

With full auto-sync on the parent:
- Add a new child Application file to Git → parent detects it → creates the Application CR → ArgoCD starts managing the new child automatically
- Remove a child Application file from Git → parent prunes it → the child Application CR is deleted → ArgoCD stops managing that child

This gives you fully declarative management of your entire application portfolio in Git.

---

## Child Application: Frontend (children/frontend-app.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sc04-frontend
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/shaydevops2024/kubernetes-production-simulator.git
    targetRevision: HEAD
    path: argocd-scenarios/04-app-of-apps/manifests/frontend
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd-sc-04
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

This is a standard ArgoCD Application CR — but it's **stored in Git as a YAML file** and managed by the parent. The parent creates this Application, then ArgoCD automatically syncs it (because it has `automated:`).

### path: .../manifests/frontend

Points to the actual frontend Deployment and Service manifests. This child app manages the frontend workload.

---

## Child Application: Backend (children/backend-app.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sc04-backend
  namespace: argocd
spec:
  project: default
  source:
    path: argocd-scenarios/04-app-of-apps/manifests/backend
  destination:
    namespace: argocd-sc-04
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

The backend child is identical in structure to the frontend child, just pointing to a different manifest path. Both deploy to the same namespace (`argocd-sc-04`) in this scenario, but in production they'd often be separate namespaces.

---

## The Full Hierarchy

```
Git Repository
└── children/
    ├── frontend-app.yaml   → Application CR "sc04-frontend"
    └── backend-app.yaml    → Application CR "sc04-backend"

ArgoCD
└── sc04-parent-app (manages children/ in Git)
    ├── sc04-frontend (manages manifests/frontend/)
    └── sc04-backend  (manages manifests/backend/)

Kubernetes Cluster
├── argocd namespace
│   ├── Application: sc04-frontend
│   └── Application: sc04-backend
└── argocd-sc-04 namespace
    ├── Deployment: frontend-app
    ├── Service: frontend-svc
    ├── Deployment: backend-app
    └── Service: backend-svc
```

---

## How the Pattern Works Step by Step

1. **You apply the parent Application** (`parent-application.yaml`) manually once
2. **Parent syncs** — reads the `children/` directory from Git
3. **Parent deploys** the Application CRs (frontend + backend) into the `argocd` namespace
4. **ArgoCD detects** the new Application CRs
5. **Children auto-sync** — each child deploys its own workloads
6. **Future changes**: Commit changes to child manifests → child apps detect and sync

---

## Adding a New Application (The Power of This Pattern)

To add a new microservice `payment-service`:

1. Create `children/payment-app.yaml` (an Application CR pointing to `manifests/payment/`)
2. Create `manifests/payment/deployment.yaml` and `manifests/payment/service.yaml`
3. `git push`
4. ArgoCD parent detects the new `payment-app.yaml` → creates the Application CR
5. New child app auto-syncs → deploys payment service

**No manual ArgoCD operations needed!** Everything is driven by Git commits.

---

## Real-World Uses of App-of-Apps

### Platform Bootstrapping

```
bootstrap-app.yaml (parent)
├── monitoring-app.yaml     → deploys Prometheus, Grafana
├── ingress-app.yaml        → deploys NGINX Ingress Controller
├── cert-manager-app.yaml   → deploys cert-manager
└── teams/
    ├── team-a-apps.yaml    → parent for Team A's apps
    └── team-b-apps.yaml    → parent for Team B's apps
```

### Environment Management

```
production-parent.yaml
├── frontend-prod.yaml     → production frontend
├── backend-prod.yaml      → production backend
└── database-prod.yaml     → production database

staging-parent.yaml
├── frontend-staging.yaml  → staging frontend
└── backend-staging.yaml   → staging backend
```

---

## Key Takeaways

- **App-of-Apps** uses ArgoCD to manage ArgoCD Application CRs themselves
- The **parent app** targets the `argocd` namespace and deploys Application resources
- **Child apps** are regular Application CRs stored as YAML files in Git
- Adding a new child = committing a new Application YAML file to Git
- Removing a child = deleting the file from Git (parent prunes the Application CR)
- This pattern scales to hundreds of applications with zero manual ArgoCD operations
- Essential for **platform teams** who need to manage multiple teams' applications
