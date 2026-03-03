# Production Deployment — Kubernetes + Argo Rollouts

You've run the stack locally. Now deploy it to Kubernetes with **real** zero-downtime
strategies powered by Argo Rollouts, Prometheus metrics, and automated rollback.

## Architecture overview

```
                       ┌─────────────────────────────────────────────────┐
                       │                  Kubernetes cluster              │
                       │                                                  │
  User traffic         │  nginx-ingress ──► Argo Rollouts Service         │
  ──────────────────►  │                        │                         │
                       │               ┌────────┴────────┐               │
                       │           stable svc        canary svc          │
                       │               │                  │               │
                       │         v1 pods (blue)    v2 pods (green)       │
                       │                                                  │
                       │  Prometheus ──► AlertManager                    │
                       │       └──────────► AnalysisTemplate             │
                       │                       │                          │
                       │              error rate > 5% → rollback         │
                       └─────────────────────────────────────────────────┘
```

**Key tools:**

| Tool             | Role                                                                |
|------------------|---------------------------------------------------------------------|
| Argo Rollouts    | Orchestrates blue-green and canary deployments                      |
| AnalysisTemplate | Queries Prometheus every 30 s; aborts rollout if error rate > 5 %  |
| Prometheus       | Scrapes app metrics; source of truth for rollback decisions         |
| Grafana          | Visualises traffic split, error rates, latency                      |
| nginx-ingress    | Routes traffic; Argo Rollouts manages the VirtualService weights    |
| MetalLB          | Provides LoadBalancer IPs on bare-metal / Kind clusters             |

---

## Phase 1 — Cluster prerequisites

### 1.1 Create a Kind cluster (skip if you have one)

```bash
cat <<EOF | kind create cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 4545
        protocol: TCP
      - containerPort: 443
        hostPort: 4443
        protocol: TCP
  - role: worker
  - role: worker
EOF
```

### 1.2 Install MetalLB (LoadBalancer on bare-metal)

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.5/config/manifests/metallb-native.yaml
kubectl wait --namespace metallb-system --for=condition=ready pod --selector=app=metallb --timeout=90s

# Apply the IP pool — see solution/k8s/metallb/
kubectl apply -f solution/k8s/metallb/
```

### 1.3 Install nginx-ingress

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s
```

### 1.4 Install Argo Rollouts

```bash
kubectl create namespace argo-rollouts
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm install argo-rollouts argo/argo-rollouts \
  --namespace argo-rollouts \
  --values solution/helm/argo-rollouts-values.yaml

# Install the kubectl plugin
curl -LO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x kubectl-argo-rollouts-linux-amd64
sudo mv kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts
```

### 1.5 Install Prometheus stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring
helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values solution/helm/prometheus-values.yaml
```

---

## Phase 2 — Build and push the app image

```bash
# Build once — version is controlled by env vars at runtime, not build time
docker build -t deploy-insight:latest ./app

# If using Kind, load directly (no registry needed)
kind load docker-image deploy-insight:latest
```

---

## Phase 3 — Deploy the namespace and base resources

```bash
# Create namespace
kubectl apply -f solution/k8s/namespace.yaml

# Deploy Prometheus ServiceMonitor so kube-prometheus scrapes the app
kubectl apply -f solution/k8s/monitoring/

# Deploy the app services
kubectl apply -f solution/k8s/app/
```

---

## Phase 4 — Blue-Green deployment

### What is blue-green?

Two full environments exist simultaneously. Traffic is instantly switched from old (blue)
to new (green). If something goes wrong, you flip back in seconds — no partial rollout,
no gradual traffic shift.

```
Before:  100% → v1 (blue)   v2 (green) [idle, pre-warmed]
After:   100% → v2 (green)  v1 (blue)  [idle, kept for rollback]
```

### Deploy the Blue-Green Rollout

```bash
kubectl apply -f solution/k8s/argo-rollouts/rollout-blue-green.yaml
kubectl apply -f solution/k8s/argo-rollouts/analysis-template.yaml

# Watch the rollout
kubectl argo rollouts get rollout deploy-insight -n zero-downtime -w
```

### Trigger a rollout (upgrade to v2)

```bash
kubectl argo rollouts set image deploy-insight \
  app=deploy-insight:v2 \
  -n zero-downtime

