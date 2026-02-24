# GatewayHub — Local Setup (Docker Compose)

Run the full GatewayHub stack locally with Docker Compose before deploying to Kubernetes.
This setup gives you Kong API Gateway, a FastAPI backend, an analytics service, a frontend
dashboard, PostgreSQL, and Redis — all wired together in a single `docker compose up`.

---

## What You'll Run

```
                     ┌─────────────────────────────────────────────┐
                     │            Docker Compose Network            │
                     │                                              │
  Browser ──────────►│  frontend :80 (host: 3000)                  │
                     │      │                                       │
                     │      └── calls Kong proxy                    │
                     │                                              │
  curl / frontend ──►│  kong :8000 (host: 8888)  ◄── proxy         │
                     │      │                                       │
                     │      ├──► api-service :8001                  │
                     │      │        │                              │
                     │      │        └──► postgres :5432            │
                     │      │                                       │
                     │      └──► analytics-service :8002            │
                     │               │                              │
                     │               └──► kong admin :8001          │
                     │                                              │
                     │  kong admin :8001 (host: 8081)  ◄── admin    │
                     │                                              │
                     │  redis :6379  ◄── Kong rate-limit backend    │
                     └─────────────────────────────────────────────┘
```

| Entry Point | Host Port | Purpose |
|---|---|---|
| Frontend UI | http://localhost:3000 | Web dashboard |
| Kong Proxy | http://localhost:8888 | All API traffic goes here |
| Kong Admin | http://localhost:8081 | Inspect Kong config & stats |

---

## Quick Start

### Step 1: Navigate to this directory and start the stack

```bash
cd hands-on-projects/project-06-api-gateway/local

docker compose up --build
```

The `--build` flag builds the three custom images (api-service, analytics-service, frontend)
before starting. You only need `--build` on first run or after code changes.

To run in the background:

```bash
docker compose up --build -d
```

### Step 2: Wait for all services to become healthy

Kong takes about 30 seconds to initialize. Watch the health status:

```bash
# In a second terminal — poll until all services show "healthy"
watch -n 2 docker compose ps

# Or check once
docker compose ps
```

Expected output when ready:

```
NAME                  STATUS
local-postgres-1      running (healthy)
local-redis-1         running (healthy)
local-api-service-1   running (healthy)
local-kong-1          running (healthy)
local-analytics-service-1  running (healthy)
local-frontend-1      running
```

Verify Kong is accepting traffic:

```bash
curl -s http://localhost:8888/health | python3 -m json.tool
```

Verify Kong Admin is reachable:

```bash
curl -s http://localhost:8081/ | python3 -m json.tool
```

### Step 3: Open the UI

Navigate to **http://localhost:3000** in your browser. You should see the GatewayHub
dashboard showing live service status, request metrics, and rate limit information.

---

## Your DevOps Tasks

Work through these tasks in order. Each one builds on the previous.

---

### Task 1: Understand the Stack

Before touching the API, understand what is running and how it is wired together.

```bash
# See all running containers and their health
docker compose ps

# View Kong startup logs — note the config it loaded
docker compose logs kong

# View API service logs
docker compose logs api-service

# Follow logs from all services simultaneously
docker compose logs -f

# Inspect the Kong declarative config Kong actually loaded
curl -s http://localhost:8081/config | python3 -m json.tool | head -80

# List all services Kong knows about
curl -s http://localhost:8081/services | python3 -m json.tool

# List all routes
curl -s http://localhost:8081/routes | python3 -m json.tool

# List all plugins (global + per-route)
curl -s http://localhost:8081/plugins | python3 -m json.tool
```

Questions to answer:
- How many services does Kong proxy to?
- Which routes require JWT authentication?
- Which routes have rate limiting enabled?
- What is the global rate limit policy for `/v1/products`?

---

### Task 2: Test the API Gateway (curl commands)

Run these commands in order to walk through the full API surface.

#### 1. Health check through Kong

