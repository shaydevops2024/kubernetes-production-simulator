# Main — Production Kubernetes Deployment

Deploy Kong API Gateway and the full GatewayHub stack to a Kubernetes cluster. This phase takes everything you tested locally with Docker Compose and makes it production-ready with CRD-based configuration, StatefulSets, HPA, and GitOps.

---

## What You'll Build

```
Namespace: api-gateway
│
├── Kong Ingress Controller (Helm, LoadBalancer)
│   ├── KongPlugin: jwt-auth
│   ├── KongPlugin: rate-limiting-public     (10 req/min, by IP)
│   ├── KongPlugin: rate-limiting-consumer   (60 req/min, by consumer)
│   ├── KongPlugin: cors
│   ├── KongPlugin: prometheus
│   ├── KongPlugin: request-transformer
│   ├── KongConsumer: demo-user    (free tier, key: demo-user-key)
│   └── KongConsumer: premium-user (premium tier, key: premium-user-key)
│
├── Ingress resources (wired to KongPlugin via annotations)
│   ├── /v1/products  → rate-limiting-public
│   ├── /v1/users, /v1/orders → jwt-auth + rate-limiting-consumer
│   ├── /v2/*  → jwt-auth + rate-limiting-consumer + request-transformer
│   ├── /auth  → (no plugins)
│   └── /analytics → (no plugins)
│
├── api-service       (Deployment, 2 replicas, HPA 2–10)
├── analytics-service (Deployment, 1 replica)
├── frontend          (Deployment, 2 replicas)
│
├── postgres          (StatefulSet, 1 replica, PVC 5Gi)
├── redis             (StatefulSet, 1 replica, PVC 1Gi)
│
└── ArgoCD (separate namespace: argocd)
    └── Application: gatewayhub → watches main/solution/
```

---

## Prerequisites

- `kubectl` connected to a running cluster (Kind, k3s, or cloud)
- Helm 3.x installed
- At least 4 CPU / 6 GB RAM available in the cluster
- (Phase 6 only) ArgoCD installed in the `argocd` namespace

---

## Phase 1: Install Kong Ingress Controller

Kong is installed via the official Helm chart. This deploys the Kong proxy and the Kong Ingress Controller (KIC) — the controller that watches KongPlugin, KongConsumer, and Ingress resources and configures Kong accordingly.

```bash
helm repo add kong https://charts.konghq.com
helm repo update

kubectl create namespace api-gateway

helm install kong kong/ingress \
  -n api-gateway \
  --wait
```

Verify Kong is running:

```bash
kubectl get pods -n api-gateway
# NAME                              READY   STATUS    RESTARTS   AGE
# kong-controller-...               1/1     Running   0          60s
# kong-gateway-...                  1/1     Running   0          60s

kubectl get svc -n api-gateway
# NAME                     TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)
# kong-gateway-proxy       LoadBalancer   10.96.x.x       <pending>     80:30080/TCP,443:30443/TCP
# kong-gateway-admin       ClusterIP      10.96.x.x       <none>        8001/TCP
```

Get the Kong proxy address for testing:

```bash
# On Kind/Minikube (no external IP):
export KONG_PROXY="http://localhost:$(kubectl get svc kong-gateway-proxy -n api-gateway -o jsonpath='{.spec.ports[0].nodePort}')"

# Or use port-forward:
kubectl port-forward -n api-gateway svc/kong-gateway-proxy 8888:80 &
export KONG_PROXY="http://localhost:8888"
```

---

## Phase 2: Deploy Application Services

### Create Secrets and ConfigMaps

```bash
kubectl apply -f solution/namespace.yaml
kubectl apply -f solution/secrets/
kubectl apply -f solution/configmaps/
```

The `secrets/app-secrets.yaml` contains:
- `DATABASE_URL` — PostgreSQL connection string
- `JWT_SECRET` — must match the Kong consumer credential secret (`gateway-demo-secret-key-2024`)

### Deploy Stateful Services

```bash
kubectl apply -f solution/statefulsets/
kubectl apply -f solution/services/postgres.yaml
kubectl apply -f solution/services/redis.yaml
```

Wait for both databases to be ready before deploying the application:

```bash
kubectl rollout status statefulset/postgres -n api-gateway
kubectl rollout status statefulset/redis -n api-gateway
```

Verify persistent volumes were created:

```bash
kubectl get pvc -n api-gateway
# NAME              STATUS   VOLUME   CAPACITY   ACCESS MODES
# postgres-data     Bound    ...      5Gi        RWO
# redis-data        Bound    ...      1Gi        RWO
```

