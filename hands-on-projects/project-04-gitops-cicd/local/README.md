# Local — Simulating a Canary Deployment with Docker Compose

This is your first DevOps task: run **two versions of the app simultaneously** with nginx splitting traffic between them — exactly like Flagger does in Kubernetes.

By the end of this step you'll have:
- app-v1 running (stable, blue theme)
- app-v2 running (canary, green theme)
- nginx load balancer splitting traffic 90% → v1, 10% → v2
- A live demo of canary deployments you can observe in your browser

---

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose plugin)
- Port 8181 not in use

```bash
docker --version        # Docker version 24+
docker compose version  # Docker Compose version v2+
```

---

## Run It

```bash
# From this directory (local/)
docker compose up --build
```

Once both services are healthy:
- **UI:** http://localhost:8181
- **v1 health:** Handled by load balancer (not exposed directly)
- **v2 health:** Handled by load balancer (not exposed directly)

Refresh http://localhost:8181 several times — about 1 in 5 requests will show the **v2 green theme** with version `V2` in the header.

---

## Architecture

```
Browser (http://localhost:8181)
        │
        ▼
   [gateway — nginx:80]     ← Port 8181 exposed to host
        │
        │  weight=9   ──────→ app-v1:8080   (stable, blue)
        │  weight=1   ──────→ app-v2:8080   (canary, green)
        │
        └── Traffic split: 90% v1, 10% v2
```

This mirrors what Flagger does when it starts a canary analysis:
- `app-v1` = the **primary** (stable) deployment
- `app-v2` = the **canary** deployment receiving a small traffic slice
- nginx = the **traffic policy** (Flagger uses Istio or NGINX Ingress in K8s)

---

## Useful Commands

```bash
# Start in detached mode
docker compose up --build -d

# Check all containers
docker compose ps

# View logs for each version
docker compose logs -f app-v1
docker compose logs -f app-v2
docker compose logs -f gateway

# Stop everything
docker compose down

# Rebuild after a code change
docker compose up --build app-v1
```

---

## DevOps Tasks for This Phase

### Task 1 — Observe the Canary Split

```bash
# Send 20 requests and count which version responds
for i in $(seq 1 20); do
  curl -s http://localhost:8181/api/version | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['version'])"
done
```

You should see roughly 18× `v1` and 2× `v2`.

**Question:** What controls the split? Where would you change it to 50/50?

---

### Task 2 — Inspect the nginx Load Balancer

```bash
# Check response headers — nginx adds upstream info
curl -I http://localhost:8181

# Look for these headers:
#   X-Upstream-Addr:   which container handled the request
#   X-Upstream-Status: HTTP status from upstream
```

Open `nginx/nginx.conf` and understand the `upstream` block with `weight`.

**Question:** How does nginx distribute requests with weights? Is it random or round-robin?

---

### Task 3 — Change the Traffic Split to 50/50

Edit `nginx/nginx.conf`:
```nginx
upstream app_canary {
    server app-v1:8080 weight=1;   # was 9
    server app-v2:8080 weight=1;   # was 1
}
```

Reload nginx without restarting:
```bash
docker compose exec gateway nginx -s reload
```

Run the version check loop again. Does the split match 50/50?

---

### Task 4 — Simulate a Failing Canary

Stop v2 to simulate a bad deployment:
```bash
docker compose stop app-v2
```

What happens when nginx tries to route to v2? What HTTP status do users see?

```bash
# Check error handling
curl -v http://localhost:8181/api/version
```

Bring v2 back:
```bash
docker compose start app-v2
```

**Question:** In Kubernetes, Flagger monitors success rate and latency. If v2 started returning 500s, what should the pipeline do? (Hint: that's the rollback trigger.)

---

### Task 5 — Promote v2 to 100%

Change the weights to complete the canary:
```nginx
upstream app_canary {
    server app-v1:8080 weight=0;   # drain v1 (nginx ignores weight=0)
    server app-v2:8080 weight=1;   # 100% to v2
}
```

> Note: nginx doesn't support `weight=0`. To fully drain v1, remove it from the upstream or comment it out. This is exactly why Flagger/Kubernetes has a more sophisticated traffic management system.

**Question:** What's the difference between how nginx handles this vs. how Flagger handles full promotion?

---

### Task 6 — Build a v2 Image Yourself

Simulate what the CI pipeline does:

```bash
# Build v2 image with version metadata
docker build \
  --build-arg APP_VERSION=v2 \
  --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --build-arg GIT_COMMIT=mycommit123 \
  -t projects-hub:v2 \
  ../app

# Run it standalone
docker run -p 9090:8080 projects-hub:v2

# Check the version
curl http://localhost:9090/api/version
```

**Question:** What CI platform steps would produce this `docker build` command? Look at the `--build-arg` flags — where does each value come from in a real pipeline?

---

## Common Issues

**Port 8181 already in use:**
```bash
lsof -i :8181
# Change the port in docker-compose.yml: "8182:80" instead of "8181:80"
```

**Health check fails on startup:**
The apps take a few seconds to start. If you see health failures, wait 15 seconds and run `docker compose ps` again.

**nginx returns 502 Bad Gateway:**
One of the app containers is unhealthy. Check: `docker compose logs app-v1` or `docker compose logs app-v2`.

---

## Next Step

Once you're comfortable with the canary simulation, move on to [../main/README.md](../main/README.md) to deploy this to Kubernetes with real GitOps tooling.