```bash
curl -s http://localhost:8888/health | python3 -m json.tool
```

This hits Kong proxy on port 8888, which forwards to `api-service:8001/health`.
Notice the response headers Kong adds (check with `-v`):

```bash
curl -sv http://localhost:8888/health 2>&1 | grep -E "^[<>]"
```

Look for: `X-Gateway`, `X-Environment`, `X-Kong-Upstream-Latency`, `X-Kong-Proxy-Latency`.

#### 2. List products (public, rate limited — no auth needed)

```bash
curl -s http://localhost:8888/v1/products | python3 -m json.tool
```

Check the rate limit headers in the response:

```bash
curl -sv http://localhost:8888/v1/products 2>&1 | grep -i "ratelimit"
```

You should see:
- `X-RateLimit-Limit-minute: 10`
- `X-RateLimit-Remaining-minute: 9`

#### 3. Get a JWT token

The API service issues JWT tokens. Authenticate as one of the demo users:

```bash
# Get a token for alice (premium user)
TOKEN=$(curl -s -X POST http://localhost:8888/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "any-password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: $TOKEN"
```

Decode the token to inspect its claims (no verification, just decoding):

```bash
echo $TOKEN | cut -d'.' -f2 | base64 -d 2>/dev/null | python3 -m json.tool
```

Note the `iss` claim — Kong uses this to look up the consumer.

#### 4. Use JWT to access a protected endpoint

```bash
# List users — requires JWT
curl -s http://localhost:8888/v1/users \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# List orders — requires JWT
curl -s http://localhost:8888/v1/orders \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Without the token:

```bash
curl -s http://localhost:8888/v1/users
# Expected: {"message":"Unauthorized"}  with HTTP 401
```

#### 5. Access the v2 API (enhanced response)

```bash
# v2 returns enriched product data
curl -s http://localhost:8888/v2/products \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Check the enhanced headers Kong injects for v2:

```bash
curl -sv http://localhost:8888/v2/products \
  -H "Authorization: Bearer $TOKEN" 2>&1 | grep -E "X-API-Version|X-Enhanced"
```

You should see `X-API-Version: 2.0` and `X-Enhanced-Response: true` — injected by the
`request-transformer` plugin on the `api-v2` route.

#### 6. Hit the rate limit

Send 11 requests to `/v1/products` (limit is 10 per minute):

```bash
for i in $(seq 1 12); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/v1/products)
  echo "Request $i: HTTP $STATUS"
done
```

After 10 requests you should see `HTTP 429` with the message:
"Rate limit exceeded. You have sent too many requests. Please wait a minute."

---

### Task 3: Explore Kong Admin API

The Kong Admin API (port 8081) gives you full visibility into the gateway state.

```bash
# View all services with their upstream URLs
curl -s http://localhost:8081/services | \
  python3 -c "import sys,json; [print(s['name'], '->', s['url']) for s in json.load(sys.stdin)['data']]"

# View all routes with their paths
curl -s http://localhost:8081/routes | \
  python3 -c "import sys,json; [print(r['name'], r.get('paths')) for r in json.load(sys.stdin)['data']]"

# View all plugins (shows both global and route-level)
curl -s http://localhost:8081/plugins | \
  python3 -c "import sys,json; [print(p['name'], '| route:', p.get('route'), '| enabled:', p['enabled']) for p in json.load(sys.stdin)['data']]"

# View all consumers
curl -s http://localhost:8081/consumers | python3 -m json.tool

# View JWT credentials for the demo-user consumer
curl -s http://localhost:8081/consumers/demo-user/jwt | python3 -m json.tool

# View rate limit counters stored in Redis via the Admin API
curl -s "http://localhost:8081/plugins?name=rate-limiting" | python3 -m json.tool
```

---

### Task 4: Watch Rate Limiting in Action

This task makes the rate limiting behavior concrete by watching counters increment in Redis.

Open two terminal windows side by side.

**Terminal 1 — watch Redis counters:**

