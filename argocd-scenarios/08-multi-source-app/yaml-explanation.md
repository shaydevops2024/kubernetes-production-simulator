# ArgoCD YAML Explanation - Multi-Source Application

This guide explains how ArgoCD's multi-source feature combines manifests from different sources, and how this scenario simulates that pattern with ConfigMaps and volume mounts.

---

## The Multi-Source Concept

In real organizations, infrastructure and application configs often live in separate repositories:
- **App repo**: `github.com/my-company/frontend` — Deployment, Service
- **Config repo**: `github.com/my-company/k8s-configs` — ConfigMaps, Secrets, environment-specific settings

The **multi-source Application** (ArgoCD v2.6+) lets a single Application pull from multiple Git repos or sources. In this scenario, we simulate the concept with a single repo using separate manifest files that represent primary and secondary sources.

---

## The Application CR (application.yaml)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sc08-multi-source
  namespace: argocd
  labels:
    scenario: "08"
    category: multi-source
spec:
  project: default
  source:
    repoURL: https://github.com/YOURUSER/YOURREPO.git
    targetRevision: HEAD
    path: argocd-scenarios/08-multi-source-app/manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd-sc-08
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
```

### metadata.labels

```yaml
labels:
  scenario: "08"
  category: multi-source
```

Labels on the Application CR itself. These aren't applied to deployed resources — they label the Application object in the `argocd` namespace. Useful for:
- `kubectl get applications -n argocd -l category=multi-source`
- Filtering in ArgoCD UI
- Organizational metadata

### Note: YOURUSER/YOURREPO

In a real multi-source scenario, you'd replace this with your own fork of the repo. The key concept here is that the `manifests/` directory contains resources that simulate coming from different sources.

---

## Primary Source: The Deployment (manifests/deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: multi-source-app
  namespace: argocd-sc-08
  labels:
    app: multi-source-app
    source: primary
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: app
          image: nginx:1.21-alpine
          volumeMounts:
            - name: config
              mountPath: /usr/share/nginx/html
      volumes:
        - name: config
          configMap:
            name: multi-source-content
```

### labels.source: primary

This label marks this resource as coming from the "primary" source (the app repository). In a real multi-source setup, different resources come from different repos.

### namespace: argocd-sc-08 in metadata

Notice the namespace is specified directly in the manifest, not just in the Application CR's `destination`. When manifests include their own namespace, ArgoCD uses that. When they don't, it falls back to `destination.namespace`.

### volumes and volumeMounts

```yaml
volumeMounts:
  - name: config
    mountPath: /usr/share/nginx/html
volumes:
  - name: config
    configMap:
      name: multi-source-content
```

This mounts the **ConfigMap** (the "secondary source") as a directory into the pod. Every key in the ConfigMap becomes a file:
- `index.html` key → `/usr/share/nginx/html/index.html` file

This is how ConfigMaps serve as configuration or content for pods. When the ConfigMap changes, Kubernetes automatically updates the mounted files (within ~1 minute).

---

## Secondary Source: The ConfigMap (manifests/configmap.yaml)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: multi-source-content
  namespace: argocd-sc-08
  labels:
    app: multi-source-app
    source: secondary
data:
  index.html: |
    <!DOCTYPE html>
    <html>
    <head><title>Multi-Source App</title></head>
    <body>
      <h1>Multi-Source Application</h1>
      <p>This content comes from a secondary source (ConfigMap).</p>
      <p>The deployment comes from the primary source.</p>
    </body>
    </html>
```

### labels.source: secondary

Marks this as the "secondary source" — in a real setup, this ConfigMap would come from a different Git repository than the Deployment.

### data.index.html

The ConfigMap stores the HTML page content. Key name (`index.html`) becomes the filename when mounted as a volume.

**Multi-line value syntax (`|`):** The `|` block scalar preserves newlines, allowing full HTML content as a YAML value.

**When to use ConfigMaps for content:**
- HTML/CSS/JS assets for static sites
- Configuration files (nginx.conf, app.properties)
- Scripts that containers run at startup
- Feature flags in JSON/YAML format

---

## The Service (manifests/service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: multi-source-service
  namespace: argocd-sc-08
  labels:
    app: multi-source-app
spec:
  selector:
    app: multi-source-app
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
```

Standard ClusterIP service. Notice all three resources (Deployment, ConfigMap, Service) share `labels.app: multi-source-app` — this is the standard Kubernetes labeling convention for grouping related resources.

---

## True Multi-Source (ArgoCD v2.6+)

In ArgoCD v2.6+, you can use `sources:` (plural) instead of `source:`:

```yaml
spec:
  sources:
    - repoURL: https://github.com/my-company/frontend.git
      path: k8s/
      targetRevision: main
    - repoURL: https://github.com/my-company/k8s-configs.git
      path: overlays/prod/
      targetRevision: main
    - repoURL: https://charts.bitnami.com/bitnami
      chart: redis
      targetRevision: "18.0.0"
```

ArgoCD merges all sources and applies them as a single application. Resources from all sources are tracked together and shown in one resource tree.

---

## Volume Mount Deep Dive

Understanding how ConfigMaps become files:

```
ConfigMap data:              Pod filesystem:
  index.html: |          →   /usr/share/nginx/html/
    <html>...</html>              index.html     ← this file
```

**What nginx serves:**
- nginx's default document root is `/usr/share/nginx/html`
- It serves `index.html` when you access `http://pod-ip/`
- By mounting our ConfigMap there, we replace the default nginx page with our custom HTML

**ConfigMap update propagation:**
- ConfigMaps mounted as volumes update automatically (no pod restart needed)
- Takes up to 1 minute for kubelet to sync the new content
- Environment variable-based ConfigMaps require pod restart to update

---

## Key Takeaways

- **Multi-source** concept: different parts of an app can come from different repos/sources
- **`labels.source`** helps identify which source each resource came from
- **ConfigMap volume mounts** let you inject file content from Git-managed config into pods
- **`data` with `|` syntax** stores multi-line content (HTML, config files, scripts) in ConfigMaps
- **`namespace` in manifest metadata** overrides the Application CR's `destination.namespace`
- ArgoCD v2.6+ supports true multi-source with the `sources:` (plural) field
- ConfigMap-mounted files update automatically without pod restarts (within ~1 minute)
