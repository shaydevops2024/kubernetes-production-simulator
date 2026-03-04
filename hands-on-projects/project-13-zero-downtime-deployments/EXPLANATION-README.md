# Project 13 — Zero-Downtime Deployments: Explained

---

## 1. The App

You are deploying a **release management platform** and building a system that can deploy new versions of it using three different strategies — with the standout feature being **automated Prometheus-driven rollback**: if your canary's error rate exceeds 5% for 60 seconds, the system rolls back without you touching anything.

```
                Users
                  │
            [NGINX Ingress]
                  │
      ┌───────────┼───────────┐
      │ strategy  │ canary    │
      ▼           ▼           ▼
  [Stable]    [Canary]    [Blue]
   v1 pods     v2 pods     pods
                  │
          [Prometheus]
          Watches: error rate, latency
                  │
          [Argo Rollouts]
          ├── If metrics OK → advance canary %
          └── If metrics fail → rollback to stable
```

The application — **ReleaseManager** (FastAPI + React-style dashboard) — tracks deployment events and shows which version/color is active. Each version can be configured to inject artificial errors (to test rollback).

| Deployment Strategy | Risk | Rollback speed | Resource overhead | Best for |
|--------------------|------|----------------|-------------------|----------|
| **Rolling** | Medium | Slow | Minimal | Stateless apps, low-risk changes |
| **Blue-Green** | Low | Instant | 2× during deploy | High-stakes releases |
| **Canary** | Very low | Fast | Small extra pods | Data-sensitive or risky changes |

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-13-zero-downtime-deployments/local/

docker compose up --build
```

| UI | URL |
|----|-----|
| ReleaseManager App | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |

**Simulate canary deployment locally:**
```bash
# Locally, nginx splits traffic by weight
# To simulate 10% canary:
# Edit local/nginx/nginx.conf — upstream weighted routing:
#   server app-v1:8000 weight=9;
#   server app-v2:8000 weight=1;

# Reload nginx to apply
docker compose exec nginx nginx -s reload

# Watch traffic split
for i in {1..20}; do
  curl -s http://localhost:8080/api/version | jq .version
done
# ~90% will show "v1", ~10% "v2"
```

### Phase 2 — Deploy to Kubernetes (Argo Rollouts)

```bash
cd hands-on-projects/project-13-zero-downtime-deployments/main/

# Install Argo Rollouts
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts \
  -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Install the Argo Rollouts kubectl plugin
curl -LO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x kubectl-argo-rollouts-linux-amd64 && mv it /usr/local/bin/kubectl-argo-rollouts

# Install kube-prometheus-stack (Prometheus + Grafana)
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f solution/helm/kube-prometheus-stack-values.yaml

# Deploy the app as a Rollout (not a Deployment)
kubectl apply -f solution/k8s/namespace/
kubectl apply -f solution/k8s/app/
kubectl apply -f solution/k8s/monitoring/   # ServiceMonitor, AnalysisTemplate
```

**Trigger a canary rollout:**
```bash
# Update the image to v2 — this starts the canary
kubectl set image rollout/releasemanager \
  releasemanager=releasemanager:v2 -n zero-downtime

# Watch the rollout progress
kubectl argo rollouts get rollout releasemanager -n zero-downtime --watch
```

---

## 3. How to Test It

### Rolling Update Test

```bash
# The simplest strategy — Kubernetes default
kubectl set image deployment/releasemanager \
  releasemanager=releasemanager:v2 -n zero-downtime

# Watch pods rolling over
kubectl rollout status deployment/releasemanager -n zero-downtime

# Watch no requests fail during the update
watch curl -s http://localhost/api/health
```

### Blue-Green Switchover Test (Argo Rollouts)

```bash
# Start a blue-green rollout
kubectl argo rollouts set image releasemanager-bg \
  releasemanager=releasemanager:v2 -n zero-downtime

# Argo deploys v2 (green) alongside v1 (blue) — no traffic yet
kubectl argo rollouts get rollout releasemanager-bg -n zero-downtime
# Status: Paused (waiting for manual promotion)

# Preview green directly (bypasses main service)
kubectl port-forward svc/releasemanager-bg-preview 8888:80 -n zero-downtime

# After verifying green:
kubectl argo rollouts promote releasemanager-bg -n zero-downtime
# Traffic instantly switches to green, blue stays for rollback window
```

### Canary with Auto-Rollback Test

```bash
# Start canary deployment
kubectl argo rollouts set image releasemanager \
  releasemanager=releasemanager:v2-buggy -n zero-downtime

# Watch canary progress
kubectl argo rollouts get rollout releasemanager -n zero-downtime --watch

# Canary steps:
# → 10% canary (waits for AnalysisRun)
# → Prometheus checks: error_rate < 5% for 60s
# → If OK: 30% canary
# → If OK: 50% canary
# → If OK: 100% (canary becomes stable)

# To test auto-rollback: use the buggy image
# The v2-buggy image returns 500 errors 50% of the time
# Prometheus detects error rate > 5% → Flagger/Argo rolls back automatically

