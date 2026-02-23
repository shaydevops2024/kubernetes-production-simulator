# Main — Production GitOps CI/CD Pipeline

This is what you build. No manifests are provided — that's the point. You'll create every piece from scratch, guided by the phases below.

By the end you'll have a complete production-grade pipeline where:
- A `git push` triggers a CI pipeline that tests, builds, and scans the image
- ArgoCD detects the manifest change and syncs your cluster automatically
- Flagger promotes the new version progressively (canary) with automated rollback

---

## What You'll Build

```
project-04-gitops-cicd/main/
├── namespace.yaml
├── configmap.yaml
├── deployment.yaml
├── service.yaml
├── ingress.yaml
├── argocd/
│   └── application.yaml        ← ArgoCD Application CRD
├── flagger/
│   └── canary.yaml             ← Flagger Canary CRD
└── .github/
    └── workflows/
        └── ci.yaml             ← GitHub Actions CI pipeline
```

---

## Phase 3A — Core Kubernetes Deployment

Get the app running on your cluster first, without GitOps or canary logic.

### Step 1 — Create the namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: gitops-cicd
  labels:
    istio-injection: enabled   # only if you use Istio for traffic splitting
```

```bash
kubectl apply -f namespace.yaml
kubectl get namespace gitops-cicd
```

### Step 2 — Create a ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: projects-hub-config
  namespace: gitops-cicd
data:
  ENVIRONMENT: production
```

### Step 3 — Create the Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: projects-hub
  namespace: gitops-cicd
spec:
  replicas: 2
  selector:
    matchLabels:
      app: projects-hub
  template:
    metadata:
      labels:
        app: projects-hub
        version: v1        # Flagger uses this label
    spec:
      containers:
        - name: projects-hub
          image: yourregistry/projects-hub:v1   # ← replace with your image
          ports:
            - containerPort: 8080
          envFrom:
            - configMapRef:
                name: projects-hub-config
          env:
            - name: APP_VERSION
              value: "v1"
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "200m"
```

### Step 4 — Create the Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: projects-hub
  namespace: gitops-cicd
spec:
  selector:
    app: projects-hub
  ports:
    - name: http
      port: 80
      targetPort: 8080
```

### Step 5 — Create an Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: projects-hub
  namespace: gitops-cicd
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: projects-hub.local   # add to /etc/hosts for local testing
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: projects-hub
                port:
                  number: 80
```

### Verify 3A

```bash
kubectl get all -n gitops-cicd
kubectl get ingress -n gitops-cicd
curl http://projects-hub.local/health
curl http://projects-hub.local/api/version
```

---

## Phase 3B — ArgoCD GitOps Sync

Install ArgoCD and let Git drive your deployments instead of `kubectl apply`.

### Install ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for pods
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=120s

# Get the initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Port-forward the UI
kubectl port-forward svc/argocd-server -n argocd 8443:443
# Open: https://localhost:8443  (admin / <password above>)
```

### Create an ArgoCD Application

Point ArgoCD at your manifest repo:

```yaml
# argocd/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: projects-hub
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/shaydevops2024/<your-gitops-repo>
    targetRevision: HEAD
    path: manifests/projects-hub     # folder in your gitops repo
  destination:
    server: https://kubernetes.default.svc
    namespace: gitops-cicd
  syncPolicy:
    automated:
      prune: true        # remove resources deleted from Git
      selfHeal: true     # revert manual kubectl changes
    syncOptions:
      - CreateNamespace=true
```

```bash
kubectl apply -f argocd/application.yaml
```

### Test GitOps

1. Change `APP_VERSION` in `configmap.yaml` and push to Git
2. Watch ArgoCD detect the change and sync automatically (takes ~30s by default)
3. Verify the change: `curl http://projects-hub.local/api/version`

**Question:** What happens if you run `kubectl delete deployment projects-hub -n gitops-cicd` while ArgoCD is running with `selfHeal: true`?

---

## Phase 3C — GitHub Actions CI Pipeline

Build the pipeline that tests, builds, scans, and pushes the image — then updates the GitOps repo to trigger ArgoCD.

### Create `.github/workflows/ci.yaml`

```yaml
# .github/workflows/ci.yaml
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/projects-hub

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r app/requirements.txt
          pip install pytest httpx

      - name: Run tests
        run: pytest app/tests/ -v     # you'll write these in Phase 3D

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push image
        uses: docker/build-push-action@v5
        with:
          context: ./app
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          build-args: |
            APP_VERSION=${{ github.sha }}
            BUILD_DATE=${{ github.event.head_commit.timestamp }}
            GIT_COMMIT=${{ github.sha }}

  scan:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - name: Scan image with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: table
          exit-code: '1'           # fail pipeline on HIGH/CRITICAL vulns
          severity: HIGH,CRITICAL

  promote:
    needs: scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout GitOps repo
        uses: actions/checkout@v4
        with:
          repository: shaydevops2024/<your-gitops-repo>
          token: ${{ secrets.GITOPS_TOKEN }}

      - name: Update image tag in manifests
        run: |
          sed -i "s|image: .*projects-hub:.*|image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}|" manifests/projects-hub/deployment.yaml

      - name: Commit and push
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add manifests/
          git commit -m "ci: update projects-hub to ${{ github.sha }}"
          git push
```

