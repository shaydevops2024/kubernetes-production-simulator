# Main — Production Kubernetes Deployment

This is the production phase. You'll transform the single-box Docker Compose setup into a **true multi-tenant Kubernetes platform** with namespace isolation, RBAC, resource quotas, and network policies.

This folder is intentionally empty — **you build it**. The guide below tells you exactly what to create.

---

## The Big Shift: From App-Level to Infra-Level Isolation

| Concern | Local (Docker Compose) | Kubernetes (this folder) |
|---------|----------------------|--------------------------|
| Tenant isolation | `X-Tenant-ID` header + DB column filter | Separate namespace per tenant |
| Database | Shared DB, `tenant_id` column | Dedicated PostgreSQL per namespace |
| Resource limits | None | ResourceQuota + LimitRange per namespace |
| Network isolation | Shared Docker network | NetworkPolicy per namespace |
| Access control | None | RBAC — ServiceAccount + RoleBinding per namespace |
| Billing | API call counter | Prometheus metrics per namespace |

---

## What You'll Build

```
main/
├── platform/                      ← Shared platform namespace
│   ├── namespace.yaml
│   ├── platform-api/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   ├── billing-service/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── admin-ui/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── databases/
│   │   ├── postgres-platform.yaml
│   │   └── postgres-billing.yaml
│   └── ingress.yaml
│
└── tenant-template/               ← Apply once per tenant (Alice, Bob, Charlie...)
    ├── namespace.yaml             ← namespace: tenant-<slug>
    ├── rbac/
    │   ├── serviceaccount.yaml
    │   ├── role.yaml
    │   └── rolebinding.yaml
    ├── quotas/
    │   ├── resourcequota.yaml     ← CPU / memory / pod limits by plan
    │   └── limitrange.yaml        ← Default requests/limits per container
    ├── network/
    │   └── networkpolicy.yaml     ← Allow only intra-namespace + platform traffic
    ├── app-service/
    │   ├── deployment.yaml        ← No X-Tenant-ID needed — namespace IS the tenant
    │   ├── service.yaml
    │   └── configmap.yaml
    └── database/
        ├── statefulset.yaml       ← Dedicated PostgreSQL per tenant
        ├── service.yaml
        └── secret.yaml
```

---

## Phase 1 — Platform Namespace

### Step 1 — Create the Platform Namespace

```yaml
# platform/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: saas-platform
  labels:
    app.kubernetes.io/part-of: saas-platform
```

```bash
kubectl apply -f platform/namespace.yaml
```

### Step 2 — Deploy the Platform API

```yaml
# platform/platform-api/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: platform-api
  namespace: saas-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: platform-api
  template:
    metadata:
      labels:
        app: platform-api
    spec:
      containers:
      - name: platform-api
        image: your-registry/platform-api:v1
        ports:
        - containerPort: 8010
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: platform-db-secret
              key: url
        readinessProbe:
          httpGet:
            path: /health
            port: 8010
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
```

Create the same for `billing-service` and `admin-ui`. Deploy PostgreSQL for platform and billing using StatefulSets (same pattern as Project 01).

### Step 3 — Ingress for the Platform

```yaml
# platform/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: saas-platform-ingress
  namespace: saas-platform
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /api/platform(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: platform-api
            port:
              number: 8010
      - path: /api/billing(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: billing-service
            port:
              number: 8012
      - path: (/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: admin-ui
            port:
              number: 80
```

---

## Phase 2 — Tenant Namespace (Repeat per Tenant)

Apply this for each tenant. Replace `<TENANT_SLUG>` and `<PLAN>` with the actual values (e.g. `alice-corp` / `enterprise`).

### Step 1 — Create the Tenant Namespace

```yaml
# tenant-template/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-<TENANT_SLUG>           # e.g. tenant-alice-corp
  labels:
    saas.platform/tenant: "<TENANT_SLUG>"
    saas.platform/plan:   "<PLAN>"
    app.kubernetes.io/part-of: saas-platform
```