# Check AnalysisRun status
kubectl get analysisrun -n zero-downtime
kubectl describe analysisrun -n zero-downtime <name>
```

### Verify Prometheus Metrics Drive Rollback

```bash
# After deploying v2-buggy:
# Check Prometheus sees elevated error rate
curl 'http://localhost:9090/api/v1/query?query=rate(http_requests_total{status=~"5.."}[1m])'

# Watch the AnalysisRun make decisions
kubectl get analysisrun -n zero-downtime --watch

# Check Argo Rollouts events
kubectl describe rollout releasemanager -n zero-downtime | grep -A20 Events

# Should see:
# - AnalysisRun started
# - Metric check failed (error rate too high)
# - Rollback initiated
# - Rollback complete → back to v1
```

### Manual Rollback

```bash
# Argo Rollouts manual abort and rollback
kubectl argo rollouts abort releasemanager -n zero-downtime
kubectl argo rollouts undo releasemanager -n zero-downtime
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Argo Rollouts** | Progressive delivery controller | Replaces Kubernetes Deployment — manages canary, blue-green strategies with traffic weighting |
| **AnalysisTemplate** | Rollout evaluation rules | Defines what metrics to check and at what thresholds (e.g., error rate < 5%) |
| **Prometheus** | Metrics source for Argo | AnalysisRun queries Prometheus; if thresholds exceeded → rollback triggered |
| **Grafana** | Visualization | Rollout dashboards — canary traffic %, error rates, latency per version |
| **NGINX Ingress** | Traffic splitting | Weighted routing between stable and canary pods (via annotations) |
| **kube-prometheus-stack** | Full monitoring stack | Prometheus + Grafana + AlertManager installed via Helm |
| **GitHub Actions** | CI/CD pipeline | Build image → push → update image tag in K8s manifests → triggers rollout |
| **kubectl-argo-rollouts** | Plugin for rollout management | `kubectl argo rollouts get`, `promote`, `abort`, `undo` |

### Key Zero-Downtime Deployment Concepts Practiced

- **Canary analysis**: Small percentage of real traffic tests the new version before full rollout
- **AnalysisTemplate**: Declarative metric checks — you define the success criteria, Argo enforces them
- **Automated rollback**: No human needed — Prometheus metrics trigger rollback automatically
- **Blue-green preview**: Test green internally before any user traffic reaches it
- **PodDisruptionBudget**: Ensures rolling update never takes down all pods simultaneously

---

## 5. Troubleshooting

### Argo Rollouts controller not running

```bash
# Check controller is up
kubectl get pods -n argo-rollouts

# Check controller logs
kubectl logs -n argo-rollouts deploy/argo-rollouts -f

# Common fix: missing RBAC
kubectl get clusterrole argo-rollouts
```

### Canary stuck at 0% forever (AnalysisRun always fails)

```bash
# Check AnalysisRun error
kubectl describe analysisrun -n zero-downtime

# Common cause 1: Prometheus not reachable from Argo Rollouts
# Check Prometheus service URL in AnalysisTemplate
kubectl get analysistemplate -n zero-downtime -o yaml | grep prometheusAddress

# Common cause 2: Metric doesn't exist yet (no traffic)
# Send some traffic first, then trigger rollout
for i in {1..30}; do curl http://localhost/; done

# Common cause 3: Incorrect PromQL query
# Test the query in Prometheus UI first
```

### Blue-green promotion not switching traffic

```bash
# Check if rollout is actually in Paused state
kubectl argo rollouts get rollout releasemanager-bg -n zero-downtime
# Should show: Status: Paused (BlueGreen)

# Check service selector
kubectl get svc releasemanager-bg -n zero-downtime -o yaml | grep -A5 selector

# Force promote
kubectl argo rollouts promote releasemanager-bg -n zero-downtime --full
```

### Automatic rollback triggered even for healthy deployment

```bash
# Check which metric triggered the rollback
kubectl describe analysisrun -n zero-downtime | grep -A10 "Message"

# Check the actual metric value vs threshold
# Example: AnalysisTemplate checks error rate, but the query window is too short
# Adjust the interval or failureLimit in the AnalysisTemplate

# Temporarily test with higher thresholds
kubectl edit analysistemplate rollout-analysis -n zero-downtime
# Increase: failureLimit: 3 (allows 3 failures before rollback)
```

### GitHub Actions not triggering rollout

```bash
# Check Actions workflow ran successfully
# GitHub repo → Actions tab → workflow run

# Verify image was pushed
docker pull <your-registry>/releasemanager:v2

# Check if the image tag was updated in the K8s manifests
git log --oneline -5  # Should show a commit updating the image tag

# Check Argo CD or ArgoRollouts picked up the change
kubectl argo rollouts get rollout releasemanager -n zero-downtime
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-13-zero-downtime-deployments/local/

docker compose down -v
```

### Kubernetes

```bash
# Delete app namespace
kubectl delete namespace zero-downtime

# Uninstall Argo Rollouts
kubectl delete -n argo-rollouts \
  -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
kubectl delete namespace argo-rollouts

# Uninstall monitoring stack
helm uninstall kube-prometheus-stack -n monitoring
kubectl delete namespace monitoring

# Remove Argo Rollouts CRDs
kubectl delete crd rollouts.argoproj.io
kubectl delete crd analysistemplates.argoproj.io
kubectl delete crd analysisruns.argoproj.io
kubectl delete crd experiments.argoproj.io
```