### Deploy Application Services

```bash
kubectl apply -f solution/deployments/
kubectl apply -f solution/services/
```

Verify all pods are running:

```bash
kubectl get pods -n api-gateway
kubectl get deployments -n api-gateway
```

Check api-service logs to confirm database connection and seed data:

```bash
kubectl logs -n api-gateway deploy/api-service
```

You should see the app start without errors. If you see database connection errors, confirm the postgres StatefulSet is fully ready before the api-service pod started. Restart api-service if needed:

```bash
kubectl rollout restart deployment/api-service -n api-gateway
```

---

## Phase 3: Configure Kong Plugins (KongPlugin CRDs)

This is the step that makes Kong aware of your auth and rate limiting policies. Each `KongPlugin` resource is a named, reusable plugin configuration. You wire them to specific Ingress routes using annotations.

```bash
# Apply all plugin definitions
kubectl apply -f solution/kong/plugins/

# Apply consumers and their JWT credentials
kubectl apply -f solution/kong/consumers.yaml
```

Verify they were created and accepted by the Kong Ingress Controller:

```bash
kubectl get kongplugins -n api-gateway
# NAME                       PLUGIN-TYPE           AGE
# cors                       cors                  10s
# jwt-auth                   jwt                   10s
# prometheus                 prometheus             10s
# rate-limiting-consumer     rate-limiting          10s
# rate-limiting-public       rate-limiting          10s
# request-transformer        request-transformer    10s

kubectl get kongconsumers -n api-gateway
# NAME            USERNAME        AGE
# demo-user       demo-user       10s
# premium-user    premium-user    10s
```

Check that consumer JWT credentials were accepted:

```bash
kubectl get secrets -n api-gateway -l konghq.com/credential=jwt
# NAME               TYPE     DATA   AGE
# demo-user-jwt      Opaque   4      10s
# premium-user-jwt   Opaque   4      10s
```

---

## Phase 4: Apply Ingress Resources

Ingress resources define the routing rules and wire KongPlugin resources to specific paths via annotations.

```bash
kubectl apply -f solution/kong/ingress.yaml

# Verify Ingress resources were accepted
kubectl get ingress -n api-gateway
kubectl describe ingress -n api-gateway
```

The Ingress annotations tell Kong which plugins to attach to which routes. Example annotation pattern:

```yaml
metadata:
  annotations:
    konghq.com/plugins: jwt-auth,rate-limiting-consumer
```

Verify routes are visible inside Kong by accessing the Admin API:

```bash
kubectl port-forward -n api-gateway svc/kong-gateway-admin 8001:8001 &

curl -s localhost:8001/routes | jq '[.data[] | {name, paths}]'
curl -s localhost:8001/plugins | jq '[.data[] | {name, enabled}]'
```

---

## Phase 5: HPA and Autoscaling

Apply the HorizontalPodAutoscaler for the api-service:

```bash
kubectl apply -f solution/hpa/

kubectl get hpa -n api-gateway
# NAME              REFERENCE              TARGETS           MINPODS   MAXPODS   REPLICAS
# api-service-hpa   Deployment/api-service  10%/60%, 5%/70%  2         10        2
```

The HPA is configured to scale on:
- CPU utilization target: 60%
- Memory utilization target: 70%
- Min replicas: 2 / Max replicas: 10

To trigger a scale-up, run a load test:

```bash
# Install hey if not present: go install github.com/rakyll/hey@latest
hey -n 5000 -c 50 $KONG_PROXY/v1/products

# Watch HPA react
kubectl get hpa -n api-gateway -w
```

---

## Phase 6: GitOps with ArgoCD

### Install ArgoCD

```bash
kubectl create namespace argocd

kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to be ready
kubectl rollout status deployment/argocd-server -n argocd

# Get the initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d
```

Access the ArgoCD UI:

```bash
kubectl port-forward svc/argocd-server -n argocd 9090:443
# Open: https://localhost:9090
# Username: admin
# Password: (from above)
```

### Create the ArgoCD Application

Update `solution/argocd/application.yaml` with your actual repository URL, then apply it:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: gatewayhub
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_USERNAME/kubernetes-production-simulator
    targetRevision: HEAD
    path: hands-on-projects/project-06-api-gateway/main/solution
  destination:
    server: https://kubernetes.default.svc
    namespace: api-gateway
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