```bash
# Connect to Redis and watch rate limit keys refresh every 2 seconds
docker compose exec redis redis-cli --no-auth-warning

# Inside redis-cli, run:
KEYS RateLimit:*
```

**Terminal 2 — send requests:**

```bash
# Send 5 requests to the products endpoint
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "Request $i: HTTP %{http_code} | Remaining: %header{x-ratelimit-remaining-minute}\n" \
    http://localhost:8888/v1/products
  sleep 0.5
done
```

Back in Terminal 1, after each request run `KEYS RateLimit:*` and `GET` on one of the keys
to see the counter value increment. The keys expire at the end of each minute window.

```bash
# Inside redis-cli:
KEYS RateLimit:*
# Example key: RateLimit:api-v1-products-public:127.0.0.1:1700000000:minute

# Get the current counter value
GET RateLimit:api-v1-products-public:127.0.0.1:1700000000:minute

# See the TTL (seconds until the window resets)
TTL RateLimit:api-v1-products-public:127.0.0.1:1700000000:minute
```

---

### Task 5: Modify Kong Configuration

Kong in DB-less mode reads its config from `kong/kong.yml`. Changes require a restart,
but only Kong needs to restart — not the other services.

**Change the public products rate limit from 10 to 5 requests per minute:**

1. Open `kong/kong.yml` in your editor.

2. Find the `api-v1-products-public` route's rate-limiting plugin:

```yaml
    plugins:
      - name: rate-limiting
        config:
          minute: 10   # <-- change this to 5
```

3. Save the file.

4. Restart only Kong (no downtime for other services):

```bash
docker compose restart kong
```

5. Wait about 10 seconds for Kong to reload, then test:

```bash
for i in $(seq 1 7); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/v1/products)
  REMAINING=$(curl -s -D - http://localhost:8888/v1/products -o /dev/null | grep -i "x-ratelimit-remaining-minute" | awk '{print $2}')
  echo "Request $i: HTTP $STATUS | Remaining: $REMAINING"
done
```

You should now hit 429 after only 5 requests.

6. Verify the new config loaded:

```bash
curl -s "http://localhost:8081/plugins?name=rate-limiting" | \
  python3 -c "import sys,json; [print(p['route'], '| minute:', p['config']['minute']) for p in json.load(sys.stdin)['data'] if p.get('route')]"
```

---

### Task 6: Add a New Plugin

Add the built-in `correlation-id` plugin to automatically stamp every request with a
unique `X-Correlation-ID` header. This is essential for distributed tracing.

1. Open `kong/kong.yml`.

2. Add the following under the `plugins:` section (after the existing global plugins):

```yaml
  # Correlation ID — stamp every request with a unique trace ID
  - name: correlation-id
    config:
      header_name: X-Correlation-ID
      generator: uuid#counter
      echo_downstream: true
```

3. Save the file and restart Kong:

```bash
docker compose restart kong
```

4. Test that the header appears:

```bash
curl -sv http://localhost:8888/health 2>&1 | grep -i "x-correlation-id"
```

Expected output:
```
< X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000#1
```

5. Send multiple requests and note that each gets a unique ID:

```bash
for i in $(seq 1 3); do
  curl -s -D - http://localhost:8888/health -o /dev/null | grep -i "x-correlation-id"
done
```

The counter suffix (`#1`, `#2`, `#3`) increments per Kong worker process restart.

---

### Task 7: API Versioning Exploration

Compare what v1 and v2 return for the same resource and understand how Kong transforms
the response.

```bash
# Get a fresh token
TOKEN=$(curl -s -X POST http://localhost:8888/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "any-password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# v1 products — basic response
echo "=== v1 response ==="
curl -s http://localhost:8888/v1/products | python3 -m json.tool

# v2 products — enriched response (stock, rating, metadata)
echo "=== v2 response ==="
curl -s http://localhost:8888/v2/products \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Compare headers between v1 and v2
echo "=== v1 headers ==="
curl -sI http://localhost:8888/v1/products | grep -iE "x-api|x-enhanced|x-ratelimit"

echo "=== v2 headers ==="
curl -sI http://localhost:8888/v2/products \
  -H "Authorization: Bearer $TOKEN" | grep -iE "x-api|x-enhanced|x-ratelimit"
```

