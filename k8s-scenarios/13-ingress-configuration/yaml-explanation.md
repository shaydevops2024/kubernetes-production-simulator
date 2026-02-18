# YAML Files Explanation - Ingress Configuration Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 🚀 deployment.yaml

### What is the Deployment's Role?
Standard application deployment providing the backend pods that will be exposed externally via Ingress.

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ingress-demo-app
  namespace: scenarios
  labels:
    app: ingress-demo
    scenario: "14"
```
**What it is:** Standard Deployment resource
**Nothing special:** Regular deployment - the magic happens in the Ingress

**Labels:**
- `app: ingress-demo` - Application identifier
- `scenario: "14"` - Scenario number (organizational)

```yaml
spec:
  replicas: 2
```
**What it is:** Number of pod replicas
**Why 2?** High availability, load balancing demonstration

```yaml
  selector:
    matchLabels:
      app: ingress-demo
  template:
    metadata:
      labels:
        app: ingress-demo
    spec:
      containers:
      - name: nginx
        image: nginx:1.21-alpine
        ports:
        - containerPort: 80
```
**What it is:** Standard pod template with Nginx
**Image:** nginx:1.21-alpine - Lightweight web server
**Port:** 80 - Standard HTTP port

---

## 🌐 service.yaml

### What is the Service's Role?
Provides a stable network endpoint for the Deployment. The Ingress routes external traffic to this Service, which then load balances to the pods.

### YAML Structure Breakdown:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ingress-demo-service
  namespace: scenarios
```
**What it is:** Standard Service resource
**Name:** `ingress-demo-service` - Referenced by Ingress

**Important:** Service name must match Ingress backend configuration

```yaml
spec:
  selector:
    app: ingress-demo
```
**What it is:** Routes to pods with label `app: ingress-demo`
**Must match:** Deployment's `template.metadata.labels`

```yaml
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
```
**What it is:** Port mapping
- `port: 80` - Service listens on port 80
- `targetPort: 80` - Forward to pod port 80

**Note:** No `type` specified = ClusterIP (default)
**Why ClusterIP?** Ingress controller accesses service internally (no external LoadBalancer needed)

**Traffic flow:**
```
Internet → Ingress Controller (NodePort/LoadBalancer) →
Ingress routes based on rules →
Service (ClusterIP) →
Pods
```

---

## 🔀 ingress.yaml

### What is an Ingress?
Ingress is an API object that manages external access to services in a cluster, typically HTTP/HTTPS. It provides:
- **Host-based routing** (domain names)
- **Path-based routing** (/api, /web)
- **TLS/SSL termination**
- **Load balancing**
- **URL rewriting**

Think of it as a **Layer 7 (HTTP) load balancer and reverse proxy** for your cluster.

### YAML Structure Breakdown:

```yaml
apiVersion: networking.k8s.io/v1
```
**What it is:** Networking API group, version 1
**History:**
- `extensions/v1beta1` - Very old (deprecated)
- `networking.k8s.io/v1beta1` - Old (deprecated in K8s 1.22)
- `networking.k8s.io/v1` - **Current stable** (K8s 1.19+)

**For older Kubernetes (<1.19):**
```yaml
apiVersion: networking.k8s.io/v1beta1
```

```yaml
kind: Ingress
```
**What it is:** Declares this is an Ingress resource
**Purpose:** Define routing rules for external HTTP/HTTPS traffic

```yaml
metadata:
  name: ingress-demo
  namespace: scenarios
```
**What it is:** Ingress metadata
- `name: ingress-demo` - Ingress name
- `namespace: scenarios` - Must match Service namespace

**Important:** Ingress can only route to Services in the **same namespace**

```yaml
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
```
**What it is:** Ingress controller-specific configuration
**Critical:** Annotations are **controller-specific** (NGINX, Traefik, HAProxy, etc.)

### 🔑 Understanding Annotations

**What are annotations?**
- Key-value pairs providing configuration hints to Ingress controller
- **Not** part of core Kubernetes spec
- Different controllers support different annotations

**This annotation explained:**
```yaml
nginx.ingress.kubernetes.io/rewrite-target: /
```

**What it does:** URL path rewriting

**Example:**
```
Incoming request: http://scenario-demo.local/api/users
Ingress path match: /api
Rewrite target: /
Backend receives: http://ingress-demo-service/users  (not /api/users)
```