```bash
kubectl apply -f solution/argocd/application.yaml

# Check application status
kubectl get application -n argocd
```

### Simulate a GitOps Policy Change

1. Edit `main/solution/kong/plugins/rate-limiting-public.yaml` — change `minute: 10` to `minute: 20`
2. Commit and push the change
3. Wait for ArgoCD to detect the diff (default sync interval: 3 minutes, or click Sync in the UI)
4. Verify the new policy:

```bash
# Hit the public endpoint more than 10 times in a minute
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\n" $KONG_PROXY/v1/products
done
# Should now return 200 for all 15 requests
```

---

## Testing the Deployment

### 1. Verify the health endpoint

```bash
curl $KONG_PROXY/health
# {"status":"healthy","service":"api-service","version":"1.0.0","uptime_seconds":...}
```

### 2. Test the public endpoint

```bash
curl $KONG_PROXY/v1/products | jq 'length'
# 12
```

### 3. Obtain a JWT token

```bash
TOKEN=$(curl -s -X POST $KONG_PROXY/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice"}' | jq -r '.access_token')

echo "Token: ${TOKEN:0:40}..."
```

### 4. Test a protected endpoint

```bash
curl -H "Authorization: Bearer $TOKEN" $KONG_PROXY/v1/users/me | jq .
```

### 5. Trigger the rate limit on the public endpoint

```bash
for i in {1..12}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" $KONG_PROXY/v1/products)
  echo "Request $i: $STATUS"
done
# Requests 11 and 12 should return 429
```

### 6. Compare v1 and v2 responses

```bash
# v1 — flat array, basic fields
curl $KONG_PROXY/v1/products/1 | jq .

# v2 — enhanced with metadata, stock, rating (JWT required)
curl -H "Authorization: Bearer $TOKEN" $KONG_PROXY/v2/products | jq '.data[0]'
```

### 7. Verify request-transformer headers on v2

```bash
curl -v -H "Authorization: Bearer $TOKEN" $KONG_PROXY/v2/products 2>&1 | grep -i "x-api-version\|x-enhanced"
# < X-API-Version: 2.0
# < X-Enhanced-Response: true
```

### 8. Check rate limit headers

```bash
curl -v $KONG_PROXY/v1/products 2>&1 | grep -i ratelimit
# < X-RateLimit-Limit-Minute: 10
# < X-RateLimit-Remaining-Minute: 9
```

---

## Exploring Kong Admin API

The Kong Admin API is exposed as a ClusterIP service. Port-forward it to explore Kong's running state:

```bash
kubectl port-forward -n api-gateway svc/kong-gateway-admin 8001:8001 &

# Registered services (upstream backends)
curl -s localhost:8001/services | jq '[.data[] | {name, host, port}]'

# Registered routes
curl -s localhost:8001/routes | jq '[.data[] | {name, paths, methods}]'

# All active plugins
curl -s localhost:8001/plugins | jq '[.data[] | {name, enabled, route: .route.id}]'

# Consumers and their credentials
curl -s localhost:8001/consumers | jq '[.data[] | .username]'
curl -s localhost:8001/consumers/demo-user/jwt | jq .

# Kong node status (connection stats)
curl -s localhost:8001/status | jq '.server'
```

---

## Monitoring with Prometheus

Kong's Prometheus plugin is enabled globally. It exposes metrics at `/metrics` on the Kong proxy (or the Admin API depending on your Kong version and config).

Access Kong metrics:

```bash
curl $KONG_PROXY/metrics
# or
curl localhost:8001/metrics
```

**Useful PromQL queries:**

```
# Total HTTP requests through Kong by route
sum by (route) (kong_http_requests_total)

# Request rate per second
rate(kong_http_requests_total[1m])

# HTTP 429 (rate limit) hits
sum(kong_http_requests_total{code="429"}) by (route)

# HTTP 401 (auth failure) hits
sum(kong_http_requests_total{code="401"}) by (route)

# Upstream latency P99 (time Kong waited for the backend)
histogram_quantile(0.99, rate(kong_upstream_latency_ms_bucket[5m]))

# Kong proxy latency P99 (time Kong added before forwarding)
histogram_quantile(0.99, rate(kong_request_latency_ms_bucket[5m]))

# Active connections to Kong
kong_nginx_connections_total{state="active"}
```

If you have Prometheus installed in the cluster (e.g., from Project 05), add a ServiceMonitor targeting Kong's metrics endpoint:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: kong-metrics
  namespace: api-gateway
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: gateway
  endpoints:
    - port: admin
      path: /metrics
      interval: 30s