Key differences to observe:
- **v1**: No auth required for products, basic product fields, limit 10/min
- **v2**: JWT required, enriched fields (stock_count, rating, last_updated), limit 60/min, `X-API-Version: 2.0` header injected by Kong's request-transformer plugin

---

### Task 8: Monitor Redis Rate Limit Keys

Go deeper into Redis to understand exactly how Kong stores rate limit state.

```bash
# Connect to Redis
docker compose exec redis redis-cli
```

Inside the Redis CLI:

```redis
# See all rate limit keys currently stored
KEYS RateLimit:*

# Count how many rate limit keys exist
DBSIZE

# Get all keys with a scan (safer for production Redis)
SCAN 0 MATCH "RateLimit:*" COUNT 100

# Inspect a specific key (substitute the actual key name)
# Key format: RateLimit:<route-or-service>:<identifier>:<window-timestamp>:<period>
GET RateLimit:api-v1-products-public:127.0.0.1:1700000000:minute

# Check TTL — how many seconds until this window resets
TTL RateLimit:api-v1-products-public:127.0.0.1:1700000000:minute

# Watch a counter increment in real time
WATCH RateLimit:api-v1-products-public:127.0.0.1:1700000000:minute

# Exit redis-cli
QUIT
```

In a second terminal, send requests while watching:

```bash
for i in $(seq 1 5); do
  curl -s -o /dev/null http://localhost:8888/v1/products
  docker compose exec redis redis-cli KEYS "RateLimit:*"
done
```

---

## Services Overview

| Service | Host Port | Container Port | URL | Purpose |
|---|---|---|---|---|
| frontend | 3000 | 80 | http://localhost:3000 | Web dashboard UI |
| kong (proxy) | 8888 | 8000 | http://localhost:8888 | All API traffic entry point |
| kong (admin) | 8081 | 8001 | http://localhost:8081 | Kong Admin API |
| postgres | (internal) | 5432 | postgres:5432 | API service database |
| redis | (internal) | 6379 | redis:6379 | Kong rate limit backend |
| api-service | (internal) | 8001 | api-service:8001 | FastAPI backend |
| analytics-service | (internal) | 8002 | analytics-service:8002 | Analytics aggregator |

Only Kong proxy and the frontend are exposed to your host machine.
All other services communicate on the internal Docker network.

---

## Credentials

**Database**

| Parameter | Value |
|---|---|
| Host | postgres (internal) |
| Port | 5432 |
| Database | gateway_db |
| Username | gateway |
| Password | gatewaypass |

**JWT**

| Parameter | Value |
|---|---|
| Secret | `gateway-demo-secret-key-2024` |
| Algorithm | HS256 |
| Expiry | 30 minutes |

**Demo Users**

| Username | Tier | Notes |
|---|---|---|
| alice | premium | Maps to `premium-user` Kong consumer |
| bob | free | Maps to `demo-user` Kong consumer |
| charlie | free | Maps to `demo-user` Kong consumer |
| diana | premium | Maps to `premium-user` Kong consumer |

Any password works — the demo API accepts any non-empty password string.
In a real deployment, passwords would be hashed and validated against the database.

**Kong Consumers (for JWT)**

| Consumer | Key | Secret |
|---|---|---|
| demo-user | `demo-user-key` | `gateway-demo-secret-key-2024` |
| premium-user | `premium-user-key` | `gateway-demo-secret-key-2024` |

---

## Troubleshooting

**Kong fails to start or exits immediately**

Check for YAML syntax errors in `kong/kong.yml`:

```bash
docker compose exec kong kong config parse /etc/kong/kong.yml
```