**Why needed?**
- Backend app doesn't know about `/api` prefix
- Ingress handles routing, backend handles logic
- Allows path-based routing without modifying app

**Without rewrite:**
```
Request: /api/users
Backend receives: /api/users
App returns: 404 (no route for /api/users)
```

**With rewrite:**
```
Request: /api/users
Rewrite: / + users = /users
Backend receives: /users
App returns: 200 ✅
```

**Common NGINX Ingress annotations:**

```yaml
annotations:
  # URL rewriting
  nginx.ingress.kubernetes.io/rewrite-target: /

  # SSL redirect
  nginx.ingress.kubernetes.io/ssl-redirect: "true"

  # CORS
  nginx.ingress.kubernetes.io/enable-cors: "true"

  # Rate limiting
  nginx.ingress.kubernetes.io/limit-rps: "10"

  # Timeouts
  nginx.ingress.kubernetes.io/proxy-connect-timeout: "60"
  nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
  nginx.ingress.kubernetes.io/proxy-read-timeout: "60"

  # Websockets
  nginx.ingress.kubernetes.io/websocket-services: "my-websocket-svc"

  # Authentication
  nginx.ingress.kubernetes.io/auth-url: "https://auth.example.com/auth"

  # Custom headers
  nginx.ingress.kubernetes.io/configuration-snippet: |
    add_header X-Custom-Header "MyValue";
```

**Traefik annotations (different syntax!):**
```yaml
annotations:
  traefik.ingress.kubernetes.io/router.entrypoints: websecure
  traefik.ingress.kubernetes.io/router.tls: "true"
```

**Key insight:** Always check your Ingress controller's documentation for supported annotations!

```yaml
spec:
  ingressClassName: nginx
```
**What it is:** **CRITICAL** - Specifies which Ingress controller handles this Ingress
**New in:** Kubernetes 1.18+ (replaces deprecated annotation)

**Why needed?**
- Multiple Ingress controllers can coexist in one cluster
- Each Ingress must specify which controller to use
- Prevents conflicts

**Common IngressClasses:**
- `nginx` - NGINX Ingress Controller (most popular)
- `traefik` - Traefik Ingress Controller
- `haproxy` - HAProxy Ingress Controller
- `alb` - AWS ALB Ingress Controller
- `gce` - GCE Ingress Controller (Google Cloud)

**Check available IngressClasses:**
```bash
kubectl get ingressclass
```

**Old way (deprecated):**
```yaml
# Deprecated annotation (K8s < 1.18)
annotations:
  kubernetes.io/ingress.class: "nginx"
```

**⚠️ Important:** If `ingressClassName` is missing, the Ingress may not work or use default controller

```yaml
  rules:
```
**What it is:** **THE CORE** - Defines routing rules
**Structure:** List of rules (can have multiple)

Each rule can have:
- **Host-based routing** (domain name)
- **Path-based routing** (URL path)
- **Backend service** (where to route)

```yaml
  - host: scenario-demo.local
```
**What it is:** **Host-based routing** - Route based on domain name
**Value:** `scenario-demo.local` - DNS hostname

**How it works:**
```
Request to: http://scenario-demo.local/anything
→ Matches this rule ✅
→ Routes to backend

Request to: http://other-domain.com/anything
→ No match ❌
→ Returns 404 (or default backend)
```

**Production examples:**
```yaml
# Production domain
host: api.example.com

# Subdomain per environment
host: staging.example.com

# Wildcard (some controllers support)
host: "*.example.com"
```

**Multiple hosts (different services):**
```yaml
rules:
- host: api.example.com
  http:
    paths:
    - path: /
      backend:
        service:
          name: api-service
- host: web.example.com
  http:
    paths:
    - path: /
      backend:
        service:
          name: web-service
```

**Testing without DNS:**
```bash
# Add to /etc/hosts (local testing)
echo "127.0.0.1 scenario-demo.local" | sudo tee -a /etc/hosts

# Or use curl with Host header
curl -H "Host: scenario-demo.local" http://<ingress-ip>/
```

```yaml
    http:
      paths:
```
**What it is:** HTTP routing rules
**Also available:** `https` (but requires TLS configuration)

