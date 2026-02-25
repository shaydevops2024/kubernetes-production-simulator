# Local — Docker Compose

Run the entire serverless platform on your machine with a single command. No Kubernetes needed yet.

---

## Start

```bash
cd local/
docker compose up --build
```

Then open: **http://localhost:3000**

---

## What Runs

| Container | Port | URL |
|-----------|------|-----|
| `faashub-runner` | 8002 | http://localhost:8002/docs |
| `faashub-service` | 8001 | http://localhost:8001/docs |
| `faashub-frontend` | 3000 | http://localhost:3000 |

The frontend proxies `/api/*` → `function-service:8001` via nginx. You interact with the UI at port 3000, never directly with the backend.

---

## Network Diagram

```
Your Browser
    │
    ▼ :3000
┌───────────────────────────────┐
│  frontend (nginx)             │
│  - serves static files        │
│  - /api/* → function-service  │
└──────────────┬────────────────┘
               │ :8001 (internal)
               ▼
┌──────────────────────────────────────────┐
│  function-service                        │
│  - GET  /functions  (registry)           │
│  - GET  /stats      (metrics)            │
│  - POST /functions/{name}/invoke (proxy) │
└──────────────┬───────────────────────────┘
               │ :8002 (internal)
               ▼
┌──────────────────────────────────────────┐
│  function-runner                         │
│  - POST /run/{name}  (executes fn)       │
└──────────────────────────────────────────┘
```

Docker Compose creates a shared network (`faashub-network`) so containers resolve each other by service name (e.g., `function-runner` resolves to the runner container). In Kubernetes, this becomes **Service DNS** — exactly the same concept.

---

## DevOps Tasks — Phase 2

### Task 1 — Read the Compose file

Open `docker-compose.yml` and answer:
- Why does `function-service` have `depends_on: function-runner`?
- What does `condition: service_healthy` mean vs just `depends_on: function-runner`?
- Why is `FUNCTION_RUNNER_URL=http://function-runner:8002` and not `http://localhost:8002`?
- What network does Docker Compose create? Run `docker network ls` to verify.

### Task 2 — Inspect the running containers

```bash
# List running containers
docker compose ps

# View logs for all containers
docker compose logs -f

# View logs for a specific service
docker compose logs -f function-service

# Inspect the network
docker network inspect faashub-network

# See what ports are exposed
docker compose port frontend 80
```

### Task 3 — Test the API directly

```bash
# List all functions
curl http://localhost:8001/functions | python3 -m json.tool

# Invoke hello-world
curl -X POST http://localhost:8001/functions/hello-world/invoke \
  -H "Content-Type: application/json" \
  -d '{"payload": {"name": "DevOps"}}'

# Invoke fibonacci (CPU-bound)
curl -X POST http://localhost:8001/functions/fibonacci/invoke \
  -H "Content-Type: application/json" \
  -d '{"payload": {"n": 40}}'

# Get stats
curl http://localhost:8001/stats | python3 -m json.tool
```

### Task 4 — Build images manually

Instead of letting Compose build for you, build and tag them yourself:

```bash
docker build -t faashub/function-runner:v1 ../app/function-runner/
docker build -t faashub/function-service:v1 ../app/function-service/
docker build -t faashub/frontend:v1 ../app/frontend/

# Check image sizes
docker images | grep faashub

# Push to Docker Hub (replace with your username)
docker tag faashub/function-runner:v1 <your-dockerhub>/function-runner:v1
docker push <your-dockerhub>/function-runner:v1
```

You'll need those pushed images in Phase 3 when Kubernetes pulls them.

### Task 5 — Simulate a cold start

```bash
# Stop just the runner
docker compose stop function-runner

# Trigger a function — you'll get a 503 (runner is down)
curl -X POST http://localhost:8001/functions/hello-world/invoke \
  -H "Content-Type: application/json" \
  -d '{"payload": {"name": "test"}}'

# Start the runner back up — observe startup time
docker compose start function-runner
docker compose logs -f function-runner
```

This is the Docker equivalent of a cold start — what happens in Kubernetes when a pod scales from zero and takes time to become Ready.

### Task 6 — Scale the runner manually

```bash
# Run 3 runner replicas
docker compose up --scale function-runner=3 -d

# Check containers
docker compose ps

# Note: Compose load-balances round-robin between replicas automatically
# In Kubernetes, a Service does the same — but with health-based routing
```

---

## Tear Down

```bash
docker compose down

# Remove images too
docker compose down --rmi all
```

---

## Common Issues

| Problem | Fix |
|---------|-----|
| Port 3000 in use | Edit `docker-compose.yml`, change `"3000:80"` to `"3001:80"` |
| Port 8001/8002 in use | Same — change the host port (left side of `:`) |
| Image build fails | Run `docker compose build --no-cache` to rebuild from scratch |
| Health check fails | Run `docker compose logs function-runner` to see startup errors |

---

**→ Go to [../main/README.md](../main/README.md) when you're ready to deploy to Kubernetes**
