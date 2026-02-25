# Main — Production Kubernetes Deployment

This is where the real DevOps work happens. You'll deploy the FaaS platform to Kubernetes, configure auto-scaling, install OpenFaaS, set up KEDA event-driven scaling, and manage it all with ArgoCD.

This folder starts intentionally empty (except `solution/`) — **you build it**. The guide below tells you exactly what to create and why.

---

## What You're Building

```
main/
├── namespace.yaml
├── configmaps/
│   └── app-config.yaml
├── deployments/
│   ├── function-runner.yaml
│   ├── function-service.yaml
│   └── frontend.yaml
├── services/
│   ├── function-runner.yaml
│   ├── function-service.yaml
│   └── frontend.yaml
├── ingress/
│   └── ingress.yaml
├── hpa/
│   └── function-runner-hpa.yaml
├── keda/
│   └── http-scaledobject.yaml
├── functions/                    ← OpenFaaS Function CRDs
│   ├── hello-world.yaml
│   ├── fibonacci.yaml
│   ├── text-processor.yaml
│   └── weather-report.yaml
└── argocd/
    └── application.yaml
```

The `solution/` folder contains completed versions of all these files — peek there only after you've tried to write them yourself.

---

## Prerequisites

```bash
# Verify your cluster is running
kubectl cluster-info
kubectl get nodes

# Verify Helm is installed
helm version

# Verify NGINX Ingress Controller is installed
kubectl get pods -n ingress-nginx

# Install metrics-server (required for HPA)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

---

## Phase 3A — Core Kubernetes Deployment

### Step 1 — Build and Push Your Images

Before Kubernetes can run your containers, images must be in a registry.

```bash
# Build
docker build -t <your-dockerhub>/function-runner:v1 ../app/function-runner/
docker build -t <your-dockerhub>/function-service:v1 ../app/function-service/
docker build -t <your-dockerhub>/frontend:v1 ../app/frontend/

# Push
docker push <your-dockerhub>/function-runner:v1
docker push <your-dockerhub>/function-service:v1
docker push <your-dockerhub>/frontend:v1

# Or load directly into Kind (no push required)
kind load docker-image <your-dockerhub>/function-runner:v1
kind load docker-image <your-dockerhub>/function-service:v1
kind load docker-image <your-dockerhub>/frontend:v1
```

### Step 2 — Create the Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: faashub
```

```bash
kubectl apply -f namespace.yaml
kubectl get namespace faashub
```

### Step 3 — ConfigMap for Environment Variables

```yaml
# configmaps/app-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: faashub-config
  namespace: faashub
data:
  FUNCTION_RUNNER_URL: "http://function-runner:8002"
```

Notice: `http://function-runner:8002` — not `localhost`. In Kubernetes, the Service name `function-runner` resolves via CoreDNS to `function-runner.faashub.svc.cluster.local`. This is service discovery, exactly like Docker Compose networks.

### Step 4 — Deploy function-runner

```yaml
# deployments/function-runner.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: function-runner
  namespace: faashub
spec:
  replicas: 2
  selector:
    matchLabels:
      app: function-runner
  template:
    metadata:
      labels:
        app: function-runner
    spec:
      containers:
      - name: function-runner
        image: <your-dockerhub>/function-runner:v1
        ports:
        - containerPort: 8002
        readinessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
```

**Why 2 replicas?** High availability. If one pod crashes or a node goes down, the other keeps serving requests. The HPA will increase replicas further under load.

### Step 5 — Deploy function-service and frontend

Repeat the same pattern for `function-service` (port 8001) and `frontend` (port 80).

For `function-service`, add the ConfigMap reference:

```yaml
        envFrom:
        - configMapRef:
            name: faashub-config
```

### Step 6 — Create Services

Every Deployment needs a Service for stable DNS and load balancing:

```yaml
# services/function-runner.yaml
apiVersion: v1
kind: Service
metadata:
  name: function-runner
  namespace: faashub
spec:
  selector:
    app: function-runner
  ports:
  - port: 8002
    targetPort: 8002
  type: ClusterIP
```

Create the same for `function-service` (8001) and `frontend` (80).

**Questions:**
- Why `ClusterIP` and not `NodePort` or `LoadBalancer`?
- What does `selector: app: function-runner` do?
- How does Kubernetes route traffic between the 2 runner replicas?

### Step 7 — Ingress

```yaml
# ingress/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: faashub-ingress
  namespace: faashub
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /api(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: function-service
            port:
              number: 8001
      - path: /(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: frontend
            port:
              number: 80
```

```bash
kubectl apply -f ingress/ingress.yaml

# Get the Ingress IP/port
kubectl get ingress -n faashub

# For Kind, use port-forward instead:
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80
# Then open: http://localhost:8080
```

### Verify Phase 3A

```bash
# All pods running?
kubectl get pods -n faashub

# Any pod crashing?
kubectl describe pod <pod-name> -n faashub

# Test function-service directly
kubectl port-forward -n faashub svc/function-service 8001:8001
curl http://localhost:8001/functions

# Frontend reachable?
kubectl port-forward -n faashub svc/frontend 3000:80
# Open http://localhost:3000
```

---

## Phase 3B — Horizontal Pod Autoscaler (HPA)

HPA watches CPU/memory metrics and adds/removes pods automatically.

