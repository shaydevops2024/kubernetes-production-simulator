# Main — Production Kubernetes Deployment

This is the production phase. You'll deploy the entire e-commerce platform to Kubernetes, then progressively harden it with Istio, observability, circuit breakers, and rate limiting.

This folder is intentionally empty — **you build it**. The guide below tells you exactly what to create.

---

## What You'll Build

```
main/
├── namespace.yaml
├── secrets/
│   └── db-secrets.yaml
├── configmaps/
│   └── service-config.yaml
├── deployments/
│   ├── product-service.yaml
│   ├── cart-service.yaml
│   ├── order-service.yaml
│   ├── payment-service.yaml
│   ├── inventory-service.yaml
│   └── frontend.yaml
├── services/
│   ├── product-service.yaml
│   ├── cart-service.yaml
│   ├── order-service.yaml
│   ├── payment-service.yaml
│   ├── inventory-service.yaml
│   └── frontend.yaml
├── statefulsets/
│   ├── postgres-products.yaml
│   ├── postgres-orders.yaml
│   ├── postgres-payments.yaml
│   └── postgres-inventory.yaml
├── pvcs/
│   └── postgres-pvcs.yaml
├── ingress/
│   └── ingress.yaml
└── istio/
    ├── gateway.yaml
    ├── virtual-services.yaml
    ├── destination-rules.yaml
    └── rate-limit.yaml
```

---

## Phase 3A — Core Kubernetes Deployment

### Step 1 — Create the Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ecommerce
  labels:
    istio-injection: enabled   # enables Istio sidecar injection
```

Apply: `kubectl apply -f namespace.yaml`

### Step 2 — Create Secrets for Databases

```bash
kubectl create secret generic db-credentials \
  --namespace ecommerce \
  --from-literal=POSTGRES_USER=shop \
  --from-literal=POSTGRES_PASSWORD=shoppass \
  --dry-run=client -o yaml > secrets/db-secrets.yaml
```

**Production note:** In real production, use Vault or Sealed Secrets, never plain Secrets in git.

### Step 3 — Deploy PostgreSQL as StatefulSets

Each database needs:
- A `StatefulSet` (not a Deployment — why?)
- A `PersistentVolumeClaim`
- A `ClusterIP` Service (internal only)

Example for products DB:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-products
  namespace: ecommerce
spec:
  serviceName: postgres-products
  replicas: 1
  selector:
    matchLabels:
      app: postgres-products
  template:
    metadata:
      labels:
        app: postgres-products
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        envFrom:
        - secretRef:
            name: db-credentials
        env:
        - name: POSTGRES_DB
          value: products_db
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "shop", "-d", "products_db"]
          initialDelaySeconds: 10
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
```

Create the same for orders, payments, and inventory databases.

### Step 4 — Deploy Microservices

For each service (product, cart, order, payment, inventory):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-service
  namespace: ecommerce
spec:
  replicas: 2
  selector:
    matchLabels:
      app: product-service
      version: v1
  template:
    metadata:
      labels:
        app: product-service
        version: v1
    spec:
      containers:
      - name: product-service
        image: your-registry/product-service:latest  # push your image here
        ports:
        - containerPort: 8001
        env:
        - name: DATABASE_URL
          value: postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@postgres-products:5432/products_db
        envFrom:
        - secretRef:
            name: db-credentials
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
```

### Step 5 — Create Services

ClusterIP for internal, one LoadBalancer/NodePort for the gateway:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: product-service
  namespace: ecommerce
spec:
  selector:
    app: product-service
  ports:
  - port: 8001
    targetPort: 8001
```

### Step 6 — Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ecommerce-ingress
  namespace: ecommerce
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /api/products(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: product-service
            port:
              number: 8001
      # Repeat for all services
      - path: /(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: frontend
            port:
              number: 80
```

---

## Phase 3B — Istio Service Mesh

### Install Istio
```bash
curl -L https://istio.io/downloadIstio | sh -
istioctl install --set profile=demo -y
kubectl label namespace ecommerce istio-injection=enabled
```

### Gateway + VirtualService
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: Gateway
metadata:
  name: ecommerce-gateway
  namespace: ecommerce
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
---
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: ecommerce-vs
  namespace: ecommerce
spec:
  hosts:
  - "*"
  gateways:
  - ecommerce-gateway
  http:
  - match:
    - uri:
        prefix: /api/products
    route:
    - destination:
        host: product-service
        port:
          number: 8001
  # Add routes for all other services
```

### Circuit Breaker
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: product-service-dr
  namespace: ecommerce
spec:
  host: product-service
  trafficPolicy:
    outlierDetection:
      consecutive5xxErrors: 3
      interval: 10s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
    connectionPool:
      http:
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
```

### Rate Limiting
Use Envoy's local rate limiting filter to limit requests per service.

---

## Phase 3C — Observability

Deploy the Kiali, Jaeger, and Prometheus addons:
```bash
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.21/samples/addons/prometheus.yaml
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.21/samples/addons/grafana.yaml
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.21/samples/addons/jaeger.yaml
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.21/samples/addons/kiali.yaml
```

Access dashboards:
```bash
istioctl dashboard kiali
istioctl dashboard jaeger
istioctl dashboard grafana
```

---

## Deploying Your Images

You need to build and push images before Kubernetes can pull them:

```bash
# Build
docker build -t your-dockerhub-user/product-service:v1 ../app/product-service/
docker build -t your-dockerhub-user/cart-service:v1 ../app/cart-service/
# ... repeat for all services

# Push
docker push your-dockerhub-user/product-service:v1
docker push your-dockerhub-user/cart-service:v1
# ... repeat for all services
```

Or use a local registry with Kind:
```bash
# Load images directly into Kind cluster
kind load docker-image your-dockerhub-user/product-service:v1 --name your-cluster-name
```

---

## Verification Checklist

- [ ] All pods running in `ecommerce` namespace
- [ ] Database StatefulSets have PVCs bound
- [ ] Product service returns products via Ingress
- [ ] Cart service can add/remove items
- [ ] Full order flow works end-to-end
- [ ] Istio sidecars injected (2/2 containers in each pod)
- [ ] Service-to-service traffic uses mTLS
- [ ] Circuit breaker triggers when payment service is down
- [ ] Rate limiting blocks excessive requests
- [ ] Traces visible in Jaeger
- [ ] Metrics visible in Grafana

---

## Tips

- Start with a single replica of each service. Scale after confirming everything works.
- Test each service independently before testing inter-service calls.
- Use `kubectl describe pod <pod>` when pods won't start — the events section tells you why.
- `kubectl logs -f <pod> -c <container>` to tail logs including Istio sidecar logs.
