# ArgoCD YAML Explanation - Basic Application Deployment

This guide explains the YAML files used in this scenario, covering the ArgoCD Application CR and the Kubernetes manifests it manages.

---

## The ArgoCD Application CR (application.yaml)

The **Application** is the central resource in ArgoCD. It is a Custom Resource (CR) that tells ArgoCD *what* to deploy, *where* to deploy it, and *how* to keep it in sync.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sc01-basic-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/shaydevops2024/kubernetes-production-simulator.git
    targetRevision: HEAD
    path: argocd-scenarios/01-basic-app-deploy/manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd-sc-01
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
```

---

## Field-by-Field Breakdown

### apiVersion: argoproj.io/v1alpha1

This is the API group and version for ArgoCD's Custom Resource Definitions (CRDs). ArgoCD extends Kubernetes with its own resource types. `argoproj.io` is the API group, and `v1alpha1` is the version.

### kind: Application

The resource type. Unlike built-in Kubernetes resources (Deployment, Service), `Application` is defined by ArgoCD. Kubernetes knows about it because ArgoCD installs CRDs during setup.

### metadata.namespace: argocd

**Critical:** The Application CR itself must live in the `argocd` namespace — this is where ArgoCD watches for its own resources. The apps it *deploys* can go anywhere.

### spec.project: default

AppProjects are ArgoCD's way to group and isolate applications. The `default` project is pre-created and allows deploying to any cluster/namespace. In production, you'd create custom projects with restrictions (see Scenario 10).

---

## spec.source — Where is the code?

```yaml
source:
  repoURL: https://github.com/shaydevops2024/kubernetes-production-simulator.git
  targetRevision: HEAD
  path: argocd-scenarios/01-basic-app-deploy/manifests
```

### repoURL

The Git repository ArgoCD polls for changes. ArgoCD fetches this repo and reads the manifests at `path`. You can also use Helm chart repos or OCI registries.

### targetRevision: HEAD

Which Git revision to track:
- `HEAD` — always track the latest commit on the default branch (GitOps continuous delivery)
- `main` or `v1.2.3` — track a specific branch or tag
- A full SHA like `a1b2c3d` — pin to a specific commit (immutable, great for production)

### path

The directory inside the repo containing the Kubernetes manifests. ArgoCD reads all `.yaml`/`.yml` files in this directory and applies them.

---

## spec.destination — Where to deploy?

```yaml
destination:
  server: https://kubernetes.default.svc
  namespace: argocd-sc-01
```

### server: https://kubernetes.default.svc

The Kubernetes API server URL. `kubernetes.default.svc` is the internal DNS name for the local cluster's API server — meaning deploy to the same cluster ArgoCD is running in. For multi-cluster setups, you'd register external cluster URLs.

### namespace: argocd-sc-01

The target namespace for the deployed resources. If the manifests don't specify a namespace, ArgoCD uses this. If `CreateNamespace=true` is set (see below), ArgoCD creates this namespace automatically.

---

## spec.syncPolicy

```yaml
syncPolicy:
  syncOptions:
    - CreateNamespace=true
```

### syncOptions: CreateNamespace=true

By default, ArgoCD fails if the target namespace doesn't exist. This option tells ArgoCD to create the namespace automatically before deploying. Very useful for new environments.

**No `automated:` block** — this means sync is **manual**. ArgoCD detects drift but won't act on it until you click "Sync" in the UI or run `argocd app sync`. This is intentional for Scenario 01 to let you see the "OutOfSync" state before manually triggering sync.

---

## The Deployment (manifests/deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: basic-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: basic-app
  template:
    metadata:
      labels:
        app: basic-app
    spec:
      containers:
        - name: basic-app
          image: nginx:1.21-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              memory: "64Mi"
              cpu: "100m"
            limits:
              memory: "128Mi"
              cpu: "200m"
```

### replicas: 2

Two identical pods run simultaneously. ArgoCD deploys this as-is. If you manually scale to 3 pods in the cluster without changing the Git manifest, ArgoCD detects "drift" — the cluster state no longer matches Git.

### image: nginx:1.21-alpine

Alpine-based nginx image — small footprint (~7MB). In GitOps, image tags in manifests act as the "desired state". To upgrade, you change the tag in Git and commit — ArgoCD then syncs the new image automatically.

### selector.matchLabels and template.labels

These must match. The Deployment uses `matchLabels` to find which pods it owns. A mismatch causes the Deployment to manage zero pods.

### resources.requests vs limits

- **requests**: Minimum guaranteed — used by the scheduler to find a node with enough capacity
- **limits**: Hard ceiling — the container is throttled (CPU) or killed (memory) if exceeded

**100m CPU** = 0.1 of one CPU core. **64Mi** = 64 mebibytes ≈ 67MB.

---

## The Service (manifests/service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: basic-app-service
spec:
  type: ClusterIP
  selector:
    app: basic-app
  ports:
    - port: 80
      targetPort: 80
      protocol: TCP
```

### type: ClusterIP

The default Service type. Creates an internal-only virtual IP that load-balances across matching pods. Not accessible from outside the cluster — use NodePort or LoadBalancer for external access.

### selector: app: basic-app

This links the Service to the Deployment's pods. Traffic to port 80 of the Service is forwarded to port 80 of any pod with label `app: basic-app`.

---

## GitOps Concept: Desired State vs Actual State

ArgoCD continuously compares:
- **Desired State** — what Git says should exist (your manifests)
- **Actual State** — what actually exists in the cluster

| State | Meaning |
|-------|---------|
| `Synced` | Cluster matches Git exactly |
| `OutOfSync` | Difference detected (new commit, or manual cluster change) |
| `Healthy` | All resources are running and ready |
| `Degraded` | Resources exist but are not healthy (pod crash loop, etc.) |

When you apply the Application CR, ArgoCD registers it and immediately detects `OutOfSync` because nothing is deployed yet. After you click "Sync", ArgoCD applies the manifests and the state becomes `Synced + Healthy`.

---

## Key Takeaways

- **Application CR** lives in `argocd` namespace, deployed apps go anywhere
- **source.path** points to your manifests directory in Git
- **destination** is the cluster + namespace to deploy into
- **No `automated:` policy** = manual sync (you control when changes go out)
- **CreateNamespace=true** handles namespace creation automatically
- ArgoCD tracks drift between Git and cluster continuously
