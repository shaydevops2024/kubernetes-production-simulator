# Project 06 — API Gateway (Kong): Explained

---

## 1. The App

You are deploying **Kong API Gateway** in front of a real REST API. Kong sits between the client and your backend, enforcing authentication, rate limiting, request transformation, and API versioning — without touching a line of backend code.

```
Browser / curl / API client
  └─▶ Kong API Gateway (:8888 local / :80 K8s)
        │
        │ Plugins enforced at the gateway:
        │   - JWT Auth (validates token before passing to backend)
        │   - Rate Limiting (per consumer, Redis-backed)
        │   - Request Transformation (injects custom headers)
        │   - CORS, Prometheus metrics
        │
        ├─▶ /v1/products (public, 10 req/min)     → api-service:8001
        ├─▶ /v1/users /v1/orders (JWT, 30 req/min) → api-service:8001
        ├─▶ /v2/* (JWT, 60 req/min, enhanced)      → api-service:8001
        ├─▶ /auth (no auth, token generation)       → api-service:8001
        └─▶ /analytics (analytics dashboard)        → analytics-service:8002
```

| Service | What it does |
|---------|-------------|
| **api-service** | The actual backend REST API — products, users, orders, auth endpoints |
| **analytics-service** | Reads Kong Admin API and api-service metrics; renders a live analytics dashboard |
| **Kong** | API Gateway — JWT validation, rate limiting, routing, plugin execution |
| **PostgreSQL** | Kong's database (Kong config) + api-service data |
| **Redis** | Rate limiting backend — Kong stores per-consumer counters here |

**Key insight:** Kong uses a declarative config. You define routes, services, plugins, and consumers in YAML/JSON — Kong enforces all of it at the gateway layer without any changes to your backend.

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-06-api-gateway/local/

