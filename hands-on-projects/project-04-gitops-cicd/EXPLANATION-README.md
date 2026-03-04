# Project 04 — GitOps CI/CD Pipeline: Explained

---

## 1. The App

You are building a **complete end-to-end GitOps pipeline** and the application you deploy is the **DevOps Projects Hub** — a live dashboard listing all 16 hands-on projects in this series. The app displays its own version number prominently, which makes canary deployments visually obvious: refresh the browser and sometimes you see v1, sometimes v2 as traffic gradually shifts.

```
Developer pushes code
  └─▶ GitHub Actions (CI)
        ├── Run tests
        ├── Build Docker image
        ├── Scan image (Trivy security scan)
        └── Push image + update GitOps repo manifests
              └─▶ ArgoCD (GitOps sync)
                    └── Detects manifest change → applies to cluster
                          └─▶ Flagger (Progressive Delivery)
                                ├── Canary: 10% → 30% → 50% → 100%
                                ├── Validates: error rate < 1%, p99 latency < 500ms
                                └── Auto-rollback if metrics fail
                                      └─▶ DevOps Projects Hub (Live UI)
                                            Users see v1 or v2 based on traffic split
```

| Component | Role |
|-----------|------|
| **GitHub Actions** | CI pipeline — test, build Docker image, security scan, push |
| **ArgoCD** | GitOps operator — watches your Git repo, syncs cluster state to match |
| **Flagger** | Progressive delivery — automates canary rollout and rollback decisions |
| **Istio / NGINX Ingress** | Traffic splitting between canary and stable versions |
| **Prometheus** | Metrics source — Flagger reads error rate and latency to make rollout decisions |
| **DevOps Projects Hub** | The app being deployed — FastAPI backend + static HTML/CSS/JS frontend |

---

## 2. How to Use the App

### Phase 1 — Run the App Locally

```bash
cd hands-on-projects/project-04-gitops-cicd/local/

docker compose up --build
```

| Endpoint | URL |
|----------|-----|
| DevOps Projects Hub UI | http://localhost:8080 |
| API (project list) | http://localhost:8080/api/projects |
| Health check | http://localhost:8080/health |

### Phase 2 — Set Up the GitOps Pipeline

**Prerequisites:**
- GitHub account and repository (fork or create)
- Kind cluster running
- ArgoCD installed in the cluster
- Flagger + Prometheus installed

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Get ArgoCD initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Port-forward ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8888:443

# Log in at https://localhost:8888 (admin / <password above>)
```

**Configure ArgoCD to watch your Git repo:**
```yaml
# argocd-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: projects-hub
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<your-org>/<your-repo>
    targetRevision: HEAD
    path: hands-on-projects/project-04-gitops-cicd/main/solution/k8s
  destination:
    server: https://kubernetes.default.svc
    namespace: projects-hub
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**Trigger a canary deployment:**
1. Change `APP_VERSION` in the app code (e.g., v1 → v2)
2. Push to GitHub → GitHub Actions CI runs
3. CI builds new Docker image, updates image tag in GitOps repo
4. ArgoCD detects the change and syncs
5. Flagger starts the canary: 10% of traffic → v2
6. Watch Prometheus metrics — if healthy, it progresses to 30%, 50%, 100%
7. Refresh http://localhost:8080 — you'll see v1 or v2 depending on traffic split

---

## 3. How to Test It

### Test the App API

```bash
# Get all projects
curl http://localhost:8080/api/projects

# Health check
curl http://localhost:8080/health

# Check version info
curl http://localhost:8080/api/version
```

### Test ArgoCD Sync

```bash
# Check sync status
argocd app get projects-hub

# Force a manual sync
argocd app sync projects-hub

# Watch sync status
argocd app wait projects-hub --sync

# List all managed resources
argocd app resources projects-hub
```

### Test Flagger Canary

```bash
# Check canary status
kubectl get canary -n projects-hub

# Watch canary progression in real-time
kubectl describe canary projects-hub -n projects-hub

# Generate traffic during canary (Flagger needs real traffic to analyze)
watch -n1 'curl -s http://localhost:8080/api/projects | jq .version'

# Check Flagger logs
kubectl logs -n flagger-system deploy/flagger -f
```

### Simulate a Bad Deployment (Force Rollback)

