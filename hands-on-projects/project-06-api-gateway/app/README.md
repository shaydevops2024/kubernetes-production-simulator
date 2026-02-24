# App — GatewayHub Application Overview

This folder contains the three pre-built services that make up GatewayHub. You do not need to modify any application code. Your job is to deploy these services and put Kong in front of them.

Read this file carefully before you write any Kubernetes manifests or Docker Compose configuration. Understanding what the services do and how they communicate will make every later phase much easier.

---

## Services

### 1. api-service (FastAPI, port 8001)

The primary REST API being protected by Kong. It has three layers:

- **Auth endpoints** — generate and validate JWT tokens
- **API v1** — standard REST endpoints, some public, some JWT-protected
- **API v2** — enhanced endpoints with richer response format, JWT required

The service uses SQLAlchemy with PostgreSQL (or SQLite for quick local testing). On startup it seeds the database with demo products, users, and a demo order.

### 2. analytics-service (FastAPI, port 8002)

A secondary service that polls the Kong Admin API every 10 seconds and caches the results in memory. It exposes aggregated statistics about Kong's running state — services, routes, plugins, consumers, connection counts — alongside metrics from the api-service itself.

This service is intentionally unauthenticated. In the local Docker Compose setup it connects to the Kong Admin API directly. In Kubernetes it would require the Kong Admin service to be accessible from within the cluster.

### 3. frontend (nginx, port 80)

A static dashboard served by nginx. The dashboard JavaScript calls `/analytics/stats`, `/analytics/routes`, `/analytics/services`, and `/analytics/plugins` through Kong to build a live view of gateway activity.

---

## API Reference

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/login` | None | Generate a JWT token |
| `POST` | `/auth/validate` | Bearer token | Decode and validate the token |

**Login request body:**
```json
{ "username": "alice", "password": "any" }
```

The password field is accepted but not validated — this is a demo. Any value works.

**Login response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "consumer": "premium-user-key",
  "plan": "premium"
}
```

**Demo users:**

| Username | Plan | Kong Consumer | Rate Limit (v1 protected) | Rate Limit (v2) |
|----------|------|--------------|--------------------------|-----------------|
| alice | premium | premium-user | 30 req/min | 60 req/min |
| bob | free | demo-user | 30 req/min | 60 req/min |
| charlie | free | demo-user | 30 req/min | 60 req/min |
| diana | premium | premium-user | 30 req/min | 60 req/min |

Note: rate limiting at the consumer level is set by the Kong plugin configuration, not by the `plan` field. Both consumers (`demo-user` and `premium-user`) share the same configured limits in the reference implementation. You can differentiate them by creating separate KongPlugin resources and assigning them per-consumer in Phase 5.

---

### API v1 — Public Endpoints (no authentication required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/products` | List all products. Optional `?category=` filter |
| `GET` | `/v1/products/{id}` | Get a single product by ID |
| `GET` | `/v1/products/categories` | List all distinct product categories |

**Example v1 product response:**
```json
{
  "id": 1,
  "name": "Kong API Gateway",
  "description": "Enterprise-grade API gateway with plugin ecosystem",
  "price": 0.0,
  "category": "Gateway",
  "is_active": true
}
```

This route is rate-limited at **10 requests per minute** (by IP in the reference config).

---

### API v1 — Protected Endpoints (JWT required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/users/me` | Get current authenticated user profile |
| `GET` | `/v1/orders` | List orders belonging to the authenticated user |
| `POST` | `/v1/orders` | Create a new order |

**Create order request body:**
```json
{ "product_ids": [1, 3], "total": 0.0 }
```

These routes require a valid `Authorization: Bearer <token>` header. Kong validates the JWT before forwarding the request. If Kong is running, the api-service trusts the `X-Consumer-Username` header that Kong injects and does not re-validate the token. If calling the api-service directly (bypassing Kong), the api-service falls back to its own JWT validation.

---

### API v2 — Enhanced (JWT required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v2/products` | Enhanced product list with stock, rating, and metadata |
| `GET` | `/v2/users/me` | Enhanced user profile with order stats and API tier info |
| `GET` | `/v2/metrics` | Internal api-service metrics (used by analytics-service) |

**Example v2 products response:**
```json
{
  "data": [
    {
      "id": 1,
      "name": "Kong API Gateway",
      "description": "...",
      "price": 0.0,
      "category": "Gateway",
      "stock": 999,
      "rating": 4.9,
      "is_active": true,
      "metadata": {
        "availability": "in_stock",
        "popularity_score": 4.9,
        "free_shipping": true,
        "tags": ["gateway", "kong-plugin"]
      }
    }
  ],
  "total": 12,
  "api_version": "2.0",
  "enhancements": ["stock_info", "ratings", "metadata", "availability_status"],
  "requested_by": "alice"
}
```

---

### Analytics Service Endpoints (no authentication)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analytics/stats` | Kong status + api-service error/request metrics |
| `GET` | `/analytics/routes` | All registered Kong routes |
| `GET` | `/analytics/services` | All registered Kong services |
| `GET` | `/analytics/plugins` | All active Kong plugins with scope |
| `GET` | `/analytics/consumers` | Registered Kong consumers |

---

## v1 vs v2 Comparison