docker compose up --build
```

Once running:

| UI | URL |
|----|-----|
| API (through Kong) | http://localhost:8888 |
| Kong Admin API | http://localhost:8001 (direct, internal) |
| Analytics Dashboard | http://localhost:8888/analytics |
| API Service (direct) | http://localhost:8002/docs |

**Get a JWT token:**
```bash
# Login to get a JWT token
TOKEN=$(curl -s -X POST http://localhost:8888/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret"}' | jq -r .token)

echo "Token: $TOKEN"
```

**Make authenticated requests:**
```bash
# Public endpoint (no auth required)
curl http://localhost:8888/v1/products

# Protected endpoint (JWT required)
curl http://localhost:8888/v1/users \
  -H "Authorization: Bearer $TOKEN"

# v2 endpoint with enhanced headers
curl http://localhost:8888/v2/products \
  -H "Authorization: Bearer $TOKEN"
# Response includes X-API-Version and X-Enhanced-Response headers
```

**Trigger rate limiting:**
```bash
# Hit the rate limit on a public endpoint (10 req/min)
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8888/v1/products
done
# First 10: 200, then: 429 Too Many Requests
```

### Phase 2 — Deploy to Kubernetes (Kong Ingress Controller)

In Kubernetes, Kong runs as the Ingress Controller. You configure it using CRDs instead of the Admin API:

```bash
cd hands-on-projects/project-06-api-gateway/main/

# Install Kong Ingress Controller
helm install kong kong/ingress -n kong --create-namespace \
  -f solution/helm/kong-values.yaml

# Apply KongPlugin CRDs (JWT, rate-limit, request-transform)
kubectl apply -f solution/plugins/
kubectl apply -f solution/consumers/
kubectl apply -f solution/ingress/
kubectl apply -f solution/app/
```

**Apply a plugin change via ArgoCD (GitOps):**
```bash
# Change rate limit in solution/plugins/rate-limit.yaml
# Commit and push → ArgoCD syncs → Kong applies new limits
# No restart required — Kong picks up config changes live
```

---

## 3. How to Test It

### JWT Authentication Test

```bash
# Without token — should get 401
curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/v1/users
# Expected: 401

# With valid token — should get 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/v1/users \
  -H "Authorization: Bearer $TOKEN"
# Expected: 200

# With invalid token — should get 401
curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/v1/users \
  -H "Authorization: Bearer invalid-token"
# Expected: 401
```

### Rate Limiting Test

```bash
# Rate limit: 30 req/min for authenticated users
for i in {1..35}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    http://localhost:8888/v1/users -H "Authorization: Bearer $TOKEN")
  echo "Request $i: $CODE"
done
# After 30 requests: 429 Too Many Requests
# Response headers: X-RateLimit-Remaining-Minute: 0
```

### Request Transformation Test (v2)

```bash
# v2 routes should have extra headers injected by Kong
curl -v http://localhost:8888/v2/products \
  -H "Authorization: Bearer $TOKEN" 2>&1 | grep -i "X-API\|X-Enhanced"
# Should see: X-API-Version: v2 and X-Enhanced-Response: true
```

### API Versioning Test

```bash
# v1 returns standard format
curl http://localhost:8888/v1/products | jq .

# v2 returns enhanced format (same data, extra metadata)
curl http://localhost:8888/v2/products \
  -H "Authorization: Bearer $TOKEN" | jq .
# Should have more fields / different structure
```

### Analytics Dashboard Test

```bash
# Check analytics dashboard is pulling Kong stats
curl http://localhost:8888/analytics/api/stats | jq .

# Check per-route statistics
curl http://localhost:8888/analytics/api/routes | jq .
```

### Kong Admin API Verification

```bash
# List all configured services
curl http://localhost:8001/services | jq .

# List all routes
curl http://localhost:8001/routes | jq .

# List all plugins and their configs
curl http://localhost:8001/plugins | jq '.data[] | {name: .name, config: .config}'

# List consumers
curl http://localhost:8001/consumers | jq .
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Kong** | API Gateway | Routes requests, enforces plugins (JWT, rate-limit, transform, CORS, Prometheus) |
| **Kong Admin API** | Kong configuration (local) | REST API on :8001 — configure services, routes, plugins, consumers |
| **Kong Ingress Controller** | Kong config (K8s) | Reads KongPlugin, KongConsumer, Ingress CRDs to configure Kong |
| **Redis** | Rate limit storage | Kong stores per-consumer request counters; shared across Kong instances |
| **PostgreSQL** | Kong config persistence | Kong stores its own configuration (services, routes, plugins) in Postgres |
| **JWT (JSON Web Tokens)** | Authentication | Kong validates JWT signature before passing request to backend |
| **ArgoCD** | GitOps for Kong config | Plugin changes committed to Git → ArgoCD syncs → Kong picks up new config |
| **Helm** | K8s installation | Installs Kong Ingress Controller and Redis |
| **Prometheus** | Metrics collection | Kong exposes `/metrics` — tracks requests per route, latency, status codes |

### Key API Gateway Concepts Practiced

- **Gateway pattern**: Backend services unaware of auth/rate-limiting — gateway handles it
- **Consumer-based rate limiting**: Different limits for different API consumers (free vs pro)
- **JWT validation at edge**: Token never reaches the backend if invalid
- **Request transformation**: Kong injects/modifies headers without backend changes
- **API versioning**: `/v1` and `/v2` routes with different plugins applied

---

## 5. Troubleshooting

### Kong won't start (database not ready)

```bash
# Kong depends on PostgreSQL being ready
docker compose logs kong

# Kong runs migrations on start — if DB isn't ready, Kong fails
# Check postgres is healthy
docker compose ps postgres-kong

# Restart Kong after DB is ready
docker compose restart kong
```

### 401 on routes that should be public

```bash
# Check route configuration
curl http://localhost:8001/routes | jq '.data[] | {name: .name, paths: .paths}'

# Check which plugins are applied to which routes
curl http://localhost:8001/routes/<route-id>/plugins

# The public /v1/products route should NOT have the jwt plugin
```

### Rate limit not working (429 never returned)

```bash
# Verify the rate-limit plugin is configured correctly
curl http://localhost:8001/plugins | jq '.data[] | select(.name=="rate-limiting")'

# Check Redis is running (Kong uses Redis for distributed rate limiting)
docker compose ps redis

# Test Redis connection
docker compose exec redis redis-cli ping
```

### Kong Ingress Controller not applying CRDs (K8s)

```bash
# Check Kong controller logs
kubectl logs -n kong deploy/kong-controller -f

# Verify CRD was applied
kubectl get kongplugin -n your-namespace

# Check for validation errors
kubectl describe kongplugin jwt-auth -n your-namespace
```

### JWT token rejected even when correct

```bash
# Check clock skew (JWT exp claim must be in the future)
date  # Check system time

# Decode the JWT to inspect claims
echo $TOKEN | cut -d. -f2 | base64 -d | jq .

# Check the consumer's JWT credential is configured
curl http://localhost:8001/consumers/alice/jwt
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-06-api-gateway/local/

# Stop everything
docker compose down

# Full reset including Kong DB and Redis state
docker compose down -v
```

### Kubernetes

```bash
# Uninstall Kong Ingress Controller
helm uninstall kong -n kong
kubectl delete namespace kong

# Delete app namespace
kubectl delete namespace api-gateway

# Delete CRDs if no longer needed
kubectl delete crd kongplugins.configuration.konghq.com
kubectl delete crd kongconsumers.configuration.konghq.com
kubectl delete crd kongingressses.configuration.konghq.com
```
