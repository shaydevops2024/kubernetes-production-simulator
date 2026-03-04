# Project 07 — Serverless Functions Platform: Explained

---

## 1. The App

You are building your **own Functions-as-a-Service (FaaS) platform** — the same concept behind AWS Lambda and Google Cloud Functions, but running on your local Kubernetes cluster. You'll deploy OpenFaaS, configure auto-scaling (including scale-to-zero), and manage everything with ArgoCD.

```
Browser
  └─▶ NGINX Ingress
        ├─▶ /api/*  →  function-service (registry + router)
        │                  └─▶ POST /run/{name} → function-runner
        │                            ├─▶ hello-world      (instant)
        │                            ├─▶ fibonacci        (CPU-heavy, triggers HPA)
        │                            ├─▶ text-processor   (string operations)
        │                            ├─▶ image-info       (metadata extraction)
        │                            └─▶ weather-report   (cron-triggered)
        └─▶ /*     →  frontend (nginx)
                         ├── Function marketplace
                         ├── Live invocation dashboard
                         ├── Scaling demo (fibonacci → watch pods appear)
                         └── Cron scheduler UI
```

| Component | What it does |
|-----------|-------------|
| **function-service** | Registry and router — lists available functions, routes invocation requests, tracks stats |
| **function-runner** | Function executor — contains all function implementations, runs them on-demand |
| **frontend** | Dashboard UI — marketplace to discover functions, invoke them, watch scaling |
| **OpenFaaS** | Production FaaS platform (K8s phase) — manages function lifecycle at scale |
| **KEDA** | Kubernetes Event-Driven Autoscaler — scales function pods to zero when idle, up on demand |

**Scale-to-zero concept:** When no requests come in for ~60 seconds, KEDA scales the function pod to 0. The next request experiences a "cold start" (1-3 seconds) while the pod spins up. You'll observe this directly in the UI.

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-07-serverless-platform/local/

docker compose up --build
```

Once running:

| UI | URL |
|----|-----|
| Function Dashboard | http://localhost:8080 |
| Function Service API | http://localhost:8001/docs |

**Browse and invoke functions:**
1. Open http://localhost:8080 — you'll see the function marketplace
2. Click "Invoke" on any function to run it
3. The `fibonacci` function is CPU-intensive — use it to demonstrate auto-scaling
4. Watch the "Active Invocations" counter as functions run

**Invoke functions via API:**
```bash
# List all available functions
curl http://localhost:8001/functions

# Invoke hello-world
curl -X POST http://localhost:8001/run/hello-world \
  -H "Content-Type: application/json" \
  -d '{"name": "DevOps Engineer"}'

# Invoke fibonacci (CPU-intensive)
curl -X POST http://localhost:8001/run/fibonacci \
  -H "Content-Type: application/json" \
  -d '{"n": 35}'

# Process text
curl -X POST http://localhost:8001/run/text-processor \
  -H "Content-Type: application/json" \
  -d '{"text": "hello world", "operation": "uppercase"}'
```

**Cron trigger simulation:**
```bash
# Trigger the weather-report function as if it were cron-triggered
curl -X POST http://localhost:8001/run/weather-report \
  -H "Content-Type: application/json" \
  -d '{"city": "Tel Aviv"}'

# Check function invocation history
curl http://localhost:8001/stats
```

### Phase 2 — Deploy to Kubernetes

```bash
cd hands-on-projects/project-07-serverless-platform/main/

# Core deployment (namespace, ConfigMaps, Deployments, Services, Ingress)
kubectl apply -f solution/namespace.yaml
kubectl apply -f solution/configmaps/
kubectl apply -f solution/deployments/
kubectl apply -f solution/services/
kubectl apply -f solution/ingress/

# HPA for CPU-based auto-scaling
kubectl apply -f solution/hpa/

# Install OpenFaaS
helm install openfaas openfaas/openfaas -n openfaas --create-namespace \
  -f solution/openfaas/values.yaml

# Install KEDA for scale-to-zero
helm install keda kedacore/keda -n keda --create-namespace

# Apply KEDA ScaledObjects for each function
kubectl apply -f solution/keda/

# Configure ArgoCD for GitOps management
kubectl apply -f solution/argocd/
```

---

## 3. How to Test It

### Function Invocation Tests

```bash
# Test all functions sequentially
for fn in hello-world fibonacci text-processor image-info; do
  echo "Testing $fn..."
  curl -s -X POST http://localhost:8001/run/$fn \
    -H "Content-Type: application/json" \
    -d '{"test": true}' | jq .status
done
```

### Auto-Scaling (HPA) Test

```bash
# In Kubernetes: generate CPU load with fibonacci
for i in {1..20}; do
  curl -X POST http://localhost/run/fibonacci \
    -H "Content-Type: application/json" \
    -d '{"n": 40}' &
done

# Watch pods scale up
watch kubectl get pods -n serverless -l app=function-runner
# Should see replicas increase from 1 → 2 → 3+ based on CPU

