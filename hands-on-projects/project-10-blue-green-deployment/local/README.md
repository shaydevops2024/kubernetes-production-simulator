# Local — Blue-Green Deployment with Docker Compose

Your first DevOps task: run two identical environments side-by-side, manually switch traffic between them, and observe zero-downtime in action.

By the end of this step you'll have:
- Blue (v1) and Green (v2) running simultaneously
- nginx routing all "user" traffic to the active environment
- A working UI on http://localhost:4455 that visually shows which version is live
- The ability to switch from blue → green without dropping a single request

---

## Architecture

```
Browser (http://localhost:4455)
        │
        ▼
  [nginx — port 4455]         ← THE live entry point
        │
        │  (nginx.conf controls this routing)
        │
        ├──→ app-blue  (port 4456)   ← v1, blue theme,  port 4456 for direct access
        └──→ app-green (port 4457)   ← v2, green theme, port 4457 for direct access

        Both connect to:
        └──→ postgres (shared DB)    ← Same database — zero-downtime requires backward-compatible schema
```

**Key insight:** Blue and Green share the same database. When you deploy v2 (green), it must be able to read the same data that v1 (blue) wrote. This is the database migration challenge in zero-downtime deployments.

---

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose plugin)
- Ports 4455, 4456, 4457 not in use

Verify:
```bash
docker --version
docker compose version
```

---

## Run It

```bash
# From this directory (local/)
docker compose up --build
```

First build takes 2–3 minutes (building the app image twice, for blue and green).

Once all services are healthy:

| URL | What you see |
|-----|-------------|
| http://localhost:4455 | **LIVE** — blue (v1) by default |
| http://localhost:4456 | Blue directly (v1, bypass nginx) |
| http://localhost:4457 | Green directly (v2, bypass nginx) |

Open all three tabs. Notice:
- 4455 and 4456 look identical (both blue) — nginx is routing to blue
- 4457 is green with a different UI

---

## DevOps Tasks

### Task 1 — Understand the Architecture

```bash
# Check all running containers
docker compose ps

# What ports are exposed?
docker compose port nginx 80
docker compose port app-blue 5000
docker compose port app-green 5000

# Check the nginx config (which upstream is active?)
cat nginx/nginx.conf | grep -A5 "upstream active"
```

**Questions:**
- Why are both blue and green running at the same time?
- What would happen to users if you stopped blue BEFORE starting green?
- Why does nginx expose port 4455 but the apps expose 5000 internally?

---

### Task 2 — Verify Both Environments Are Healthy

Blue-green requires both environments to be healthy before switching.

```bash
# Check health endpoints directly
curl http://localhost:4456/health    # blue
curl http://localhost:4457/health    # green

# You should see:
# blue:  { "status": "healthy", "color": "blue",  "version": "v1" }
# green: { "status": "healthy", "color": "green", "version": "v2" }

# Check version endpoints
curl http://localhost:4456/version
curl http://localhost:4457/version
```

**Before any traffic switch:** Always confirm the new environment is healthy.

---

### Task 3 — Run Smoke Tests on Green (Before Switching)

Never switch traffic to a new environment without testing it first.

```bash
# Manual smoke test on green (it's not live yet, so safe to test)
curl -s http://localhost:4457/health | python3 -m json.tool
curl -s http://localhost:4457/version | python3 -m json.tool
curl -s http://localhost:4457/api/releases | python3 -m json.tool

# Post a test release to verify write operations work
curl -s -X POST http://localhost:4457/api/releases \
  -H "Content-Type: application/json" \
  -d '{"version": "v2-smoke-test", "color": "green", "environment": "staging", "notes": "Smoke test"}' \
  | python3 -m json.tool

# Verify the database is shared — the release you just wrote should appear in blue too
curl -s http://localhost:4456/api/releases | python3 -m json.tool
```

This proves the database is shared and backward-compatible.

---

### Task 4 — Switch Traffic from Blue to Green (The Cutover)

This is the core blue-green operation. nginx is the traffic router.

**Option A: Edit nginx.conf and reload**

Open `nginx/nginx.conf` and find the `upstream active` block:

