# Local — Running the Developer Portal with Docker Compose

This is your first DevOps task: containerize and run the developer portal locally. You'll see the platform UI, explore the API, and understand what you're about to build on Kubernetes.

By the end you'll have:
- The Developer Portal running at **http://localhost:5454**
- A working self-service UI with teams, namespaces, services, pipelines, and cost tracking
- Hands-on experience with the API you'll later wire to real Kubernetes components

---

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose plugin)
- Port **5454** not in use

Verify:
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

Once you see the portal is healthy:
- **Developer Portal:** http://localhost:5454
- **API docs (Swagger):** http://localhost:5454/docs
- **Health check:** http://localhost:5454/health

---

## Architecture in docker-compose

```
Browser (http://localhost:5454)
        │
        ▼
   [portal — FastAPI:8000]   ← Port 5454 exposed to host
        │
        ├── /           → index.html (Portal UI)
        ├── /api/*      → REST endpoints (mock data)
        └── /static/*   → CSS, JS
```

In this local mode the portal uses hardcoded mock data. In the Kubernetes deployment (Phase 6 — Backstage), a real portal would connect to the live cluster APIs, Crossplane, Vault, and OpenCost.

---

## Useful Commands

```bash
# Start in detached mode (background)
docker compose up --build -d

# Check status
docker compose ps

# View logs
docker compose logs -f portal

# Stop everything
docker compose down

# Rebuild after code change
docker compose up --build
```

---

## DevOps Tasks for This Phase

### Task 1 — Explore the Portal

Open http://localhost:5454 and navigate through every section:
- **Dashboard** — overall platform health
- **Teams** — who owns what
- **Namespaces** — resource quotas and usage
- **Services** — what's running
- **Pipelines** — CI/CD status
- **Service Catalog** — deploy a new service (try the form!)
- **Costs** — per-team cost breakdown

**Question:** What data would you need to make each section live instead of mocked? For example, the Namespaces section would need a connection to `kubectl` or the Kubernetes API.

### Task 2 — Inspect the API

The portal has a full REST API. Explore it:
```bash
# Dashboard summary
curl http://localhost:5454/api/dashboard | python3 -m json.tool

# All teams
curl http://localhost:5454/api/teams | python3 -m json.tool

# Filter services by team
curl "http://localhost:5454/api/services?team_id=team-alpha" | python3 -m json.tool

# Full API documentation
open http://localhost:5454/docs
```

**Question:** The API returns JSON. How would you replace the mock data in `main.py` with real Kubernetes API calls using `kubectl` or the Python `kubernetes` client?

### Task 3 — Inspect the Container

```bash
# See what's running inside
docker compose exec portal ls /app
docker compose exec portal ls /app/static

# Check environment variables
docker compose exec portal env | grep PORT

# Check health check manually
docker compose exec portal python3 -c "
import urllib.request
r = urllib.request.urlopen('http://localhost:8000/health')
print(r.read().decode())
"
```

**Question:** The Dockerfile copies `static/` separately. Why might this matter for Docker layer caching?

### Task 4 — Test the Self-Service Features

The portal has two "write" operations. Try them:

**Deploy a service:**
```bash
curl -X POST http://localhost:5454/api/deploy \
  -H "Content-Type: application/json" \
  -d '{"service_name": "my-api", "team_id": "team-alpha", "template_id": "tpl-api", "replicas": 2}'
```

**Request a namespace:**
```bash
curl -X POST http://localhost:5454/api/namespaces/request \
  -H "Content-Type: application/json" \
  -d '{"team_name": "team-delta", "lead_email": "delta@company.com", "description": "New ML team", "cpu_limit": "4", "memory_limit": "8Gi"}'
```

Check the records were created:
```bash
curl http://localhost:5454/api/deploy | python3 -m json.tool
curl http://localhost:5454/api/namespaces/requests/list | python3 -m json.tool
```

**Question:** These requests are stored in memory. What happens when you restart the container? What would you need to persist them?

### Task 5 — Simulate a Restart

```bash
# Stop the container
docker compose stop portal

# Start it again
docker compose start portal

# Check if your deploy requests are still there
curl http://localhost:5454/api/deploy
```

**What did you notice?** The data is gone — it was stored only in memory. In the real platform, Crossplane would store namespace requests as Kubernetes CRDs, and Woodpecker would store pipeline runs in its own database.

### Task 6 — Inspect the Dockerfile

```bash
# Read the Dockerfile
cat ../app/portal/Dockerfile

# Check the image layers
docker history project-14-internal-paas-portal
```

**Improvement challenge:** The current Dockerfile runs as root. Add a non-root user:
```dockerfile
RUN adduser --disabled-password --no-create-home appuser
USER appuser
```

Where should this go in the Dockerfile? What constraints does it add?

---

## Common Issues

**Port 5454 already in use:**
```bash
lsof -i :5454
# Change the port in docker-compose.yml: "5455:8000" instead of "5454:8000"
```

**Build fails (pip install error):**
```bash
docker compose build --no-cache
```

---

## Next Step

Once you're comfortable with the portal, move on to [../main/README.md](../main/README.md) to build the full platform on Kubernetes.
