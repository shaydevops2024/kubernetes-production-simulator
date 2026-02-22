# Local — Running the Full Stack with Docker Compose

This is your first DevOps task: get the entire e-commerce platform running locally using Docker Compose.

By the end of this step you'll have:
- All 5 microservices running in containers
- 4 PostgreSQL databases (one per stateful service)
- An nginx API gateway routing traffic
- A working web UI at http://localhost:8088

---

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose plugin)
- At least 4GB of free RAM
- Port 8088 not in use

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

The first build downloads images and builds all service images — takes 2-3 minutes.

Once you see all services healthy:
- **UI:** http://localhost:8088
- **Product Service API docs:** http://localhost:8001/docs *(direct access)*
- **Cart Service API docs:** http://localhost:8002/docs
- **Order Service API docs:** http://localhost:8003/docs
- **Payment Service API docs:** http://localhost:8004/docs
- **Inventory Service API docs:** http://localhost:8005/docs

---

## Architecture in docker-compose

```
Browser (http://localhost:8088)
        │
        ▼
   [gateway — nginx:80]          ← Port 8088 exposed to host
        │
        ├── /api/products/*  ──→ product-service:8001  ──→ postgres-products
        ├── /api/cart/*      ──→ cart-service:8002      (in-memory)
        ├── /api/orders/*    ──→ order-service:8003     ──→ postgres-orders
        │                              │
        │                         ┌───┴──────────────────┐
        │                         │ calls payment-service │
        │                         │ calls inventory-service│
        │                         └───────────────────────┘
        ├── /api/payments/*  ──→ payment-service:8004   ──→ postgres-payments
        ├── /api/inventory/* ──→ inventory-service:8005 ──→ postgres-inventory
        └── /                ──→ frontend (nginx)
```

---

## Useful Commands

```bash
# Start in detached mode (background)
docker compose up --build -d

# Check status of all containers
docker compose ps

# View logs for a specific service
docker compose logs -f product-service
docker compose logs -f order-service

# View logs for all services
docker compose logs -f

# Stop everything
docker compose down

# Stop and remove volumes (reset all data)
docker compose down -v

# Rebuild a specific service after code change
docker compose up --build product-service

# Execute commands inside a running container
docker compose exec product-service python -c "print('hello from container')"
docker compose exec postgres-products psql -U shop -d products_db -c "\dt"
```

---

## DevOps Tasks for This Phase

Now that it runs, explore and understand what's happening:

### Task 1 — Inspect Networking
```bash
# List Docker networks
docker network ls

# Inspect the compose network
docker network inspect local_default

# See which services are connected
docker compose exec gateway ping product-service
docker compose exec order-service ping payment-service
```

**Question:** How do services discover each other? Why can `order-service` reach `payment-service` by hostname?

### Task 2 — Inspect Volumes
```bash
# List volumes created
docker volume ls | grep local

# Connect to the database and explore
docker compose exec postgres-products psql -U shop -d products_db
\dt           # list tables
\d products   # describe products table
SELECT count(*) FROM products;
\q
```

**Question:** Where is the data stored on your host machine? What happens to data when you run `docker compose down` vs `docker compose down -v`?

### Task 3 — Health Checks
```bash
# Check health status of all containers
docker compose ps

# Inspect health check details
docker inspect local-product-service-1 | grep -A 15 '"Health"'
```

**Question:** What happens if a service fails its health check? How does the gateway handle a downstream service being unhealthy?

### Task 4 — Environment Variables
```bash
# See env vars for a service
docker compose exec order-service env | grep -E "SERVICE_URL|DATABASE"
```

**Question:** How does `order-service` know where `cart-service` is? What would break if you changed the service name in docker-compose.yml?

### Task 5 — Simulate a Failure
```bash
# Stop one service
docker compose stop payment-service

# Try to place an order via the UI
# What error do you see? How does the order-service handle it?

# Bring it back
docker compose start payment-service
```

### Task 6 — Scale a Service
```bash
# Scale product-service to 3 replicas
docker compose up --scale product-service=3 -d

# Can you still reach products? What's the behavior?
# Hint: the gateway config only knows about one upstream. What would you need to change?
```

---

## Common Issues

**Port 8088 already in use:**
```bash
# Find what's using it
lsof -i :8088
# Change the port in docker-compose.yml: "8089:80" instead of "8088:80"
```

**Database not ready error on startup:**
The healthchecks handle this — services wait for DB readiness. If you still see errors, give it 30 seconds and check `docker compose ps`.

**Permission errors on Linux:**
```bash
sudo chmod 666 /var/run/docker.sock
```

---

## Next Step

Once you're comfortable with the local setup, move on to [../main/README.md](../main/README.md) to deploy this to Kubernetes.