### What This Does

```
git push → main
    │
    ▼
[test]   → runs pytest
    │
    ▼
[build-and-push]  → docker build → push to GHCR
    │
    ▼
[scan]   → Trivy scans image → fails if HIGH/CRITICAL CVEs found
    │
    ▼
[promote]  → updates deployment.yaml in gitops repo
    │
    ▼
ArgoCD detects change → syncs cluster → Flagger triggers canary
```

---

## Phase 3D — Progressive Delivery with Flagger

Install Flagger and define a Canary resource. Flagger will manage traffic shifting automatically.

### Install Flagger (with NGINX Ingress provider)

```bash
# Add Flagger Helm repo
helm repo add flagger https://flagger.app
helm repo update

# Install Flagger with NGINX Ingress Controller support
helm upgrade --install flagger flagger/flagger \
  --namespace flagger-system \
  --create-namespace \
  --set meshProvider=nginx \
  --set metricsServer=http://prometheus.monitoring:9090
```

> If you're using Istio, set `--set meshProvider=istio` and install Prometheus via the Istio addons.

### Create the Canary Resource

```yaml
# flagger/canary.yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: projects-hub
  namespace: gitops-cicd
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: projects-hub

  # NGINX Ingress to use for traffic splitting
  ingressRef:
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    name: projects-hub

  progressDeadlineSeconds: 120

  service:
    port: 80
    targetPort: 8080

  analysis:
    # Check every 30s
    interval: 30s
    # Promote after 5 consecutive successful checks
    threshold: 5
    # Max number of failed checks before rollback
    maxWeight: 50
    # Increment traffic by 10% per step
    stepWeight: 10

    metrics:
      # Built-in metric: require >99% success rate
      - name: request-success-rate
        thresholdRange:
          min: 99
        interval: 1m

      # Built-in metric: require <500ms P99 latency
      - name: request-duration
        thresholdRange:
          max: 500
        interval: 1m
```

```bash
kubectl apply -f flagger/canary.yaml
kubectl get canary -n gitops-cicd
```

### Watch a Canary Deployment

```bash
# Watch Flagger's progress in real time
kubectl get canary projects-hub -n gitops-cicd -w

# See what Flagger is doing
kubectl describe canary projects-hub -n gitops-cicd

# Watch events
kubectl get events -n gitops-cicd --field-selector reason=Synced
```

Trigger a canary by updating the image in Git (the CI pipeline does this for you). Flagger will:
1. Create a `projects-hub-canary` deployment with the new image
2. Start shifting traffic: 10% → 20% → 30% → ... → 100%
3. Analyze metrics at each step
4. Promote if healthy, rollback if not

### Trigger a Rollback (Optional Exercise)

Deploy a "broken" v2 that returns errors:

```bash
# Temporarily update the canary to use an image that returns 500s
# (or point it to a non-existent image)
kubectl set image deployment/projects-hub projects-hub=projects-hub:broken -n gitops-cicd

# Watch Flagger detect the failures and roll back
kubectl get canary projects-hub -n gitops-cicd -w
```

---

## Verification Checklist

### 3A — Core K8s
- [ ] `kubectl get pods -n gitops-cicd` shows 2 Running pods
- [ ] `curl http://projects-hub.local/health` returns `{"status":"healthy"}`
- [ ] `curl http://projects-hub.local/api/version` returns `{"version":"v1",...}`
- [ ] Projects Hub UI loads in browser

### 3B — ArgoCD
- [ ] ArgoCD UI shows `projects-hub` application as Synced + Healthy
- [ ] Changing a manifest in Git causes ArgoCD to auto-sync within 3 minutes
- [ ] Manual `kubectl` changes are reverted by ArgoCD (selfHeal)

### 3C — GitHub Actions
- [ ] `git push` to main triggers the CI workflow
- [ ] Tests pass; image is built, tagged, and pushed to registry
- [ ] Trivy scan runs and blocks on HIGH/CRITICAL vulnerabilities
- [ ] GitOps repo gets a new commit updating the image tag
- [ ] ArgoCD picks up the new image and syncs

### 3D — Flagger
- [ ] `kubectl get canary` shows status `Initialized`
- [ ] Updating the image triggers a canary analysis
- [ ] Traffic shifts from 10% → 100% over multiple intervals
- [ ] Refreshing the browser during canary shows v1 (blue) and v2 (green)
- [ ] Rolling out a broken image triggers automatic rollback

---

## Tips

- **GitOps repos:** Keep app code and manifests in separate repos. The CI pipeline writes to the manifests repo; ArgoCD watches it.
- **Image tags:** Always use immutable tags (git SHA, not `latest`). This is what makes GitOps auditable.
- **Flagger analysis:** Start with lenient thresholds (99% success, 1000ms latency) and tighten them as you learn your baseline.
- **Dry-run ArgoCD sync:** `argocd app diff projects-hub` shows what would change before syncing.
- **Manual promotion:** `kubectl annotate canary/projects-hub -n gitops-cicd flagger.app/approved=true` skips the analysis and promotes immediately.
