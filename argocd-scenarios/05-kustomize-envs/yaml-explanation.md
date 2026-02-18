# ArgoCD YAML Explanation - Kustomize Environments

This guide explains how Kustomize works with ArgoCD to manage multiple environments (dev and prod) from a single base configuration.

---

## The Problem: Multi-Environment Configuration

You want the same app in dev and prod, but with different settings:
- Dev: 1 replica, small resources
- Prod: 3 replicas, larger resources

Options:
1. **Copy-paste** manifests — duplication, maintenance nightmare
2. **Helm templates** — powerful but complex for simple differences
3. **Kustomize overlays** — simple, native Kubernetes, no templating needed

---

## Kustomize Structure

```
05-kustomize-envs/
├── base/
│   ├── kustomization.yaml    ← lists base resources
│   ├── deployment.yaml       ← base deployment (1 replica, small resources)
│   └── service.yaml          ← base service
└── overlays/
    ├── dev/
    │   └── kustomization.yaml  ← dev customizations (1 replica)
    └── prod/
        └── kustomization.yaml  ← prod customizations (3 replicas, larger resources)
```

---

## Base: The Shared Foundation

### base/kustomization.yaml

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
```

The base `kustomization.yaml` simply lists which files belong to this base. Kustomize reads these files and makes them available for overlays to customize.

**No environment-specific settings here.** The base contains only what's common across all environments.

### base/deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kustomize-app
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: app
          image: nginx:1.21-alpine
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "100m"
```

This is the base configuration — default values that overlays will customize. `replicas: 1` is the base default; each overlay patches it.

---

## Dev Overlay (overlays/dev/kustomization.yaml)

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namePrefix: dev-
commonLabels:
  environment: dev
patches:
  - target:
      kind: Deployment
      name: kustomize-app
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
```

### resources: - ../../base

Points to the base directory (two levels up). Kustomize loads all resources defined in the base kustomization.yaml.

### namePrefix: dev-

Prepends `dev-` to the names of **all resources**. So `kustomize-app` becomes `dev-kustomize-app`, and `kustomize-service` becomes `dev-kustomize-service`.

This is essential when deploying to the same namespace as prod — resource names must be unique. In this scenario, dev and prod use separate namespaces, but namePrefix is still good practice.

### commonLabels: environment: dev

Adds `environment: dev` label to every resource. Useful for:
- `kubectl get all -l environment=dev` — filter dev resources
- Monitoring dashboards segmented by environment
- Network policies targeting specific environments

### patches — JSON Patch

```yaml
patches:
  - target:
      kind: Deployment
      name: kustomize-app
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
```

JSON Patch (RFC 6902) modifies specific fields without touching the rest. Operations:
- `op: replace` — change an existing value
- `op: add` — add a new field
- `op: remove` — delete a field

`path: /spec/replicas` is a JSON Pointer to the field. `value: 1` sets it to 1 replica for dev.

---

## Prod Overlay (overlays/prod/kustomization.yaml)

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namePrefix: prod-
commonLabels:
  environment: production
patches:
  - target:
      kind: Deployment
      name: kustomize-app
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 3
      - op: replace
        path: /spec/template/spec/containers/0/resources/requests/memory
        value: "128Mi"
      - op: replace
        path: /spec/template/spec/containers/0/resources/requests/cpu
        value: "100m"
      - op: replace
        path: /spec/template/spec/containers/0/resources/limits/memory
        value: "256Mi"
      - op: replace
        path: /spec/template/spec/containers/0/resources/limits/cpu
        value: "200m"
```

### Multiple patches in one overlay

Prod applies **4 patches** to the base Deployment:
- 3 replicas (vs 1 in dev) for high availability
- Doubled memory requests/limits (prod handles real traffic)
- Doubled CPU requests/limits (prod needs more compute)

The JSON Pointer `spec/template/spec/containers/0/resources/requests/memory` navigates to the first container's (index `0`) memory request. This is how you patch nested values precisely.

### Result after rendering

| Setting | Base | Dev | Prod |
|---------|------|-----|------|
| Name | `kustomize-app` | `dev-kustomize-app` | `prod-kustomize-app` |
| Replicas | 1 | 1 | 3 |
| CPU request | 50m | 50m | 100m |
| Memory request | 64Mi | 64Mi | 128Mi |
| Label | (none) | `environment: dev` | `environment: production` |

---

## The Two ArgoCD Applications

### application-dev.yaml

```yaml
spec:
  source:
    path: argocd-scenarios/05-kustomize-envs/overlays/dev
  destination:
    namespace: argocd-sc-05-dev
```

ArgoCD points to `overlays/dev/` — ArgoCD automatically detects the `kustomization.yaml` and runs `kustomize build` internally. No special configuration needed.

### application-prod.yaml

```yaml
spec:
  source:
    path: argocd-scenarios/05-kustomize-envs/overlays/prod
  destination:
    namespace: argocd-sc-05-prod
```

Same setup, different overlay path and namespace.

**ArgoCD + Kustomize integration:** When ArgoCD finds a `kustomization.yaml` in the path, it automatically runs Kustomize to render the final manifests. You don't need to pre-render anything.

---

## Why Kustomize Over Copy-Paste

### Copy-paste approach:
```
prod/deployment.yaml   # Full copy with prod settings
dev/deployment.yaml    # Full copy with dev settings
```
Problem: When you update the image, you must update both files. Easy to miss one.

### Kustomize approach:
```
base/deployment.yaml   # Update image here once
overlays/dev/          # Only overrides dev-specific settings
overlays/prod/         # Only overrides prod-specific settings
```
Change the image in `base/deployment.yaml` → both dev and prod get the new image automatically.

---

## Key Takeaways

- **Base** contains common config, **overlays** contain environment-specific differences
- `namePrefix` prevents resource name collisions between environments
- `commonLabels` adds environment labels to all resources automatically
- **JSON Patch** (`op: replace`) modifies specific fields without touching other parts
- ArgoCD auto-detects `kustomization.yaml` and runs Kustomize internally
- Two ArgoCD Applications (dev + prod) point to two different overlay directories
- Update base once → all environments inherit the change