```nginx
upstream active {
    server app-blue:5000;
    # server app-green:5000;   # ← switch here for blue→green cutover
}
```

Change it to:
```nginx
upstream active {
    # server app-blue:5000;
    server app-green:5000;   # ← green is now live
}
```

Then reload nginx **without restarting it** (zero-downtime nginx reload):
```bash
docker compose exec nginx nginx -s reload
```

**Verify the switch:**
```bash
# Open http://localhost:4455 — it should now show green/v2
# Or verify via curl:
curl -s http://localhost:4455/version
# Expected: { "version": "v2", "color": "green", ... }
```

**Option B: Use sed (one-liner)**
```bash
# Switch to green
sed -i 's/server app-blue:5000;/# server app-blue:5000;/' nginx/nginx.conf
sed -i 's/# server app-green:5000;/server app-green:5000;/' nginx/nginx.conf
docker compose exec nginx nginx -s reload

# Switch back to blue
sed -i 's/server app-green:5000;/# server app-green:5000;/' nginx/nginx.conf
sed -i 's/# server app-blue:5000;/server app-blue:5000;/' nginx/nginx.conf
docker compose exec nginx nginx -s reload
```

---

### Task 5 — Instant Rollback

The power of blue-green: rollback is instant because the old environment is still running.

```bash
# Something is wrong with green? Switch back to blue:
sed -i 's/server app-green:5000;/# server app-green:5000;/' nginx/nginx.conf
sed -i 's/# server app-blue:5000;/server app-blue:5000;/' nginx/nginx.conf
docker compose exec nginx nginx -s reload

# Rollback complete. No redeployment needed.
curl http://localhost:4455/version
# Expected: { "version": "v1", "color": "blue", ... }
```

Compare this with a traditional deployment rollback (redeploy previous image → wait for startup). With blue-green it's milliseconds.

---

### Task 6 — Simulate a Failed Deployment

```bash
# Make green unhealthy
docker compose stop app-green

# Check that live traffic still works (blue is still running)
curl http://localhost:4455/health
# Should still return healthy (nginx still routes to blue)

# If you had already switched to green, this is where you'd need the rollback
# Restart green to simulate recovery
docker compose start app-green
```

---

### Task 7 — Inspect Database Sharing

```bash
# Connect to the shared PostgreSQL
docker compose exec postgres psql -U deploytrack -d deploytrack_db

# List all tables
\dt

# Show releases (written by both blue and green)
SELECT version, color, environment, status, deployed_at FROM releases ORDER BY deployed_at DESC;

# Exit
\q
```

**Key observation:** Both blue and green read/write to the same database. The schema must be backward-compatible — v2 cannot require columns that break v1.

---

### Task 8 — Watch the Request Counter

Keep http://localhost:4455 open in a browser. Notice the "Requests Served" stat counter updates every 3 seconds. While you switch traffic from blue → green, the counter keeps incrementing — no interruption.

This is what "zero-downtime" means.

---

## Useful Commands

```bash
# Start (background)
docker compose up --build -d

# Check all containers
docker compose ps

# Follow logs for a specific service
docker compose logs -f app-green
docker compose logs -f nginx

# Reload nginx config (no restart, no dropped connections)
docker compose exec nginx nginx -s reload

# Check health of an environment
docker compose exec app-blue curl -s localhost:5000/health
docker compose exec app-green curl -s localhost:5000/health

# Scale: run 2 replicas of green for more capacity
docker compose up --scale app-green=2 -d

# Stop and clean up
docker compose down

# Stop and remove data too
docker compose down -v
```

---

## Common Issues

**Port 4455/4456/4457 already in use:**
```bash
lsof -i :4455
# Change ports in docker-compose.yml
```

**nginx fails to reload after config change:**
```bash
# Test nginx config first
docker compose exec nginx nginx -t
# If there's a syntax error, the config won't reload
```

**Green not healthy after startup:**
```bash
docker compose logs app-green
# Usually a database connection issue — wait for postgres healthcheck
```

---

## Next Step

Now that you understand blue-green locally, move to [../main/README.md](../main/README.md) to implement it properly in Kubernetes with automated health checks, GitLab CI, and a real rollback mechanism.