| Field | v1 Response | v2 Response |
|-------|-------------|-------------|
| `id` | yes | yes |
| `name` | yes | yes |
| `description` | yes | yes |
| `price` | yes | yes |
| `category` | yes | yes |
| `is_active` | yes | yes |
| `stock` | no | yes |
| `rating` | no | yes |
| `metadata.availability` | no | yes |
| `metadata.popularity_score` | no | yes |
| `metadata.free_shipping` | no | yes |
| `metadata.tags` | no | yes |
| `api_version` | no | `"2.0"` |
| `enhancements` | no | yes (list) |
| `requested_by` | no | yes (username) |
| Response shape | flat array | `{ data: [], total, api_version }` |

This response structure difference is the core of the versioning exercise. In production you would maintain v1 for backwards compatibility while adding capabilities to v2.

---

## Environment Variables

### api-service

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./gateway_demo.db` | SQLAlchemy connection string |
| `PORT` | `8001` | Port the service listens on |
| `JWT_SECRET` | `gateway-demo-secret-key-2024` | HS256 signing secret — must match Kong consumer credential |

In Kubernetes, `DATABASE_URL` should be set to the PostgreSQL connection string via a Secret.

### analytics-service

| Variable | Default | Description |
|----------|---------|-------------|
| `KONG_ADMIN_URL` | `http://kong:8001` | Kong Admin API base URL |
| `API_SERVICE_URL` | `http://api-service:8001` | api-service base URL for metrics polling |
| `PORT` | `8002` | Port the service listens on |

The analytics service polls both URLs every 10 seconds in a background task.

---

## JWT Token Structure

When a user calls `POST /auth/login`, the api-service generates a JWT with this structure:

**Header:**
```json
{ "alg": "HS256", "typ": "JWT" }
```

**Payload:**
```json
{
  "iss": "demo-user-key",
  "sub": "bob",
  "plan": "free",
  "jti": "a7f3c2d1-...",
  "iat": 1734567890,
  "exp": 1734654290
}
```

For premium users (`alice`, `diana`), the `iss` claim is `"premium-user-key"` instead.

**Claims explained:**

| Claim | Value | Purpose |
|-------|-------|---------|
| `iss` | `demo-user-key` or `premium-user-key` | Issuer — Kong uses this to look up the matching consumer credential |
| `sub` | username (e.g. `"alice"`) | Subject — who the token belongs to |
| `plan` | `"free"` or `"premium"` | Application-level metadata (not used by Kong) |
| `jti` | UUID | Unique token ID (prevents replay in stricter setups) |
| `iat` | Unix timestamp | Issued at |
| `exp` | Unix timestamp | Expiry — Kong validates this automatically |

---

## How Kong JWT Authentication Works

This is the most important concept in this project. Follow the chain carefully.

**Step 1 — Login**

The client calls `POST /auth/login`. The api-service looks up the user, determines their plan, and creates a JWT signed with `gateway-demo-secret-key-2024`. The `iss` claim is set to either `demo-user-key` or `premium-user-key` based on the user's plan.

**Step 2 — Kong Consumer Configuration**

Kong has two consumers configured:

```
Consumer: demo-user
  JWT credential:
    key:    demo-user-key           ← matches iss in token
    secret: gateway-demo-secret-key-2024
    alg:    HS256

Consumer: premium-user
  JWT credential:
    key:    premium-user-key        ← matches iss in token
    secret: gateway-demo-secret-key-2024
    alg:    HS256
```

**Step 3 — Request reaches Kong**

When the client sends a request to a JWT-protected route:
1. Kong reads the `Authorization: Bearer <token>` header
2. Kong decodes the JWT header (no validation yet) to read the `iss` claim
3. Kong looks up the consumer whose JWT credential `key` matches `iss`
4. Kong verifies the JWT signature using that consumer's `secret`
5. Kong verifies the `exp` claim has not passed
6. If all checks pass, Kong proxies the request and injects `X-Consumer-Username` into the request headers

**Step 4 — api-service receives the forwarded request**

The api-service checks for the `X-Consumer-Username` header first. If it is present (set by Kong), it trusts it and skips re-validation. This is the standard Kong pattern — the gateway is the trust boundary.

**What happens if the JWT secret does not match?**

If the api-service and Kong are configured with different secrets, Kong will return `401 Unauthorized` with `{"message": "Invalid signature"}`. The request never reaches the api-service.

---

## Running a Single Service Standalone

### api-service

```bash
cd app/api-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
# OpenAPI docs: http://localhost:8001/docs
# Health check:  http://localhost:8001/health
```

This runs with SQLite by default (no PostgreSQL needed). Useful for exploring the API before adding Kong.

### analytics-service

```bash
cd app/analytics-service
pip install -r requirements.txt
KONG_ADMIN_URL=http://localhost:8001 API_SERVICE_URL=http://localhost:8001 \
  uvicorn main:app --reload --port 8002
```

If Kong is not running, `kong_available` will be `false` in all responses, but the service starts without error.

---

## Things to Think About

- Why does the api-service use `iss` as the Kong consumer lookup key instead of `sub`?
- What happens if a user generates a token and you then delete the KongConsumer from Kubernetes?
- The analytics service connects to the Kong Admin API. In a real production setup, should this be publicly accessible?
- The JWT secret is the same for both consumers. What are the security implications of rotating it?
- The api-service trusts `X-Consumer-Username` from any caller. What would happen if someone sent that header directly to the api-service, bypassing Kong?