# v2 is now running in the preview environment — traffic still hits v1
kubectl argo rollouts get rollout deploy-insight -n zero-downtime
```

### Promote (send traffic to v2)

```bash
kubectl argo rollouts promote deploy-insight -n zero-downtime
```

### Rollback

```bash
kubectl argo rollouts undo deploy-insight -n zero-downtime
```

---

## Phase 5 — Canary deployment

### What is canary?

Traffic shifts gradually: 5 % → 25 % → 50 % → 100 %. At each step, Argo Rollouts
runs an AnalysisRun that checks Prometheus. If error rate > 5 %, the rollout pauses
and eventually rolls back automatically.

```
Step 1:  95% v1  +  5% v2   → AnalysisRun checks metrics for 1 min
Step 2:  75% v1  + 25% v2   → AnalysisRun checks metrics for 1 min
Step 3:  50% v1  + 50% v2   → AnalysisRun checks metrics for 2 min
Step 4:   0% v1  +100% v2   → promotion complete
```

### Deploy the Canary Rollout

```bash
kubectl apply -f solution/k8s/argo-rollouts/rollout-canary.yaml

# Watch live
kubectl argo rollouts get rollout deploy-insight-canary -n zero-downtime -w
```

### Trigger the canary

```bash
kubectl argo rollouts set image deploy-insight-canary \
  app=deploy-insight:v2 \
  -n zero-downtime
```

### Watch it in Grafana

1. Open Grafana at http://localhost:4446 (port-forward or NodePort — see below)
2. Open the **Zero-Downtime Deployment Monitor** dashboard
3. Watch **Request Rate by Version** shift gradually from v1 to v2

### Trigger automatic rollback

While the canary is at 25 %, inject errors:

```bash
# Hit the /break endpoint on v2 pods
kubectl exec -it deploy/deploy-insight-canary -n zero-downtime -- \
  curl -X POST http://localhost:4545/break
```

Watch in Grafana: error rate climbs above 5 %. After ~60 seconds the AnalysisRun fails
and Argo Rollouts rolls back automatically — no human intervention.

---

## Phase 6 — Access Grafana

```bash
# Port-forward Grafana
kubectl port-forward svc/kube-prometheus-grafana 4446:80 -n monitoring

# Or if you installed with NodePort in prometheus-values.yaml, just open:
# http://localhost:4446
```

Default credentials: `admin / admin` (change in production).

---

## Phase 7 — CI/CD with GitHub Actions

The workflow at `solution/github-actions/workflows/deploy.yml` automates:

1. Build and push Docker image on every push to `main`
2. Update the image tag in the Rollout manifest
3. Apply via `kubectl` (requires a kubeconfig secret in GitHub)

```bash
# Required GitHub repository secrets:
# KUBE_CONFIG    → base64-encoded kubeconfig
# DOCKER_USER    → Docker Hub username
# DOCKER_PASS    → Docker Hub password
```

---

## Phase 8 — Verify everything works

```bash
# Check all pods are running
kubectl get pods -n zero-downtime

# Check rollout status
kubectl argo rollouts list rollouts -n zero-downtime

# Check AnalysisTemplates
kubectl get analysistemplates -n zero-downtime

# Check Prometheus targets (should see app-v1 and app-v2)
kubectl port-forward svc/kube-prometheus-prometheus 4447:9090 -n monitoring
# Open http://localhost:4447/targets
```

---

## Troubleshooting

| Symptom                                    | Fix                                                              |
|--------------------------------------------|------------------------------------------------------------------|
| Pods stuck in `Pending`                    | `kubectl describe pod <name> -n zero-downtime` — check resources |
| AnalysisRun failing immediately            | Check Prometheus is scraping the app: `/targets` in Prometheus UI |
| Rollout stuck at `Paused`                  | Run `kubectl argo rollouts promote` or check analysis logs       |
| `deploy-insight:v2` ImagePullBackOff       | Load image into Kind: `kind load docker-image deploy-insight:v2` |
| Grafana shows no data                      | Confirm ServiceMonitor namespace selector matches app namespace  |

---

## What you built

By completing this project you have:

- Deployed an app using **blue-green** strategy with instant traffic switching
- Deployed an app using **canary** strategy with Prometheus-driven promotion gates
- Configured **automated rollback** — no human needed when error rate exceeds threshold
- Connected **Prometheus** → **Argo Rollouts** for metric-based rollout decisions
- Built a **GitHub Actions** pipeline that triggers rollouts on every merge to main
- Set up **Grafana** dashboards to visualise deployment health in real time

> **Compare with the local setup:** the concept is the same, but in production Argo Rollouts
> replaces your manual nginx weight edits, and Prometheus replaces your eyeballing of the error gauge.