```bash
kubectl apply -f tenant-template/namespace.yaml
```

### Step 2 — RBAC (ServiceAccount + Role + RoleBinding)

Every tenant namespace gets a dedicated ServiceAccount. In Kubernetes, RBAC lets you define exactly what the app-service is allowed to do within its own namespace.

```yaml
# tenant-template/rbac/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-service-sa
  namespace: tenant-<TENANT_SLUG>
---
# tenant-template/rbac/role.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-service-role
  namespace: tenant-<TENANT_SLUG>
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
---
# tenant-template/rbac/rolebinding.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-service-rb
  namespace: tenant-<TENANT_SLUG>
subjects:
- kind: ServiceAccount
  name: app-service-sa
  namespace: tenant-<TENANT_SLUG>
roleRef:
  kind: Role
  apiGroup: rbac.authorization.k8s.io
  name: app-service-role
```

**Why this matters:** Without RBAC, a compromised pod in `tenant-alice-corp` could potentially read Secrets from `tenant-bob-industries`. The Role restricts it to its own namespace only.

### Step 3 — Resource Quotas

This is where plan tiers become real infrastructure limits.

```yaml
# tenant-template/quotas/resourcequota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-quota
  namespace: tenant-<TENANT_SLUG>
spec:
  hard:
    # Adjust based on plan: starter / pro / enterprise
    requests.cpu:    "500m"    # starter: 500m | pro: 2 | enterprise: 8
    requests.memory: "512Mi"   # starter: 512Mi | pro: 2Gi | enterprise: 8Gi
    limits.cpu:      "1"
    limits.memory:   "1Gi"
    pods:            "5"       # starter: 5 | pro: 20 | enterprise: 100
    services:        "5"
    persistentvolumeclaims: "2"
---
# tenant-template/quotas/limitrange.yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: tenant-limits
  namespace: tenant-<TENANT_SLUG>
spec:
  limits:
  - type: Container
    default:           { cpu: "200m",  memory: "256Mi" }
    defaultRequest:    { cpu: "100m",  memory: "128Mi" }
    max:               { cpu: "1",     memory: "1Gi"   }
```

```bash
# Verify the quota is enforced
kubectl describe resourcequota tenant-quota -n tenant-alice-corp

# Try to create more pods than allowed — it should fail
```

### Step 4 — Network Policies

Isolate tenants from each other. By default, all pods in a Kubernetes cluster can talk to any other pod. NetworkPolicies fix this.

```yaml
# tenant-template/network/networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: tenant-<TENANT_SLUG>
spec:
  podSelector: {}          # applies to ALL pods in this namespace
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Allow inbound traffic only from the same namespace
  - from:
    - podSelector: {}
  # Allow inbound from the platform namespace (for billing + admin)
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: saas-platform
  egress:
  # Allow all outbound within the same namespace
  - to:
    - podSelector: {}
  # Allow talking to the billing service in saas-platform
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: saas-platform
    ports:
    - port: 8012
  # Allow DNS resolution
  - ports:
    - port: 53
      protocol: UDP
    - port: 53
      protocol: TCP
```

**Test isolation:**
```bash
# Can alice's pod reach bob's app-service?
kubectl exec -n tenant-alice-corp deploy/app-service -- \
  curl -s http://app-service.tenant-bob-industries.svc.cluster.local:8011/health
# Should fail — NetworkPolicy blocks it
```

### Step 5 — Tenant-Specific Database

Each tenant gets their own PostgreSQL. This is the core of **data isolation**.

