# Project 01 — E-Commerce Platform: Explained

---

## 1. The App

You are deploying a **fully containerized e-commerce platform** built from 5 independent microservices plus a web frontend. Each service owns its own database — a key microservices principle.

```
Browser
  └─▶ NGINX (API Gateway :8088)
        ├─▶ product-service  (:8001)  → PostgreSQL (products_db)
        ├─▶ cart-service     (:8002)  → Redis (in-memory sessions)
        ├─▶ order-service    (:8003)  → PostgreSQL (orders_db)
        │         └─ calls payment-service + inventory-service internally
        ├─▶ payment-service  (:8004)  → PostgreSQL (payments_db)
        ├─▶ inventory-service(:8005)  → PostgreSQL (inventory_db)
        └─▶ frontend         (static HTML/JS)
```

| Service | What it does |
|---------|-------------|
| **product-service** | Product catalog — browse, search, filter |
| **cart-service** | Shopping cart — add, remove, view items |
| **order-service** | Order management — create, track; orchestrates payment + inventory |
| **payment-service** | Mock payment gateway — processes charges |
| **inventory-service** | Stock tracking — reserve and release inventory |
| **frontend** | Simple web UI — ties everything together |

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-01-ecommerce-platform/local/

# Start the full stack
docker compose up --build

# Or in background
docker compose up --build -d
```

Once all containers are healthy (takes 2-3 min on first run):

| Endpoint | URL |
|----------|-----|
| Web UI | http://localhost:8088 |
| Product Service API docs | http://localhost:8001/docs |
| Cart Service API docs | http://localhost:8002/docs |
| Order Service API docs | http://localhost:8003/docs |
| Payment Service API docs | http://localhost:8004/docs |
| Inventory Service API docs | http://localhost:8005/docs |

**Basic user flow:**
1. Browse products at http://localhost:8088
2. Add items to cart
3. Place an order (triggers payment + inventory reservation)
4. Track order status

### Phase 2 — Deploy to Kubernetes

```bash
cd hands-on-projects/project-01-ecommerce-platform/main/

# Create namespace with Istio injection enabled
kubectl apply -f namespace.yaml

# Deploy secrets, ConfigMaps, StatefulSets, Deployments, Services, Ingress
kubectl apply -f secrets/
kubectl apply -f statefulsets/
kubectl apply -f deployments/
kubectl apply -f services/
kubectl apply -f ingress/

# Optional: Apply Istio VirtualServices and DestinationRules
kubectl apply -f istio/
```

Access the app through your Ingress controller (NGINX or Istio Gateway).

---

## 3. How to Test It

### Smoke Tests — Local

```bash
# Check all services are running
docker compose ps

# Test the product API directly
curl http://localhost:8001/products
curl http://localhost:8001/products/1

# Add to cart
curl -X POST http://localhost:8002/cart \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "product_id": "1", "quantity": 2}'

# Place an order
curl -X POST http://localhost:8003/orders \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "items": [{"product_id": "1", "quantity": 1}]}'

# Check inventory
curl http://localhost:8005/inventory/1
```

### Smoke Tests — Kubernetes

```bash
# Check all pods are Running
kubectl get pods -n ecommerce

# Check services
kubectl get svc -n ecommerce

# Port-forward a service for direct testing
kubectl port-forward svc/product-service 8001:8001 -n ecommerce

# Verify Istio sidecars injected (READY should show 2/2)
kubectl get pods -n ecommerce
```

### Database Tests

```bash
# Local: connect to PostgreSQL directly
docker compose exec postgres-products \
  psql -U shop -d products_db -c "SELECT * FROM products LIMIT 5;"

# Kubernetes: exec into the pod
kubectl exec -it postgres-products-0 -n ecommerce -- \
  psql -U shop -d products_db -c "SELECT COUNT(*) FROM products;"
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Docker / Docker Compose** | Local containerization | `docker compose up --build` runs all 6 containers + 4 DBs |
| **NGINX** | API Gateway | Routes `/api/products/*`, `/api/cart/*`, etc. to backend services |
| **PostgreSQL 16** | Relational database | One instance per stateful service; initialized via SQL scripts |
| **Redis** | Session store | Cart service uses Redis for fast in-memory cart state |
| **Kubernetes** | Production orchestration | Deployments, StatefulSets, Services, Ingress |
| **Istio** | Service mesh | mTLS, traffic management, circuit breaking, rate limiting |
| **Helm** | Package manager | Used to install Istio and NGINX Ingress Controller |
| **kubectl** | K8s CLI | Apply manifests, check pod health, exec into containers |

### Key Kubernetes Concepts Practiced

- **StatefulSets** for PostgreSQL (stable network identity, persistent volumes)
- **Deployments** for stateless microservices
- **Services** (ClusterIP for internal, LoadBalancer/Ingress for external)
- **Secrets** for database credentials
- **ConfigMaps** for service environment variables
- **Istio VirtualServices** for traffic shaping and canary routing
- **Istio DestinationRules** for circuit breakers

---

## 5. Troubleshooting

### Container won't start (Local)

```bash
# Check logs for a failing service
docker compose logs product-service
docker compose logs postgres-products

# Common fix: DB not ready yet — services auto-retry, but you can force restart
docker compose restart product-service
```

### Database connection errors

```bash
# Verify DB is healthy
docker compose exec postgres-products \
  pg_isready -U shop -d products_db

# Check environment variables are set correctly
docker compose exec product-service env | grep POSTGRES
```

### Kubernetes: Pod stuck in Pending

```bash
# Check why pod isn't scheduling
kubectl describe pod <pod-name> -n ecommerce

# Common causes:
# - PVC not bound (check storage class)
# - Node doesn't have enough resources
kubectl get pvc -n ecommerce
kubectl describe pvc <pvc-name> -n ecommerce
```

### Kubernetes: CrashLoopBackOff

```bash
# Get logs from crashing pod
kubectl logs <pod-name> -n ecommerce --previous

# Check environment variables (secrets/configmaps mounted correctly)
kubectl describe pod <pod-name> -n ecommerce
```

### Istio: 503 errors

```bash
# Check if sidecars are injected (READY = 2/2 means sidecar present)
kubectl get pods -n ecommerce

# Check Istio proxy logs
kubectl logs <pod-name> -c istio-proxy -n ecommerce

# Verify VirtualService routing
kubectl get virtualservice -n ecommerce
kubectl describe virtualservice product-service -n ecommerce
```

### NGINX Gateway returning 502

```bash
# NGINX can't reach an upstream service — check service is running
docker compose ps
docker compose logs nginx

# Check nginx config
docker compose exec nginx nginx -t
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-01-ecommerce-platform/local/

# Stop containers (keep data)
docker compose down

# Stop containers AND delete all database volumes (full reset)
docker compose down -v

# Remove built images too
docker compose down -v --rmi local
```

### Kubernetes

```bash
# Delete everything in the namespace
kubectl delete namespace ecommerce

# If you installed Istio separately
helm uninstall istio-base -n istio-system
helm uninstall istiod -n istio-system
kubectl delete namespace istio-system

# If you installed NGINX Ingress Controller
helm uninstall ingress-nginx -n ingress-nginx
kubectl delete namespace ingress-nginx
```
