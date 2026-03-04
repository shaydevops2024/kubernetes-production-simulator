# Project 02 — Multi-Tenant SaaS: Explained

---

## 1. The App

You are deploying a **multi-tenant SaaS platform** — a system where multiple companies ("tenants") each get an isolated environment within the same application. Think of it like AWS accounts: each customer sees only their own data and resources.

```
Browser
  └─▶ NGINX (Admin Dashboard)
        ├─▶ /api/platform/*  →  platform-api   → PostgreSQL (platform_db)
        ├─▶ /api/billing/*   →  billing-service → PostgreSQL (billing_db)
        └─▶ /api/app/*       →  app-service     → PostgreSQL (app_db)
```

| Service | What it does |
|---------|-------------|
| **platform-api** | Tenant lifecycle — create, suspend, delete tenants. Stores plan limits (CPU, memory, pod counts) |
| **app-service** | The actual SaaS product (a task manager). Each tenant sees only their own tasks via header-based routing |
| **billing-service** | Meters every API call per tenant. Computes usage and estimated cost |
| **admin-ui** | Admin dashboard showing all tenants, their resource limits, task counts, and usage charts |

**Core tenant isolation concept:** In Kubernetes, each tenant gets their own `Namespace` with dedicated RBAC roles, `ResourceQuota`, and `NetworkPolicy` — so one tenant can't affect another's resources or traffic.

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-02-multitenant-saas/local/

docker compose up --build -d
```

Once running:

| Endpoint | URL |
|----------|-----|
| Admin Dashboard | http://localhost:8080 |
| Platform API docs | http://localhost:8001/docs |
| App Service docs | http://localhost:8002/docs |
| Billing Service docs | http://localhost:8003/docs |

**Basic workflow:**
1. Open the Admin Dashboard at http://localhost:8080
2. Create a tenant (e.g., "acme-corp", plan: "pro")
3. Switch the tenant header to use that tenant's data
4. Create tasks as tenant-A — observe tenant-B cannot see them
5. Check billing service for per-tenant usage metrics

```bash
# Create a tenant via API
curl -X POST http://localhost:8001/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "acme-corp", "plan": "pro"}'

# Create a task as a specific tenant
curl -X POST http://localhost:8002/tasks \
  -H "X-Tenant-ID: acme-corp" \
  -H "Content-Type: application/json" \
  -d '{"title": "Deploy new feature", "priority": "high"}'

# See only acme-corp tasks (isolation check)
curl http://localhost:8002/tasks \
  -H "X-Tenant-ID: acme-corp"
```

### Phase 2 — Deploy to Kubernetes

```bash
cd hands-on-projects/project-02-multitenant-saas/main/

# Core namespace + RBAC
kubectl apply -f namespaces/
kubectl apply -f rbac/

# Resource quotas and network policies
kubectl apply -f quotas/
kubectl apply -f network-policies/

# Deploy all services
kubectl apply -f deployments/
kubectl apply -f services/
kubectl apply -f ingress/
```

In Kubernetes, each tenant namespace is isolated:
- `ResourceQuota`: limits CPU, memory, and pod count per namespace
- `NetworkPolicy`: tenants cannot send traffic across namespaces
- RBAC: per-tenant service accounts with minimal permissions

---

## 3. How to Test It

### Tenant Isolation Test

```bash
# Create two tenants
curl -X POST http://localhost:8001/tenants -d '{"name": "tenant-a", "plan": "starter"}'
curl -X POST http://localhost:8001/tenants -d '{"name": "tenant-b", "plan": "pro"}'

# Create tasks for each
curl -X POST http://localhost:8002/tasks \
  -H "X-Tenant-ID: tenant-a" \
  -d '{"title": "Task for A"}'

# Verify tenant-b cannot see tenant-a tasks
curl http://localhost:8002/tasks -H "X-Tenant-ID: tenant-b"
# Should return empty list
```

### Billing Metering Test

```bash
# Make several API calls as tenant-a
for i in {1..10}; do
  curl http://localhost:8002/tasks -H "X-Tenant-ID: tenant-a"
