# Project 10 — Blue-Green Deployment: Explained

---

## 1. The App

You are implementing a **blue-green deployment system** using a pre-built application called **DeployTrack** — a FastAPI deployment tracking dashboard that visually shows which version (blue/green) is currently serving traffic.

The key idea: you always keep two identical environments running. One is "live" (serving users), one is on "standby" (your new version). To deploy, you switch traffic — instantly. To roll back, you switch back — also instantly. No users experience downtime at any point.

```
              Users
                │
                ▼
    ┌─────────────────────┐
    │   nginx / K8s Ingress│   ← single entry point
    └──────────┬──────────┘
               │ (service selector picks one)
           ┌───┴───┐
           │       │
       ┌───▼──┐ ┌──▼───┐
       │ BLUE │ │ GREEN│   ← both always running
       │  v1  │ │  v2  │
       │ :3   │ │ :3   │
       └───┬──┘ └──┬───┘
           └───┬───┘
               ▼
       ┌───────────────┐
       │  PostgreSQL   │   ← shared database
       └───────────────┘
```

**DeployTrack** makes the deployment strategy visible: each version renders in a different color (blue vs green) and shows its version number and environment name prominently. When you switch traffic, refreshing the browser switches colors instantly.

| Feature | What it demonstrates |
|---------|---------------------|
| Color-coded UI (blue/green) | Visual confirmation of which version is live |
| Version number display | You can see v1 vs v2 clearly |
| Deployment history log | App records each deployment event in the shared DB |
| Health endpoint | Ready for readiness probes and traffic switch automation |

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-10-blue-green-deployment/local/

docker compose up --build
```

The compose file runs both blue and green simultaneously, with nginx routing to only one:

| Service | URL (direct, bypass nginx) |
|---------|-----------------------------|
| NGINX (active traffic) | http://localhost:8080 |
| Blue environment | http://localhost:8081 |
| Green environment | http://localhost:8082 |

**Switch traffic from blue to green:**
```bash
# Edit nginx.conf to point to green
# In local/nginx/nginx.conf, change:
#   proxy_pass http://blue:8000;
# to:
#   proxy_pass http://green:8000;

# Reload nginx without restart (zero downtime config reload)
docker compose exec nginx nginx -s reload

# Verify — refresh http://localhost:8080
# Should now show green UI
```

**Rollback (switch back to blue):**
```bash
# Revert nginx.conf
# Reload
docker compose exec nginx nginx -s reload
# Instant rollback — green is still running, just not receiving traffic
```

### Phase 2 — Deploy to Kubernetes

```bash
cd hands-on-projects/project-10-blue-green-deployment/main/

# Namespace and shared database
kubectl apply -f solution/k8s/namespace/

# Deploy BLUE (v1) — set as live
kubectl apply -f solution/k8s/blue/

# Deploy GREEN (v2) — on standby, not receiving traffic
kubectl apply -f solution/k8s/green/

# Verify both are running
kubectl get pods -n blue-green

# The Service currently points to BLUE
kubectl get svc -n blue-green deploytrack -o yaml | grep selector
```

**Switch traffic to GREEN in Kubernetes:**
```bash
# Change service selector from blue to green
kubectl patch svc deploytrack -n blue-green \
  -p '{"spec":{"selector":{"version":"green"}}}'

# Verify traffic switched (check the live UI)
kubectl get svc deploytrack -n blue-green -o yaml | grep version

# Rollback is equally instant
kubectl patch svc deploytrack -n blue-green \
  -p '{"spec":{"selector":{"version":"blue"}}}'
```

---

## 3. How to Test It

### Verify Both Environments Are Running

```bash
# Local
docker compose ps
# blue, green, postgres, nginx should all be Up

# K8s
kubectl get pods -n blue-green
# blue-pod-xxx and green-pod-xxx should both be Running
```

### Traffic Switch Test (Local)

```bash
# Watch which version is responding before and after switch
watch -n0.5 'curl -s http://localhost:8080/api/version | jq .version'

# In another terminal, switch nginx to green
docker compose exec nginx nginx -s reload

# The watch should instantly switch from "v1" to "v2"
```

### Traffic Switch Test (Kubernetes)

```bash
# Watch version in real time
watch -n0.5 'curl -s http://localhost/api/version | jq .version'

