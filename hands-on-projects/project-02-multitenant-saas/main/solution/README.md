# Solution — Complete Kubernetes Manifests

This folder contains the reference solution for deploying the Multi-Tenant SaaS platform to Kubernetes. Use it as a guide when you're stuck, or to compare against your own work.

---

## How to Apply

### Step 0 — Build and load images into Kind

```bash
# From the project root (project-02-multitenant-saas/)
bash main/solution/build-images.sh
```

### Step 1 — Deploy the shared platform namespace

```bash
cd main/solution

kubectl apply -f platform/namespace.yaml
kubectl apply -f platform/secrets.yaml
kubectl apply -f platform/databases/
kubectl apply -f platform/platform-api/
kubectl apply -f platform/billing-service/
kubectl apply -f platform/admin-ui/
kubectl apply -f platform/ingress.yaml

# Wait for all pods to be ready
kubectl get pods -n saas-platform -w
```

### Step 2 — Deploy tenant namespaces (repeat per tenant)

```bash
# Alice Corp — enterprise plan
TENANT=alice-corp PLAN=enterprise bash main/solution/deploy-tenant.sh

# Bob Industries — pro plan
TENANT=bob-industries PLAN=pro bash main/solution/deploy-tenant.sh

# Charlie Ltd — starter plan (suspended — 0 replicas)
TENANT=charlie-ltd PLAN=starter bash main/solution/deploy-tenant.sh
```

### Step 3 — Verify everything

```bash
# All tenant namespaces
kubectl get ns -l saas.platform/tenant

# Pods in each namespace
kubectl get pods -n saas-platform
kubectl get pods -n tenant-alice-corp
kubectl get pods -n tenant-bob-industries
kubectl get pods -n tenant-charlie-ltd

# Quotas
kubectl describe quota -n tenant-alice-corp

# Test network isolation
kubectl exec -n tenant-alice-corp deploy/app-service -- \
  curl -s --max-time 3 http://app-service.tenant-bob-industries.svc.cluster.local:8011/health
# Expected: connection timeout (NetworkPolicy blocks it)

# Access platform via ingress
kubectl get ingress -n saas-platform
```

---

## File Structure

```
solution/
├── README.md              ← You are here
├── build-images.sh        ← Build all Docker images and load to Kind
├── deploy-tenant.sh       ← Deploys one tenant namespace from template
│
├── platform/              ← Shared saas-platform namespace
│   ├── namespace.yaml
│   ├── secrets.yaml       ← DB credentials for platform-api and billing-service
│   ├── databases/
│   │   ├── postgres-platform.yaml  ← StatefulSet + Service
│   │   └── postgres-billing.yaml   ← StatefulSet + Service
│   ├── platform-api/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── billing-service/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── admin-ui/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   └── ingress.yaml       ← Routes /api/platform/, /api/billing/, / to services
│
└── tenant-template/       ← Template files — TENANT_SLUG gets replaced by deploy-tenant.sh
    ├── namespace.yaml
    ├── rbac.yaml          ← ServiceAccount + Role + RoleBinding
    ├── quotas.yaml        ← ResourceQuota + LimitRange (starter defaults; see comments)
    ├── network.yaml       ← NetworkPolicy (intra-namespace + platform only)
    ├── database.yaml      ← Secret + StatefulSet + Service (dedicated postgres)
    └── app-service.yaml   ← Deployment + Service (uses the dedicated DB)
```

---

## Plan Quota Reference

| Resource | Starter | Pro | Enterprise |
|----------|---------|-----|------------|
| requests.cpu | 500m | 2 | 8 |
| requests.memory | 512Mi | 2Gi | 8Gi |
| limits.cpu | 1 | 4 | 16 |
| limits.memory | 1Gi | 4Gi | 16Gi |
| pods | 5 | 20 | 100 |

The `deploy-tenant.sh` script sets the right quota values based on the `PLAN` env var.

---

## Accessing the Services

After deployment, access services via kubectl port-forward:

```bash
# Admin Dashboard
kubectl port-forward -n saas-platform svc/admin-ui 8090:80
# → http://localhost:8090

# Platform API (Swagger docs)
kubectl port-forward -n saas-platform svc/platform-api 8010:8010
# → http://localhost:8010/docs

# Alice's tasks (app-service in her namespace)
kubectl port-forward -n tenant-alice-corp svc/app-service 9001:8011
curl -H "X-Tenant-ID: alice-corp" http://localhost:9001/tasks
```

Or if you have the NGINX Ingress controller running in Kind:
```bash
# Get the ingress port
kubectl get svc -n ingress-nginx ingress-nginx-controller

# Access via ingress (NodePort)
curl http://localhost:<nodeport>/api/platform/tenants
```