# Check HPA status
kubectl get hpa -n serverless
# TARGETS column shows current CPU vs threshold
```

### Scale-to-Zero (KEDA) Test

```bash
# Stop sending requests for 60 seconds
# Watch function-runner scale down to 0
watch kubectl get pods -n serverless

# Then make a request and observe cold start
time curl -X POST http://localhost/run/hello-world \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}'
# First request after scale-to-zero will take 2-5s (cold start)
# Subsequent requests: ~50ms (pod is warm)
```

### Cron Trigger Test (K8s)

```bash
# Check KEDA CronJob ScaledObject
kubectl get scaledobject -n serverless

# Manually trigger to verify function works
kubectl create job --from=cronjob/weather-report weather-test -n serverless
kubectl logs job/weather-test -n serverless
```

### OpenFaaS Deployment Test

```bash
# Check OpenFaaS gateway
kubectl get pods -n openfaas

# Deploy a function via faas-cli
faas-cli deploy --image ghcr.io/openfaas/hello --name hello-fn \
  --gateway http://localhost:8080

# Invoke via OpenFaaS
curl http://localhost:8080/function/hello-fn -d "world"
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Docker / Docker Compose** | Local development | Runs function-service, function-runner, frontend |
| **OpenFaaS** | Production FaaS platform | Manages function deployment, auto-scaling, monitoring in K8s |
| **KEDA** | Event-driven autoscaler | Scales pods to zero on idle, scales up on HTTP requests or queue depth |
| **HPA (Kubernetes)** | CPU-based autoscaler | Scales function-runner based on CPU utilization (Fibonacci demo) |
| **Prometheus** | Metrics source | HPA reads CPU metrics; Alertmanager fires on function error rate |
| **AlertManager** | Alerting | Fires alerts when function error rate exceeds threshold |
| **ArgoCD** | GitOps operator | Manages serverless app manifests; syncs config changes from Git |
| **faas-cli** | OpenFaaS CLI | Deploy, list, invoke, and monitor OpenFaaS functions |
| **Helm** | K8s package manager | Installs OpenFaaS, KEDA, kube-prometheus-stack |

### Key Serverless / Auto-scaling Concepts Practiced

- **Cold start vs warm start**: Scale-to-zero means the first request has latency penalty
- **HPA (CPU/memory)**: Reactive scaling — scales up when utilization exceeds threshold
- **KEDA ScaledObject**: Scales based on external triggers (HTTP concurrency, Kafka lag, cron)
- **Function-as-a-Service pattern**: Stateless, single-purpose functions invoked on demand
- **Cron triggers**: Schedule functions to run at intervals without managing a CronJob manually

---

## 5. Troubleshooting

### Function invocation returning 500

```bash
# Check function-runner logs
docker compose logs function-runner

# Or in K8s:
kubectl logs deploy/function-runner -n serverless -f

# Check if the function name exists
curl http://localhost:8001/functions
```

### HPA not scaling up

```bash
# Check HPA target (must be > threshold to trigger scale)
kubectl describe hpa function-runner-hpa -n serverless

# Check metrics-server is installed (HPA depends on it)
kubectl top pods -n serverless  # If this fails, metrics-server isn't running

# Install metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### KEDA ScaledObject not scaling to zero

```bash
# Check KEDA controller logs
kubectl logs -n keda deploy/keda-operator -f

# Check ScaledObject status
kubectl describe scaledobject function-runner-keda -n serverless

# Verify idle period has passed (default 60s with no traffic)
# Check cooldown/pollingInterval settings
kubectl get scaledobject function-runner-keda -n serverless -o yaml | grep -A5 idleReplicaCount
```

### OpenFaaS function not found

```bash
# List deployed functions
faas-cli list --gateway http://localhost:8080

# Check function pod is running
kubectl get pods -n openfaas-fn

# Check function logs
faas-cli logs hello-fn --gateway http://localhost:8080
```

### Cold start taking too long (KEDA)

```bash
# This is expected behavior — first request after scale-to-zero takes 2-10s
# To reduce cold start:
# 1. Increase minReplicaCount from 0 to 1 (eliminates cold start, costs resources)
kubectl edit scaledobject -n serverless function-runner-keda
# Change spec.minReplicaCount: 0 → 1

# 2. Use readinessProbe tuning (fail-fast if app is unhealthy)
kubectl describe pod -n serverless -l app=function-runner | grep -A10 Readiness
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-07-serverless-platform/local/

docker compose down
docker compose down -v  # Also remove volumes
```

### Kubernetes

```bash
# Delete app namespace
kubectl delete namespace serverless

# Uninstall OpenFaaS
helm uninstall openfaas -n openfaas
kubectl delete namespace openfaas
kubectl delete namespace openfaas-fn

# Uninstall KEDA
helm uninstall keda -n keda
kubectl delete namespace keda

# Remove KEDA CRDs
kubectl delete crd scaledobjects.keda.sh
kubectl delete crd scaledjobs.keda.sh
kubectl delete crd triggerauthentications.keda.sh
```
