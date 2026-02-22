# Local — Running the Full Stack with Docker Compose

This is your first DevOps task: get the entire SaaS platform running locally with Docker Compose.

By the end of this step you'll have:
- 3 PostgreSQL databases (platform, app, billing)
- 3 FastAPI services running in containers
- An nginx API gateway routing all traffic
- A working admin dashboard at http://localhost:8090

---

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose plugin)
- At least 4GB of free RAM
- Port 8090 not in use

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

First build downloads images and installs dependencies — takes 2–3 minutes.

Once all containers are healthy:
- **Admin Dashboard:** http://localhost:8090
- **Platform API docs:** http://localhost:8090/api/platform/docs
- **App Service docs:** http://localhost:8090/api/app/docs
- **Billing Service docs:** http://localhost:8090/api/billing/docs

---

## Architecture in docker-compose

```
Browser (http://localhost:8090)
        │
        ▼
   [gateway — nginx:80]          ← Port 8090 exposed to host
        │
        ├── /api/platform/*  ──→ platform-api:8010   ──→ postgres-platform
        │                           (tenant CRUD)
        │
        ├── /api/billing/*   ──→ billing-service:8012 ──→ postgres-billing
        │                           (metering)
        │
        ├── /api/app/*       ──→ app-service:8011     ──→ postgres-app
        │                           (tasks per tenant)
        │                           ↓ (records each call)
        │                       billing-service:8012
        │
        └── /               ──→ admin-ui:80
                                    (nginx serving HTML/JS)
```

**Key observation:** All tenants share a single `app-service` instance. Tenant isolation is enforced by the `X-Tenant-ID` HTTP header — every request must include it, and the service filters data by that value. This is **application-level multi-tenancy**.

---

## Useful Commands

```bash
# Start in detached mode (background)
docker compose up --build -d

# Check status of all containers
docker compose ps

# View logs for a specific service
docker compose logs -f platform-api
docker compose logs -f app-service
docker compose logs -f billing-service

# View logs for all services
docker compose logs -f

# Stop everything
docker compose down

# Stop and remove volumes (reset all data)
docker compose down -v

# Rebuild one service after a code change
docker compose up --build platform-api
```

---

## DevOps Tasks for This Phase

Now that it runs, explore what's happening:

### Task 1 — Inspect the Network
```bash
# List Docker networks created by compose
docker network ls

# Inspect the compose network — which IPs are assigned?
docker network inspect local_default

# Can platform-api reach billing-service by hostname?
docker compose exec platform-api ping billing-service -c 3

# Can app-service reach billing-service?
docker compose exec app-service ping billing-service -c 3
```

**Question:** How do containers know each other's hostnames? Where does DNS resolution happen inside Docker?

### Task 2 — Explore Tenant Isolation
```bash
# List tasks for alice-corp
curl -s http://localhost:8090/api/app/tasks \
  -H "X-Tenant-ID: alice-corp" | python3 -m json.tool

# List tasks for bob-industries
curl -s http://localhost:8090/api/app/tasks \
  -H "X-Tenant-ID: bob-industries" | python3 -m json.tool

# Try without the header — what happens?
curl -s http://localhost:8090/api/app/tasks
```

**Question:** What prevents Alice from accessing Bob's tasks? Could she fake the header? What would you need to add to make this more secure?

### Task 3 — Create and Suspend a Tenant
```bash
# Create a new tenant
curl -s -X POST http://localhost:8090/api/platform/tenants \
  -H "Content-Type: application/json" \
  -d '{"name":"Delta Corp","plan":"pro","contact_email":"admin@delta.com"}' \
  | python3 -m json.tool

# Suspend alice-corp (grab the id from the previous response)
curl -s -X PATCH http://localhost:8090/api/platform/tenants/<ID>/suspend

# Confirm alice is now suspended
curl -s http://localhost:8090/api/platform/tenants | python3 -m json.tool
```

**Question:** In production, what should happen to Alice's running workloads when you suspend them? What K8s resource would you use to stop a tenant's pods without deleting them?

### Task 4 — Inspect the Databases
```bash
# Look at the tenants table in platform-api's DB
docker compose exec postgres-platform psql -U saas -d platform_db
\dt                            # list tables
SELECT id, name, slug, plan, status FROM tenants;
\q

# Look at the tasks table — note tenant_id column
docker compose exec postgres-app psql -U saas -d app_db
SELECT tenant_id, count(*) FROM tasks GROUP BY tenant_id;
\q

# Look at billing events
docker compose exec postgres-billing psql -U saas -d billing_db
SELECT tenant_id, count(*) as total, date(timestamp) as day
  FROM usage_events
  GROUP BY tenant_id, date(timestamp)
  ORDER BY day DESC, total DESC;
\q
```

**Question:** All tenants share one `tasks` table, separated only by `tenant_id`. What could go wrong? What would you need to add to prevent a buggy query from leaking data across tenants?

### Task 5 — Inspect Billing
```bash
# Get usage for all tenants
curl -s http://localhost:8090/api/billing/usage | python3 -m json.tool

# Get detailed breakdown for alice-corp
curl -s http://localhost:8090/api/billing/usage/alice-corp | python3 -m json.tool

# Create a few tasks and watch the counts increase
curl -s -X POST http://localhost:8090/api/app/tasks \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: alice-corp" \
  -d '{"title":"New task","priority":"high"}'

curl -s http://localhost:8090/api/billing/usage/alice-corp | python3 -m json.tool
```

**Question:** The billing-service is called fire-and-forget (app-service doesn't wait for it). What are the trade-offs of this approach? What happens if billing-service is down?

### Task 6 — Simulate a Failure
```bash
# Stop the billing service
docker compose stop billing-service

# Try creating a task — does it still work?
curl -s -X POST http://localhost:8090/api/app/tasks \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: alice-corp" \
  -d '{"title":"Task while billing is down","priority":"low"}'

# Bring billing back
docker compose start billing-service
```

**Question:** The task was created successfully even though billing was down. Is this the right behaviour? What are the alternatives? How would you handle this in a financial-critical system?

---

## Common Issues

**Port 8090 already in use:**
```bash
lsof -i :8090
# Change the port in docker-compose.yml: "8091:80" instead of "8090:80"
```

**Database not ready — service crashes on startup:**
The `depends_on` + healthchecks handle this. If you still see errors, give it 30 seconds and re-check `docker compose ps`.

**Permission errors on Linux:**
```bash
sudo chmod 666 /var/run/docker.sock
```

---

## Next Step

Once you're comfortable with how the local stack works, move on to **[../main/README.md](../main/README.md)** to deploy this to Kubernetes with proper tenant isolation at the infrastructure level.
