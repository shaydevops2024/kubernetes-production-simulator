# Main — Production Blue-Green Deployment on Kubernetes

This is the production phase. You'll deploy the DeployTrack application to Kubernetes using a proper blue-green strategy: automated health checks, Ingress-based traffic switching, a GitLab CI pipeline, rollback mechanism, and safe database migration handling.

This folder is **intentionally empty** — you build it. The guide below tells you exactly what to create and why.

---

## What You'll Build

```
main/
├── namespace.yaml
├── configmaps/
│   └── app-config.yaml
├── secrets/
│   └── db-secret.yaml
├── deployments/
│   ├── deployment-blue.yaml        ← v1, blue, 3 replicas
│   ├── deployment-green.yaml       ← v2, green, 3 replicas (starts at 0 until deploy)
│   └── job-db-migrate.yaml         ← Init migration Job (runs before switching)
├── services/
│   ├── service-blue.yaml           ← ClusterIP → blue pods
│   ├── service-green.yaml          ← ClusterIP → green pods
│   └── service-live.yaml           ← The live service (selector changes on switch)
├── ingress/
│   └── ingress.yaml                ← Routes external traffic to service-live
└── scripts/                        ← DevOps scripts you write
    ├── health-check.sh
    ├── smoke-tests.sh
    └── switch-traffic.sh
```

Check the `solution/` folder for complete, working versions of all these files.

---

## Phase 1 — Core Kubernetes Deployment

### Step 1 — Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: blue-green
  labels:
    app: deploytrack
```

```bash
kubectl apply -f namespace.yaml
```

---

### Step 2 — Secrets and ConfigMaps

**Secret** for the database password (never hardcode in manifests):

```bash
kubectl create secret generic db-secret \
  --namespace blue-green \
  --from-literal=POSTGRES_USER=deploytrack \
  --from-literal=POSTGRES_PASSWORD=deploypass \
  --from-literal=DATABASE_URL="postgresql://deploytrack:deploypass@postgres-svc:5432/deploytrack_db" \
  --dry-run=client -o yaml > secrets/db-secret.yaml
```

> **Production note:** Use Sealed Secrets or Vault for real credentials — never commit plain Secrets to git.

**ConfigMap** for non-sensitive config:

```yaml
# configmaps/app-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: blue-green
data:
  APP_ENV: "production"
  PORT: "5000"
```

---

### Step 3 — Deploy Blue (v1) — The Baseline

```yaml
# deployments/deployment-blue.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deploytrack-blue
  namespace: blue-green
  labels:
    app: deploytrack
    color: blue
    version: v1
spec:
  replicas: 3
  selector:
    matchLabels:
      app: deploytrack
      color: blue
  template:
    metadata:
      labels:
        app: deploytrack
        color: blue
        version: v1
    spec:
      containers:
      - name: deploytrack
        image: your-registry/deploytrack:v1      # change this
        ports:
        - containerPort: 5000
        env:
        - name: APP_COLOR
          value: "blue"
        - name: APP_VERSION
          value: "v1"
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: db-secret
        readinessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
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

---

### Step 4 — Services

**Three services** are the key to blue-green switching:

```yaml
# services/service-blue.yaml — routes to blue pods only
apiVersion: v1
kind: Service
metadata:
  name: deploytrack-blue
  namespace: blue-green
spec:
  selector:
    app: deploytrack
    color: blue
  ports:
  - port: 80
    targetPort: 5000

---
# services/service-green.yaml — routes to green pods only
apiVersion: v1
kind: Service
metadata:
  name: deploytrack-green
  namespace: blue-green
spec:
  selector:
    app: deploytrack
    color: green
  ports:
  - port: 80
    targetPort: 5000

---
# services/service-live.yaml — THE LIVE SERVICE
# This is what the Ingress points to. Switching here = traffic switch.
apiVersion: v1
kind: Service
metadata:
  name: deploytrack-live
  namespace: blue-green
spec:
  selector:
    app: deploytrack
    color: blue       # ← change this to "green" to switch traffic
  ports:
  - port: 80
    targetPort: 5000
```

**Why three services?**
- `deploytrack-blue` → test blue directly (bypasses live routing)
- `deploytrack-green` → test green directly before switching
- `deploytrack-live` → what users hit. You only change the selector here.

---

### Step 5 — Ingress

```yaml
# ingress/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: deploytrack-ingress
  namespace: blue-green
  annotations:
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "5"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "30"
spec:
  ingressClassName: nginx
  rules:
  - host: deploytrack.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: deploytrack-live     # ← always points to the live service
            port:
              number: 80
```

Apply all manifests:
```bash
kubectl apply -f namespace.yaml
kubectl apply -f secrets/
kubectl apply -f configmaps/
kubectl apply -f deployments/deployment-blue.yaml
kubectl apply -f services/
kubectl apply -f ingress/
```