done

# Check billing usage
curl http://localhost:8003/usage/tenant-a
# Should show 10+ API calls
```

### Kubernetes: Resource Quota Test

```bash
# Check quotas in a tenant namespace
kubectl describe resourcequota -n tenant-acme-corp

# Try to exceed quota (deploy more replicas than allowed)
kubectl scale deployment app-service -n tenant-acme-corp --replicas=100
# Kubernetes should reject with quota exceeded error
```

### Network Policy Test (K8s)

```bash
# Attempt cross-namespace traffic (should be blocked)
kubectl exec -n tenant-a-ns -- curl http://app-service.tenant-b-ns.svc.cluster.local
# Should timeout or be refused
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Docker / Docker Compose** | Local development | `docker compose up` runs all 4 services + 3 PostgreSQL instances |
| **NGINX** | Reverse proxy | Routes `/api/platform`, `/api/billing`, `/api/app` to correct backends |
| **PostgreSQL** | Relational database | Separate DB per service; tenant data isolated by `tenant_id` column |
| **Kubernetes Namespaces** | Tenant isolation | Each tenant = one namespace with its own resources |
| **ResourceQuota** | Usage limits | Enforces max CPU, memory, pod count per tenant namespace |
| **NetworkPolicy** | Traffic isolation | Blocks cross-namespace traffic between tenants |
| **RBAC** | Access control | Per-tenant service accounts; developers can only access their own namespace |
| **kubectl** | K8s CLI | Apply manifests, verify quotas, check policy enforcement |

### Key Kubernetes Concepts Practiced

- **Namespace-per-tenant** multi-tenancy model
- `ResourceQuota` enforcement at the namespace level
- `LimitRange` for default resource limits on pods
- `NetworkPolicy` with namespace selectors for tenant isolation
- **RBAC**: `Role` + `RoleBinding` scoped to tenant namespace

---

## 5. Troubleshooting

### Service can't connect to its database

```bash
# Check if PostgreSQL is running
docker compose ps postgres-platform

# Check logs
docker compose logs postgres-platform

# Test connection manually
docker compose exec postgres-platform \
  psql -U saas -d platform_db -c "\dt"
```

### Tenant data appearing in wrong tenant's view

```bash
# The app uses X-Tenant-ID header — check it's being passed
curl -v http://localhost:8002/tasks -H "X-Tenant-ID: acme-corp"

# Check the app-service logs for tenant parsing
docker compose logs app-service | grep tenant
```

### Kubernetes: Pod can't reach other pods across namespace

```bash
# This is expected if NetworkPolicy is in place
# To verify the policy is the cause:
kubectl describe networkpolicy -n tenant-a-ns

# Check if DNS resolves correctly within namespace
kubectl exec -n tenant-a-ns deploy/app-service -- \
  nslookup postgres-app.tenant-a-ns.svc.cluster.local
```

### ResourceQuota blocking deployments

```bash
# See current quota usage
kubectl describe resourcequota -n tenant-a-ns

# Quota name and used/hard limits shown
# Increase quota or reduce replicas
kubectl edit resourcequota tenant-quota -n tenant-a-ns
```

### Admin dashboard showing no tenants

```bash
# Check platform-api is reachable
curl http://localhost:8001/tenants

# Check NGINX routing config
docker compose exec nginx nginx -t
docker compose logs nginx
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-02-multitenant-saas/local/

# Stop and remove containers
docker compose down

# Full reset including all database volumes
docker compose down -v
```

### Kubernetes

```bash
# Delete all tenant namespaces
kubectl delete namespace tenant-a-ns tenant-b-ns

# Delete the platform namespace
kubectl delete namespace saas-platform

# Or delete by label if you labeled them
kubectl delete namespaces -l project=multitenant-saas
```