# Switch the service selector
kubectl patch svc deploytrack -n blue-green \
  -p '{"spec":{"selector":{"version":"green"}}}'

# Observe: no dropped requests, instant switch
```

### Zero-Downtime Verification

```bash
# Run continuous requests during the switch
for i in {1..1000}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/)
  echo "Request $i: $STATUS"
done &

# While that's running, switch traffic
docker compose exec nginx nginx -s reload

# Check output — should see all 200s with no gaps
```

### Shared Database Integrity Test

```bash
# Create data as blue (v1)
curl -X POST http://localhost:8081/api/deployments \
  -H "Content-Type: application/json" \
  -d '{"version": "v1", "environment": "blue", "deployed_by": "alice"}'

# Switch to green
docker compose exec nginx nginx -s reload

# Verify green can see the same data (shared DB)
curl http://localhost:8080/api/deployments
# Should return the deployment created by blue
```

### Health Check Test

```bash
# Verify both environments pass health checks
curl http://localhost:8081/health  # blue
curl http://localhost:8082/health  # green

# In K8s: verify readiness probes pass before switching
kubectl describe pod -n blue-green -l version=green | grep -A5 Readiness
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **NGINX** | Traffic router (local) | `proxy_pass` in nginx.conf points to blue or green; `nginx -s reload` switches |
| **Kubernetes Service** | Traffic router (K8s) | Label selector (`version: blue` or `version: green`) determines which pods get traffic |
| **Docker Compose** | Local simulation | Runs both environments plus nginx and postgres simultaneously |
| **kubectl patch** | Traffic switching (K8s) | Updates Service selector to switch between blue and green in milliseconds |
| **PostgreSQL** | Shared database | Both blue and green connect to the same DB — data is shared across versions |
| **FastAPI** | Application framework | DeployTrack backend — serves the UI and deployment tracking API |

### Key Blue-Green Concepts Practiced

- **Immutable deployments**: Never update a running environment — always deploy to the idle one
- **Traffic switching at the load balancer layer**: The Service/nginx is what changes, not the pods
- **Instant rollback**: The old version never stopped running — just switch the pointer back
- **Shared database caveat**: Both versions must be DB-schema compatible during the switch window
- **Readiness probes**: Verify the standby is healthy before switching traffic to it

---

## 5. Troubleshooting

### nginx not switching traffic after config change

```bash
# Verify the config was modified correctly
docker compose exec nginx cat /etc/nginx/nginx.conf | grep proxy_pass

# Test nginx config syntax before reload
docker compose exec nginx nginx -t

# If syntax OK, reload
docker compose exec nginx nginx -s reload

# Check nginx logs
docker compose logs nginx | tail -20
```

### Kubernetes Service not routing to new version

```bash
# Check selector is correct
kubectl get svc deploytrack -n blue-green -o yaml | grep -A5 selector

# Verify pods have the right labels
kubectl get pods -n blue-green --show-labels
# Green pods should have: version=green

# Test by port-forwarding directly to a pod
kubectl port-forward -n blue-green pod/green-xxx 9999:8000
curl http://localhost:9999/api/version
```

### Green environment crashing on startup

```bash
# Check green pod logs
kubectl logs -n blue-green -l version=green --previous

# Check DB migrations — green (v2) might need a schema migration
kubectl exec -n blue-green -l version=green -- \
  python -c "from main import app; print('startup ok')"

# Common fix: run DB migration before switching traffic
kubectl exec -n blue-green -l version=green -- \
  python manage.py migrate
```

### Database schema incompatibility between blue and green

```bash
# This is the hardest blue-green challenge
# If v2 adds a NOT NULL column, v1 will fail to write to it
# Solution: multi-phase migration
# Phase 1: Add column as nullable → deploy green → switch traffic
# Phase 2: Backfill + make NOT NULL → deploy blue-updated

# Check current schema
kubectl exec -n blue-green postgres-0 -- \
  psql -U dt -d deploytrack -c "\d deployments"
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-10-blue-green-deployment/local/

# Stop all containers
docker compose down

# Full reset including database
docker compose down -v
```

### Kubernetes

```bash
# Delete the namespace (removes everything)
kubectl delete namespace blue-green
```