```

---

## Solution Reference Layout

```
main/solution/
├── namespace.yaml
├── configmaps/
│   └── app-config.yaml          ← KONG_ADMIN_URL, API_SERVICE_URL env vars
├── secrets/
│   └── app-secrets.yaml         ← DATABASE_URL, JWT_SECRET
├── deployments/
│   ├── api-service.yaml         ← 2 replicas, resource limits, env from Secret
│   ├── analytics-service.yaml   ← 1 replica, env from ConfigMap
│   └── frontend.yaml            ← 2 replicas, nginx
├── services/
│   ├── api-service.yaml         ← ClusterIP :8001
│   ├── analytics-service.yaml   ← ClusterIP :8002
│   ├── frontend.yaml            ← ClusterIP :80
│   ├── postgres.yaml            ← ClusterIP :5432
│   └── redis.yaml               ← ClusterIP :6379
├── statefulsets/
│   ├── postgres.yaml            ← 1 replica, 5Gi PVC
│   └── redis.yaml               ← 1 replica, 1Gi PVC
├── hpa/
│   └── api-service-hpa.yaml     ← minReplicas: 2, maxReplicas: 10
└── kong/
    ├── consumers.yaml           ← KongConsumer + JWT credential Secrets
    └── plugins/
        ├── cors.yaml            ← Global CORS headers
        ├── jwt.yaml             ← JWT validation (key_claim_name: iss)
        ├── prometheus.yaml      ← Metrics export
        ├── rate-limiting-public.yaml    ← 10 req/min, by IP
        ├── rate-limiting-consumer.yaml  ← 60 req/min, by consumer
        └── request-transformer.yaml     ← Injects X-API-Version on v2
```

---

## Your Challenges

Work through these after completing the guided phases. They require independent research.

1. **Add IP restriction to the analytics endpoint** — The analytics service is currently wide open. Apply the Kong IP Restriction plugin to only allow requests from within the cluster (or from a specific CIDR).

2. **Implement response caching** — The `/v1/products` endpoint returns the same data for every unauthenticated request. Apply the Kong Proxy Cache plugin to cache responses for 60 seconds. Measure the reduction in requests hitting the api-service.

3. **Canary routing for v2** — Set up a new deployment `api-service-v2-beta` and use the Kong Traffic Splitting plugin to send 10% of `/v2/products` traffic to the beta deployment. Monitor error rates on both versions.

4. **Consumer-differentiated rate limits** — Currently both `demo-user` and `premium-user` share the same rate limit policy. Create separate KongPlugin resources for free and premium tiers, and use consumer group annotations or separate Ingress resources to enforce different limits per consumer.

5. **Add a Prometheus alert for high 429 rate** — Write a PrometheusRule that fires an alert when more than 5% of requests through Kong return 429 over a 5-minute window. Connect AlertManager to a Slack webhook.

6. **mTLS between Kong and the api-service** — Enable Kong's HTTPS upstream mode and configure mutual TLS between Kong and the api-service backend. Create the certificates as Kubernetes Secrets and reference them in your Ingress or KongPlugin configuration.

---

## Checklist

- [ ] Kong Ingress Controller running: `kubectl get pods -n api-gateway -l app=kong`
- [ ] PostgreSQL StatefulSet ready: `kubectl rollout status statefulset/postgres -n api-gateway`
- [ ] Redis StatefulSet ready: `kubectl rollout status statefulset/redis -n api-gateway`
- [ ] api-service healthy: `curl $KONG_PROXY/health`
- [ ] Public products endpoint works: `curl $KONG_PROXY/v1/products`
- [ ] Rate limit enforced on public endpoint (429 after 10 req/min)
- [ ] JWT login works: POST to `/auth/login` returns a token
- [ ] Protected endpoint requires JWT (401 without token)
- [ ] Protected endpoint works with valid JWT
- [ ] v2 response includes `X-API-Version: 2.0` header
- [ ] v2 response body includes `stock`, `rating`, `metadata` fields
- [ ] KongConsumers visible: `kubectl get kongconsumers -n api-gateway`
- [ ] KongPlugins visible: `kubectl get kongplugins -n api-gateway`
- [ ] Analytics stats return data: `curl $KONG_PROXY/analytics/stats`
- [ ] HPA created: `kubectl get hpa -n api-gateway`
- [ ] (Phase 6) ArgoCD Application in Synced state