```yaml
# hpa/function-runner-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: function-runner-hpa
  namespace: faashub
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: function-runner
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30   # Don't scale up more often than every 30s
    scaleDown:
      stabilizationWindowSeconds: 120  # Wait 2min before scaling down (avoid flapping)
```

```bash
kubectl apply -f hpa/function-runner-hpa.yaml
kubectl get hpa -n faashub -w   # Watch it in real-time

# Trigger the HPA — burst 30 fibonacci requests from the UI Scaling Demo tab
# Then watch:
kubectl get hpa -n faashub -w
kubectl get pods -n faashub -w
```

---

## Phase 3C — Install OpenFaaS (the real FaaS platform)

OpenFaaS turns your Kubernetes cluster into a proper serverless platform with a UI, CLI, and auto-scaling.

```bash
# Install
helm repo add openfaas https://openfaas.github.io/faas-netes/
helm repo update
kubectl apply -f https://raw.githubusercontent.com/openfaas/faas-netes/master/namespaces.yml

# Or use the provided script:
chmod +x solution/helm/install-openfaas.sh
./solution/helm/install-openfaas.sh
```

After installation:
```bash
# Access the UI
kubectl port-forward -n openfaas svc/gateway 8080:8080
# Open http://localhost:8080

# Install faas-cli
curl -sL https://cli.openfaas.com | sudo sh

# Deploy your functions as OpenFaaS Functions
kubectl apply -f functions/hello-world.yaml
kubectl apply -f functions/fibonacci.yaml
kubectl apply -f functions/text-processor.yaml
kubectl apply -f functions/weather-report.yaml

# List deployed functions
faas-cli list --gateway http://localhost:8080

# Invoke via faas-cli
echo '{"name": "OpenFaaS"}' | faas-cli invoke hello-world --gateway http://localhost:8080
```

**What OpenFaaS adds over raw Kubernetes:**
- Automatic scale-to-zero and back
- Built-in Prometheus metrics per function
- Function marketplace
- Event connectors (Kafka, NATS, Cron)
- Simple function packaging with `faas-cli build`

---

## Phase 3D — KEDA Event-Driven Scaling

KEDA extends HPA to support custom scaling triggers — including Kafka and HTTP queue depth.

```bash
# Install KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace

# Install HTTP Add-on (for HTTP-based scale-to-zero)
helm install http-add-on kedacore/keda-add-ons-http --namespace keda

# Apply the ScaledObject
kubectl apply -f keda/http-scaledobject.yaml

# Watch KEDA scaling in action
kubectl get scaledobject -n faashub
kubectl describe scaledobject function-runner-http-scaler -n faashub
```

**KEDA vs HPA:**
| | HPA | KEDA |
|--|-----|------|
| Trigger | CPU / Memory | HTTP, Kafka, Redis, Cron, 50+ sources |
| Scale to zero | No (min: 1) | Yes (min: 0) |
| External metrics | Requires Prometheus adapter | Built-in |
| Cold start | N/A | Yes — when scaling from 0 |

---

## Phase 3E — Cron Trigger

```bash
kubectl apply -f functions/weather-report.yaml   # Includes a CronJob definition

# Watch the CronJob
kubectl get cronjob -n faashub
kubectl get jobs -n faashub -w

# Manually trigger it
kubectl create job weather-manual --from=cronjob/weather-report-cron -n faashub
kubectl logs job/weather-manual -n faashub
```

---

## Phase 3F — GitOps with ArgoCD

Once your manifests are committed to Git, let ArgoCD deploy and reconcile automatically.

```bash
# Install ArgoCD (if not installed)
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to start
kubectl rollout status deploy/argocd-server -n argocd

# Access the UI
kubectl port-forward -n argocd svc/argocd-server 9090:80

# Update argocd/application.yaml with your repo URL, then:
kubectl apply -f argocd/application.yaml

# Watch sync
kubectl get application faashub -n argocd -w
```

Now any commit to your repo automatically deploys to the cluster.

---

## Verification Checklist

- [ ] All pods `Running` in `faashub` namespace
- [ ] `function-service` returns function list via Ingress
- [ ] Frontend dashboard loads at the Ingress URL
- [ ] Can invoke all 5 functions through the UI
- [ ] HPA is created and shows current/desired replicas
- [ ] Bursting fibonacci requests triggers HPA scale-out
- [ ] OpenFaaS UI accessible at port 8080
- [ ] Functions deployed via OpenFaaS and invokable via `faas-cli`
- [ ] `weather-report` CronJob runs on schedule
- [ ] ArgoCD Application shows `Synced` and `Healthy`

---

## Useful Commands

```bash
# Watch all resources in the namespace
kubectl get all -n faashub

# Watch HPA decisions in real time
kubectl get hpa -n faashub -w

# Stream logs from all runner pods
kubectl logs -l app=function-runner -n faashub -f --max-log-requests=10

# Describe a pod (useful for CrashLoopBackOff debugging)
kubectl describe pod <pod-name> -n faashub

# Exec into a pod to test internal networking
kubectl exec -it deploy/function-service -n faashub -- sh
curl http://function-runner:8002/health

# Check events (first place to look when things break)
kubectl get events -n faashub --sort-by=.lastTimestamp

# Force a scale-to-zero (for cold start testing)
kubectl scale deploy/function-runner --replicas=0 -n faashub
# Then invoke a function and measure how long it takes to come back up
```

---

## Tear Down

```bash
kubectl delete namespace faashub
helm uninstall openfaas -n openfaas
helm uninstall keda -n keda
```