```yaml
# tenant-template/database/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-db-secret
  namespace: tenant-<TENANT_SLUG>
type: Opaque
stringData:
  POSTGRES_USER:     tenant
  POSTGRES_PASSWORD: <generated-per-tenant>
  POSTGRES_DB:       app_db
  url: postgresql://tenant:<password>@postgres-app:5432/app_db
---
# tenant-template/database/statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-app
  namespace: tenant-<TENANT_SLUG>
spec:
  serviceName: postgres-app
  replicas: 1
  selector:
    matchLabels:
      app: postgres-app
  template:
    metadata:
      labels:
        app: postgres-app
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        envFrom:
        - secretRef:
            name: app-db-secret
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "tenant", "-d", "app_db"]
          initialDelaySeconds: 10
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 2Gi
```

### Step 6 — Tenant App Service

```yaml
# tenant-template/app-service/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-service
  namespace: tenant-<TENANT_SLUG>
spec:
  replicas: 1
  selector:
    matchLabels:
      app: app-service
  template:
    metadata:
      labels:
        app: app-service
    spec:
      serviceAccountName: app-service-sa   # uses the RBAC SA from Step 2
      containers:
      - name: app-service
        image: your-registry/app-service:v1
        ports:
        - containerPort: 8011
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-db-secret
              key: url
        - name: BILLING_SERVICE_URL
          value: "http://billing-service.saas-platform.svc.cluster.local:8012"
        # NOTE: No X-Tenant-ID env var needed.
        # In K8s, the namespace itself IS the tenant boundary.
        readinessProbe:
          httpGet:
            path: /health
            port: 8011
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
```

---

## Phase 3 — Verify Everything Works

```bash
# Check all tenant namespaces exist
kubectl get ns -l saas.platform/tenant

# Verify resource quotas are applied
kubectl describe quota -n tenant-alice-corp
kubectl describe quota -n tenant-bob-industries

# Check pods in each namespace
kubectl get pods -n tenant-alice-corp
kubectl get pods -n tenant-bob-industries
kubectl get pods -n saas-platform

# Verify database isolation — each tenant has their own PVC
kubectl get pvc -n tenant-alice-corp
kubectl get pvc -n tenant-bob-industries

# Test the app service for each tenant (no X-Tenant-ID needed — they're separate deployments)
kubectl port-forward -n tenant-alice-corp svc/app-service 9001:8011 &
curl http://localhost:9001/tasks
# Should return only Alice's tasks

# Test network isolation
kubectl exec -n tenant-alice-corp deploy/app-service -- \
  curl -s --max-time 3 http://app-service.tenant-bob-industries.svc.cluster.local:8011/health
# Should time out — NetworkPolicy blocks cross-tenant traffic

# Check admin dashboard still works through ingress
kubectl get ingress -n saas-platform
```

---

## Verification Checklist

- [ ] `saas-platform` namespace running (platform-api, billing-service, admin-ui, 2 databases)
- [ ] `tenant-alice-corp` namespace with app-service + postgres-app
- [ ] `tenant-bob-industries` namespace with app-service + postgres-app
- [ ] `tenant-charlie-ltd` namespace with app-service + postgres-app (suspended — 0 replicas)
- [ ] ResourceQuota applied to all tenant namespaces
- [ ] LimitRange applied to all tenant namespaces
- [ ] NetworkPolicy isolating tenants from each other
- [ ] RBAC: each tenant's app-service uses its own ServiceAccount
- [ ] Ingress routing to platform-api and admin-ui works
- [ ] Admin dashboard loads and shows tenants
- [ ] Tasks API returns only tenant-specific data per namespace
- [ ] Cross-tenant traffic is blocked by NetworkPolicy

---

## Tips

- Start with one tenant namespace (`tenant-alice-corp`) and get it fully working before repeating for others.
- Use `kubectl events -n <namespace>` to debug scheduling or quota rejection issues.
- If a pod can't start due to quota, `kubectl describe pod <name> -n <ns>` will show the quota error.
- Use `kubectl auth can-i --as=system:serviceaccount:<ns>:app-service-sa get secrets -n <ns>` to test RBAC without actually running the pod.
- Network policies only work if your cluster has a CNI plugin that supports them (Calico, Cilium, etc.). Kind with default settings supports them.