**Multiple paths example:**
```yaml
http:
  paths:
  - path: /api
    backend:
      service:
        name: api-service
  - path: /web
    backend:
      service:
        name: web-service
```

```yaml
      - path: /
        pathType: Prefix
```
**What it is:** **Path-based routing** - Route based on URL path

**path: /**
- Match all paths starting with `/`
- Essentially matches everything

**pathType: Prefix** ⭐ **CRITICAL FIELD**
- How to interpret the path

**pathType options:**

1. **Prefix** (used here - most common):
   ```yaml
   path: /api
   pathType: Prefix

   Matches:
   /api              ✅
   /api/users        ✅
   /api/users/123    ✅
   /apidocs          ❌ (not a prefix)
   /web              ❌
   ```

2. **Exact**:
   ```yaml
   path: /api
   pathType: Exact

   Matches:
   /api              ✅
   /api/             ❌
   /api/users        ❌ (not exact)
   ```

3. **ImplementationSpecific** (controller-dependent):
   ```yaml
   path: /api/*
   pathType: ImplementationSpecific

   Behavior depends on Ingress controller
   ```

**Path matching examples:**

```yaml
# Route API calls to api-service
- path: /api
  pathType: Prefix
  backend:
    service:
      name: api-service
      port:
        number: 8080

# Route web UI to web-service
- path: /web
  pathType: Prefix
  backend:
    service:
      name: web-service
      port:
        number: 80

# Exact match for root
- path: /
  pathType: Exact
  backend:
    service:
      name: home-service
      port:
        number: 80

# Catch-all (place last)
- path: /
  pathType: Prefix
  backend:
    service:
      name: default-service
      port:
        number: 80
```

**⚠️ Path precedence:**
- More specific paths matched first
- `/api/v2` > `/api` > `/`
- Exact > Prefix
- Longer paths > Shorter paths

```yaml
        backend:
          service:
            name: ingress-demo-service
            port:
              number: 80
```
**What it is:** **Backend service** - Where to route matching requests

**backend.service.name:** Must match a Service name in same namespace
**backend.service.port.number:** Service port (not pod port)

**Port specification options:**

```yaml
# Option 1: Port number (used here)
port:
  number: 80

# Option 2: Port name (references named Service port)
port:
  name: http
```

**Using named ports:**
```yaml
# Service
apiVersion: v1
kind: Service
spec:
  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: https
    port: 443
    targetPort: 8443

---
# Ingress
backend:
  service:
    name: my-service
    port:
      name: http  # References "http" port from Service
```

**Benefits of named ports:**
- Change port numbers without updating Ingress
- More readable
- Less error-prone

---

## 🔄 How Ingress Works - Complete Flow

### Architecture:

```
Internet
  │
  ▼
Load Balancer (Cloud) / NodePort (on-prem)
  │
  ▼
Ingress Controller Pod (NGINX, Traefik, etc.)
  │ Reads Ingress resources
  │ Generates routing configuration
  │ Watches for changes
  │
  ▼ Applies routing rules
  │
  ▼
Service (ClusterIP)
  │
  ▼
Pods
```

### Components:

1. **Ingress Resource** (this YAML):
   - Defines routing rules
   - Declarative configuration
   - Kubernetes API object

2. **Ingress Controller**:
   - Pod running in cluster
   - Watches Ingress resources
   - Implements routing rules
   - Examples: NGINX, Traefik, HAProxy, Istio

3. **Service**:
   - Backend target
   - Routes to pods

### Complete Request Flow:

```
1. User types: http://scenario-demo.local/

2. DNS resolution:
   scenario-demo.local → Ingress Controller IP (LoadBalancer or NodeIP)

3. Request hits Ingress Controller Pod:
   - NGINX pod receives request
   - Checks Host header: "scenario-demo.local"
   - Checks path: "/"

4. Ingress Controller matches Ingress rules:
   - Finds Ingress: ingress-demo
   - Rule: host=scenario-demo.local, path=/
   - Backend: ingress-demo-service:80

5. Ingress Controller forwards to Service:
   - Sends request to ingress-demo-service:80 (ClusterIP)

6. Service load balances to Pod:
   - Service selects pod with label app=ingress-demo
   - Forwards to pod port 80

7. Pod processes request:
   - NGINX serves response

8. Response travels back:
   Pod → Service → Ingress Controller → User
```

### Installation Flow (NGINX Ingress Controller):

```bash
# 1. Install NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# 2. Wait for controller ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# 3. Get Ingress Controller IP
kubectl get svc -n ingress-nginx ingress-nginx-controller

# 4. Deploy application (Deployment + Service)
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# 5. Deploy Ingress
kubectl apply -f ingress.yaml

# 6. Access application
curl -H "Host: scenario-demo.local" http://<ingress-ip>/
```

---

## 📊 Advanced Ingress Features

### 1. TLS/SSL Termination

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ingress-tls
spec:
  tls:
  - hosts:
    - scenario-demo.local
    secretName: tls-secret  # References Secret with TLS cert
  rules:
  - host: scenario-demo.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ingress-demo-service
            port:
              number: 80
```

**Create TLS Secret:**
```bash
kubectl create secret tls tls-secret \
  --cert=path/to/cert.crt \
  --key=path/to/key.key \
  -n scenarios
```

**Result:**
- HTTPS enabled on scenario-demo.local
- Ingress Controller terminates TLS
- Backend traffic is HTTP (inside cluster)

### 2. Multiple Paths (Microservices)

```yaml
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /users
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 80
      - path: /products
        pathType: Prefix
        backend:
          service:
            name: product-service
            port:
              number: 80
      - path: /orders
        pathType: Prefix
        backend:
          service:
            name: order-service
            port:
              number: 80
```

**Traffic routing:**
```
http://api.example.com/users/123     → user-service
http://api.example.com/products/456  → product-service
http://api.example.com/orders/789    → order-service
```

### 3. Default Backend

```yaml
spec:
  defaultBackend:
    service:
      name: default-service
      port:
        number: 80
  rules:
  - host: scenario-demo.local
    # ... rules ...
```

**What it does:**
- Catches all requests that don't match any rules
- Like a "404 handler"

**Example:**
```
Request: http://unknown-domain.com/
→ No matching rule
→ Routes to default-service
```

### 4. Path Rewriting (Advanced)

```yaml
annotations:
  nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /api(/|$)(.*)
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

**Regex capture groups:**
```
Request: /api/users/123
Capture: $2 = users/123
Rewrite: / + users/123 = /users/123
Backend receives: /users/123
```

### 5. Authentication (OAuth, Basic Auth)

```yaml
annotations:
  # OAuth2 authentication
  nginx.ingress.kubernetes.io/auth-url: "https://oauth2.example.com/auth"
  nginx.ingress.kubernetes.io/auth-signin: "https://oauth2.example.com/start"

  # Basic authentication
  nginx.ingress.kubernetes.io/auth-type: basic
  nginx.ingress.kubernetes.io/auth-secret: basic-auth
  nginx.ingress.kubernetes.io/auth-realm: "Authentication Required"
```

**Create Basic Auth secret:**
```bash
htpasswd -c auth myuser
kubectl create secret generic basic-auth --from-file=auth -n scenarios
```

### 6. Rate Limiting

```yaml
annotations:
  nginx.ingress.kubernetes.io/limit-rps: "10"          # 10 req/sec per IP
  nginx.ingress.kubernetes.io/limit-connections: "5"    # 5 concurrent connections
```

**Prevents:**
- DDoS attacks
- API abuse
- Resource exhaustion

### 7. CORS Headers

```yaml
annotations:
  nginx.ingress.kubernetes.io/enable-cors: "true"
  nginx.ingress.kubernetes.io/cors-allow-origin: "https://example.com"
  nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, PUT, DELETE"
  nginx.ingress.kubernetes.io/cors-allow-headers: "Content-Type, Authorization"
```

### 8. Canary Deployments

```yaml
# Main Ingress (90% traffic)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: main-ingress
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        backend:
          service:
            name: main-service
---
# Canary Ingress (10% traffic)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: canary-ingress
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"  # 10% traffic
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        backend:
          service:
            name: canary-service
```

**Progressive rollout:**
```
canary-weight: 10   # 10% to canary, 90% to main
canary-weight: 50   # 50/50 split
canary-weight: 100  # 100% to canary (then remove main)
```

---

## 🎯 Best Practices

### 1. Always Use IngressClassName

```yaml
# Good
spec:
  ingressClassName: nginx

# Bad (deprecated)
annotations:
  kubernetes.io/ingress.class: "nginx"
```

### 2. Use TLS for Production

```yaml
spec:
  tls:
  - hosts:
    - api.example.com
    secretName: api-tls
```

### 3. Set Resource Limits on Ingress Controller

```yaml
# Ingress Controller Deployment
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### 4. Configure Timeouts

```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-connect-timeout: "60"
  nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
  nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
```

### 5. Use Readiness Probes on Backends

```yaml
# Deployment
readinessProbe:
  httpGet:
    path: /health
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 5
```

**Why:** Ingress only routes to ready pods

### 6. Monitor Ingress Controller

**Metrics to monitor:**
- Request rate
- Error rate (4xx, 5xx)
- Response times
- Active connections

**NGINX Ingress exposes Prometheus metrics:**
```bash
kubectl port-forward -n ingress-nginx \
  svc/ingress-nginx-controller-metrics 10254:10254

curl http://localhost:10254/metrics
```

### 7. Configure Client Body Size Limit

```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-body-size: "10m"  # Max upload size
```

**Default:** 1m (1 megabyte)
**For file uploads:** Increase as needed

---

## 🔍 Debugging Commands

```bash
# Get Ingress
kubectl get ingress -n scenarios

# Describe Ingress (see events, rules)
kubectl describe ingress ingress-demo -n scenarios

# Get Ingress YAML
kubectl get ingress ingress-demo -n scenarios -o yaml

# Get Ingress Controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller

# Get Ingress Controller Service (find external IP)
kubectl get svc -n ingress-nginx

# Test Ingress routing
curl -H "Host: scenario-demo.local" http://<ingress-ip>/

# Check backend Service endpoints
kubectl get endpoints ingress-demo-service -n scenarios

# Verify Ingress Controller is running
kubectl get pods -n ingress-nginx

# Get IngressClasses
kubectl get ingressclass

# Check Ingress annotations
kubectl get ingress ingress-demo -n scenarios -o jsonpath='{.metadata.annotations}'
```

---

## 🚨 Common Issues & Solutions

### Issue 1: 404 Not Found

```bash
$ curl -H "Host: scenario-demo.local" http://<ingress-ip>/
<404 Not Found>
```

**Causes:**
1. Ingress not created
2. Wrong host header
3. Backend Service doesn't exist
4. Pods not ready

**Debug:**
```bash
kubectl get ingress -n scenarios
kubectl get svc ingress-demo-service -n scenarios
kubectl get pods -n scenarios -l app=ingress-demo
kubectl describe ingress ingress-demo -n scenarios
```

### Issue 2: Default Backend - 404

```bash
$ kubectl get ingress
NAME           CLASS   HOSTS                 ADDRESS
ingress-demo   nginx   scenario-demo.local   <none>
```

**Cause:** No IngressClass named "nginx" or Ingress Controller not installed

**Solution:**
```bash
# Check IngressClasses
kubectl get ingressclass

# Install NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
```

### Issue 3: TLS Certificate Invalid

**Cause:** Secret doesn't exist or wrong format

**Debug:**
```bash
kubectl get secret tls-secret -n scenarios
kubectl describe secret tls-secret -n scenarios
```

**Solution:**
```bash
# Create from files
kubectl create secret tls tls-secret \
  --cert=cert.crt \
  --key=key.key \
  -n scenarios
```

### Issue 4: Path not matching

**Example:**
```yaml
path: /api
pathType: Exact

Request: /api/users  → 404 (doesn't match exactly /api)
```

**Solution:** Use `Prefix` instead of `Exact`

---

## 🎓 Key Takeaways

1. **Ingress = Layer 7 routing** - Host and path-based routing for HTTP/HTTPS
2. **Ingress Controller required** - Install NGINX, Traefik, or other controller
3. **IngressClassName** - Always specify which controller to use
4. **Annotations** - Controller-specific configuration (check docs!)
5. **pathType matters** - Prefix vs Exact vs ImplementationSpecific
6. **Service must exist** - Backend service must be created first
7. **TLS termination** - Use Secrets for HTTPS certificates
8. **Single entry point** - Reduces cloud costs (1 LoadBalancer vs many)

---

*This explanation provides deep insights into Ingress for exposing HTTP/HTTPS services externally with advanced routing capabilities!*