```bash
# Inject errors into the new version (simulated)
kubectl set env deployment/projects-hub-canary \
  ERROR_RATE=0.5 -n projects-hub

# Watch Flagger detect the high error rate and roll back
kubectl describe canary projects-hub -n projects-hub
# Status should show "Progressing" then "Failed" then roll back to stable
```

### Verify GitHub Actions CI

After a push:
1. Go to your GitHub repo → Actions tab
2. Watch the workflow: Test → Build → Scan → Push
3. Check Trivy scan results for vulnerabilities
4. Verify the new image tag appears in the GitOps manifests commit

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **GitHub Actions** | CI pipeline | `.github/workflows/ci.yml` — triggers on push, runs test, build, scan, push |
| **Docker** | Image building | `docker build` in CI, image pushed to Docker Hub or GHCR |
| **Trivy** | Security scanning | Scans the built image for CVEs before push; fails pipeline if critical vulns found |
| **ArgoCD** | GitOps operator | Watches Git repo, auto-syncs K8s cluster to match the manifests in Git |
| **Flagger** | Progressive delivery | Reads Prometheus metrics to decide whether to advance or roll back the canary |
| **Prometheus** | Metrics source | Flagger queries `http_request_duration_seconds` and error rate from Prometheus |
| **Istio / NGINX** | Traffic splitting | Weighted routing between stable and canary pods |
| **Helm** | Package installation | Used to install ArgoCD, Flagger, kube-prometheus-stack |
| **kubectl / argocd CLI** | Operations | Monitor sync status, manually trigger syncs, check canary state |

### Key DevOps Concepts Practiced

- **GitOps**: Git is the single source of truth — no `kubectl apply` by hand in production
- **Declarative configuration**: The desired state lives in Git; ArgoCD enforces it
- **Progressive delivery**: Traffic shifts gradually, with automated metric checks
- **Automated rollback**: Prometheus metrics trigger rollback without human intervention
- **Image promotion**: CI builds → pushes image → updates manifest → ArgoCD applies

---

## 5. Troubleshooting

### ArgoCD shows app as OutOfSync

```bash
# Check what's different between Git and cluster
argocd app diff projects-hub

# Force sync
argocd app sync projects-hub

# If a resource is stuck, hard refresh
argocd app get projects-hub --hard-refresh
```

### Flagger canary stuck at 0% traffic

```bash
# Check if Flagger sees metrics
kubectl describe canary projects-hub -n projects-hub
# Look at "Status.Conditions" for error messages

# Common cause: Prometheus not scraping the app
kubectl get servicemonitor -n projects-hub
curl http://localhost:9090/targets  # Prometheus targets page

# Check Flagger logs for errors
kubectl logs -n flagger-system -l app.kubernetes.io/name=flagger -f
```

### GitHub Actions failing at Docker build

```bash
# Check the Actions log for the exact error
# Common fix: Dockerfile path issue
# Verify Dockerfile exists at the expected path
ls hands-on-projects/project-04-gitops-cicd/app/Dockerfile

# Check DOCKER_USERNAME and DOCKER_TOKEN secrets are set in GitHub repo settings
# Settings → Secrets and variables → Actions
```

### Trivy scan failing pipeline

```bash
# Run Trivy locally to see what it finds
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image <your-image>:<tag>

# Fix: update base image in Dockerfile to a patched version
# Or configure Trivy to ignore specific CVEs if they're non-applicable
```

### ArgoCD can't connect to Git repo

```bash
# Check repository credentials in ArgoCD
argocd repo list

# If using SSH, verify key is added to GitHub
# If using HTTPS, verify token has repo read permissions
argocd repo add https://github.com/org/repo --username <user> --password <token>
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-04-gitops-cicd/local/
docker compose down -v
```

### Kubernetes

```bash
# Delete the application namespace
kubectl delete namespace projects-hub

# Remove ArgoCD application
argocd app delete projects-hub

# Uninstall ArgoCD
kubectl delete namespace argocd

# Uninstall Flagger
helm uninstall flagger -n flagger-system
kubectl delete namespace flagger-system

# Uninstall Prometheus stack (if installed for this project)
helm uninstall kube-prometheus-stack -n monitoring
kubectl delete namespace monitoring
```