Also check Kong logs for the specific error:

```bash
docker compose logs kong
```

Common causes: missing required fields, indentation errors, duplicate plugin names in
the global plugins section.

**401 Unauthorized on protected endpoints**

Your JWT token has expired (tokens expire after 30 minutes). Get a fresh one:

```bash
TOKEN=$(curl -s -X POST http://localhost:8888/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "any-password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Also verify you are sending the token correctly:

```bash
# Correct format
curl -H "Authorization: Bearer $TOKEN" http://localhost:8888/v1/users

# Wrong format (no "Bearer " prefix) — will get 401
curl -H "Authorization: $TOKEN" http://localhost:8888/v1/users
```

**Rate limiting not working (all requests succeed past the limit)**

Check that Redis is healthy:

```bash
docker compose ps redis
docker compose exec redis redis-cli ping
# Expected: PONG
```

If Redis is unhealthy, Kong falls back to `fault_tolerant: true` which means it allows
all requests rather than blocking. Restart Redis:

```bash
docker compose restart redis
```

Then restart Kong so it reconnects:

```bash
docker compose restart kong
```

**502 Bad Gateway when calling through Kong**

The api-service may still be starting up. Kong depends on api-service being healthy, but
there can be a race condition on first boot. Check:

```bash
docker compose ps api-service
docker compose logs api-service --tail 20
```

If api-service is still starting:

```bash
# Wait for it to become healthy, then restart Kong
docker compose restart kong
```

**Cannot connect to postgres / database errors in api-service logs**

Postgres takes a few seconds to initialize on first boot. The api-service has a health
check dependency, but if you see DB errors:

```bash
docker compose logs postgres --tail 20

# Force recreate api-service after postgres is healthy
docker compose restart api-service
```

**Port conflict on 3000, 8888, or 8081**

Another process is using that port. Find it:

```bash
lsof -i :8888
# or
ss -tlnp | grep 8888
```

Either stop the conflicting process or change the host port mapping in `docker-compose.yml`.

**Frontend shows "Service Unavailable" or blank data**

The analytics-service depends on both api-service and kong being healthy. It may take
up to 60 seconds for all health checks to pass on first boot:

```bash
docker compose logs analytics-service --tail 20
```

If analytics-service is repeatedly restarting, check the `KONG_ADMIN_URL` environment
variable — it must resolve to `http://kong:8001` (the internal container port, not 8081).

---

## Useful Commands Reference

```bash
# Start everything (build images first)
docker compose up --build

# Start in background
docker compose up --build -d

# Stop and remove containers (keep volumes)
docker compose down

# Stop and remove everything including volumes (fresh start)
docker compose down -v

# View logs from all services
docker compose logs -f

# View logs from a specific service
docker compose logs -f kong

# Restart a single service without touching others
docker compose restart kong

# Rebuild and restart a single service
docker compose up --build -d api-service

# Open a shell in a running container
docker compose exec api-service bash
docker compose exec redis redis-cli

# Check resource usage
docker stats $(docker compose ps -q)
```

---

## What's Next

Once you have explored the local stack and completed all 8 tasks, you are ready to
deploy GatewayHub on Kubernetes.

Move to the `main/` directory for the full Kubernetes deployment:

```bash
cd ../main
ls
```

The Kubernetes deployment adds:
- Kong deployed as a Deployment with a ConfigMap for the declarative config
- Redis as a StatefulSet with persistent storage
- PostgreSQL as a StatefulSet
- Horizontal Pod Autoscaler on api-service and analytics-service
- Kubernetes Secrets for sensitive values (DB password, JWT secret)
- Ingress for external access
- Prometheus ServiceMonitor for scraping Kong metrics
- Helm chart packaging of the entire stack

The concepts are identical — the same kong.yml, the same routes, the same plugins.
The difference is operational: health checks become readinessProbes, volumes become
PersistentVolumeClaims, and network routing goes through kube-proxy and Ingress.