Verify:
```bash
kubectl get pods -n blue-green
kubectl get svc -n blue-green
kubectl get ingress -n blue-green
```

---

## Phase 2 — Deploy Green (v2) Without Affecting Live

Green starts at 0 replicas. It's deployed and scaled up only when you're ready to test.

```yaml
# deployments/deployment-green.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deploytrack-green
  namespace: blue-green
  labels:
    app: deploytrack
    color: green
    version: v2
spec:
  replicas: 0    # ← start at 0 — scale up when ready
  selector:
    matchLabels:
      app: deploytrack
      color: green
  template:
    metadata:
      labels:
        app: deploytrack
        color: green
        version: v2
    spec:
      containers:
      - name: deploytrack
        image: your-registry/deploytrack:v2
        ports:
        - containerPort: 5000
        env:
        - name: APP_COLOR
          value: "green"
        - name: APP_VERSION
          value: "v2"
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: db-secret
        readinessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
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

Deploy it (at 0 replicas — no traffic yet):
```bash
kubectl apply -f deployments/deployment-green.yaml
```

Scale it up when ready to test:
```bash
kubectl scale deployment deploytrack-green --replicas=3 -n blue-green
kubectl rollout status deployment/deploytrack-green -n blue-green
```

---

## Phase 3 — Database Migration (Backward-Compatible)

Before switching traffic, run any schema migrations. The migration must be backward-compatible: the OLD code (blue/v1) must still work with the NEW schema.

**The rule:** Never add a NOT NULL column without a default. Never rename a column. Only add new columns.

```yaml
# deployments/job-db-migrate.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate-v2
  namespace: blue-green
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migrate
        image: your-registry/deploytrack:v2
        command: ["python", "-c", "
from main import Base, engine;
Base.metadata.create_all(bind=engine);
print('Migration complete')
"]
        envFrom:
        - secretRef:
            name: db-secret
  backoffLimit: 3
```

```bash
kubectl apply -f deployments/job-db-migrate.yaml
kubectl wait --for=condition=complete job/db-migrate-v2 -n blue-green --timeout=60s
```

---

## Phase 4 — Health Check Before Switching

**Never switch traffic to a version that isn't healthy.**

Write `scripts/health-check.sh`:

```bash
#!/bin/bash
set -euo pipefail

NAMESPACE=${1:-blue-green}
COLOR=${2:-green}
EXPECTED_REPLICAS=${3:-3}

echo "==> Checking $COLOR environment in namespace $NAMESPACE"

# 1. Check pods are running
READY=$(kubectl get deployment deploytrack-$COLOR -n $NAMESPACE \
  -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")

if [ "$READY" -lt "$EXPECTED_REPLICAS" ]; then
  echo "FAIL: Only $READY/$EXPECTED_REPLICAS pods ready"
  exit 1
fi
echo "OK: $READY/$EXPECTED_REPLICAS pods ready"

# 2. Hit health endpoint via service
POD=$(kubectl get pod -n $NAMESPACE -l "app=deploytrack,color=$COLOR" \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POD" ]; then
  echo "FAIL: No pod found for $COLOR"
  exit 1
fi

HEALTH=$(kubectl exec -n $NAMESPACE $POD -- \
  python -c "import urllib.request,json; \
  r=urllib.request.urlopen('http://localhost:5000/health'); \
  d=json.loads(r.read()); print(d['status'])")

if [ "$HEALTH" != "healthy" ]; then
  echo "FAIL: Health check returned: $HEALTH"
  exit 1
fi
echo "OK: Health check passed (status=$HEALTH)"

echo "==> $COLOR environment is healthy. Ready to receive traffic."
```

---

## Phase 5 — Smoke Tests

After switching, verify the live environment works as expected:

```bash
#!/bin/bash
# scripts/smoke-tests.sh

INGRESS_HOST=${1:-"deploytrack.local"}
EXPECTED_COLOR=${2:-"green"}
EXPECTED_VERSION=${3:-"v2"}

echo "==> Running smoke tests against $INGRESS_HOST"
echo "    Expected: color=$EXPECTED_COLOR, version=$EXPECTED_VERSION"

BASE_URL="http://$INGRESS_HOST"

# Test 1: Health endpoint
echo -n "Test 1 - /health ... "
RESP=$(curl -sf "$BASE_URL/health")
STATUS=$(echo $RESP | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])")
COLOR=$(echo $RESP  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['color'])")
if [ "$STATUS" != "healthy" ] || [ "$COLOR" != "$EXPECTED_COLOR" ]; then
  echo "FAIL (status=$STATUS, color=$COLOR)"
  exit 1
fi
echo "PASS"

# Test 2: Version endpoint
echo -n "Test 2 - /version ... "
VER=$(curl -sf "$BASE_URL/version" | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])")
if [ "$VER" != "$EXPECTED_VERSION" ]; then
  echo "FAIL (got $VER, expected $EXPECTED_VERSION)"
  exit 1
fi
echo "PASS"

# Test 3: API list
echo -n "Test 3 - GET /api/releases ... "
RELEASES=$(curl -sf "$BASE_URL/api/releases")
COUNT=$(echo $RELEASES | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
if [ "$COUNT" -lt "1" ]; then
  echo "FAIL (empty releases list)"
  exit 1
fi
echo "PASS ($COUNT releases)"

# Test 4: POST then GET
echo -n "Test 4 - POST /api/releases ... "
curl -sf -X POST "$BASE_URL/api/releases" \
  -H "Content-Type: application/json" \
  -d "{\"version\":\"smoke-test\",\"color\":\"$EXPECTED_COLOR\",\"environment\":\"production\",\"notes\":\"Smoke test\"}" > /dev/null
echo "PASS"

echo ""
echo "==> All smoke tests passed. $EXPECTED_COLOR/$EXPECTED_VERSION is live and working."
```

---

## Phase 6 — Traffic Switch

```bash
# scripts/switch-traffic.sh
#!/bin/bash
set -euo pipefail

TARGET=${1:-green}
NAMESPACE=${2:-blue-green}

echo "==> Switching live traffic to: $TARGET"

# Patch service-live selector
kubectl patch service deploytrack-live -n $NAMESPACE \
  --type='json' \
  -p="[{\"op\":\"replace\",\"path\":\"/spec/selector/color\",\"value\":\"$TARGET\"}]"

echo "OK: Traffic now routes to $TARGET"

# Verify
SELECTOR=$(kubectl get service deploytrack-live -n $NAMESPACE \
  -o jsonpath='{.spec.selector.color}')
echo "OK: service-live selector = $SELECTOR"
```

Usage:
```bash
# Switch to green
bash scripts/switch-traffic.sh green

# Roll back to blue
bash scripts/switch-traffic.sh blue
```

---

## Phase 7 — GitLab CI Pipeline

The pipeline automates the entire blue-green deployment flow.

See `solution/gitlab-ci/.gitlab-ci.yml` for the complete pipeline. Here's the high-level stages:

```
build → test → push → deploy-green → health-check → run-smoke-tests → switch-traffic → retire-blue
                                         │
                                         └─ (fails? auto-rollback, pipeline exits)
```

Each stage:

| Stage              | What it does                                              |
|--------------------|-----------------------------------------------------------|
| `build`            | `docker build` the new image (v2)                         |
| `test`             | Run unit tests inside the container                       |
| `push`             | Push image to registry                                    |
| `deploy-green`     | Scale up green deployment with new image                  |
| `health-check`     | Run `health-check.sh` — fails pipeline if unhealthy       |
| `run-smoke-tests`  | Run `smoke-tests.sh` against the green service (not live) |
| `switch-traffic`   | Patch `service-live` selector from blue → green           |
| `retire-blue`      | Scale blue to 0 replicas (it stays deployed for rollback) |

**Rollback:** Any failing stage triggers `switch-traffic.sh blue` before exiting.

---

## Phase 8 — Full Blue-Green Runbook

This is the sequence you (or CI) follows for every deployment:

```
1. Build new image → tag as v2
2. Push to registry
3. Apply deployment-green.yaml with new image
4. Scale green to 3 replicas
5. Wait for green pods to be ready (kubectl rollout status)
6. Run migration job
7. Run health-check.sh against green service (not live)
8. Run smoke-tests.sh against green service
9. Switch service-live selector: blue → green
10. Run smoke-tests.sh against live (ingress) to confirm
11. Scale blue to 0 replicas (keep deployment, just no traffic)

ROLLBACK (any step fails):
  - Switch service-live selector back to blue
  - Scale blue back to 3 (if it was scaled down)
  - Scale green to 0
  - Investigation window
```

---

## Verification Checklist

- [ ] Both blue and green deployments deployed
- [ ] All pods healthy (readinessProbe passing)
- [ ] `service-live` selector points to active color
- [ ] Ingress routes to `service-live`
- [ ] Health check script passes on green before switch
- [ ] Smoke tests pass after switch
- [ ] Rollback works by patching selector back to blue
- [ ] Database migration job completes before switch
- [ ] GitLab CI pipeline runs end-to-end
- [ ] `solution/` folder contains all working files

---

## Tools Installed Summary

| Tool | Purpose |
|------|---------|
| kubectl | Apply manifests, patch services, check pod health |
| Helm (optional) | Package the blue-green chart (see `solution/helm/`) |
| GitLab CI | Automate the full deployment pipeline |
| nginx Ingress | Route external traffic to service-live |

---

## Tips

- Start with blue only, get it working end-to-end before adding green
- Test health checks manually before writing the CI pipeline
- `kubectl patch` is your friend for quick service selector changes
- Keep blue running after the switch — rollback is instant as long as blue is alive
- Run `kubectl get endpoints deploytrack-live -n blue-green` to verify which pods the live service is pointing to
