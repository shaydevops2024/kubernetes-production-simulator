# App — E-Commerce Microservices

This folder contains the source code for all 5 microservices and the frontend. Each service is a standalone FastAPI application that you can run individually or together via Docker Compose (see `../local/`).

---

## Services Overview

| Service | Port | Language | Database | Description |
|---------|------|----------|----------|-------------|
| product-service | 8001 | Python/FastAPI | SQLite/PostgreSQL | Product catalog CRUD |
| cart-service | 8002 | Python/FastAPI | In-Memory/Redis | Shopping cart management |
| order-service | 8003 | Python/FastAPI | SQLite/PostgreSQL | Order creation and tracking |
| payment-service | 8004 | Python/FastAPI | SQLite/PostgreSQL | Mock payment gateway |
| inventory-service | 8005 | Python/FastAPI | SQLite/PostgreSQL | Stock level management |
| frontend | 80 | HTML/CSS/JS | — | Browser UI served by nginx |

---

## Running a Single Service (without Docker)

Useful for development and understanding the code.

```bash
# Example: run the product service
cd product-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Then open: http://localhost:8001/docs — every service has an automatic Swagger UI.

---

## Running All Services Together

Use the Docker Compose setup in `../local/`. That's the intended way to run the full stack.

---

## Environment Variables

Each service is configured via environment variables (with sane defaults for local dev):

### product-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./products.db` | Database connection string |
| `PORT` | `8001` | Port to listen on |

### cart-service
| Variable | Default | Description |
|----------|---------|-------------|
| `PRODUCT_SERVICE_URL` | `http://localhost:8001` | URL to call product service |
| `PORT` | `8002` | Port to listen on |

### order-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./orders.db` | Database connection string |
| `CART_SERVICE_URL` | `http://localhost:8002` | URL to call cart service |
| `PAYMENT_SERVICE_URL` | `http://localhost:8004` | URL to call payment service |
| `INVENTORY_SERVICE_URL` | `http://localhost:8005` | URL to call inventory service |
| `PORT` | `8003` | Port to listen on |

### payment-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./payments.db` | Database connection string |
| `PORT` | `8004` | Port to listen on |

### inventory-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./inventory.db` | Database connection string |
| `PORT` | `8005` | Port to listen on |

---

## API Contracts

### product-service
```
GET    /products              → List all products (supports ?category=&search=)
GET    /products/{id}         → Get single product
POST   /products              → Create product
PUT    /products/{id}         → Update product
DELETE /products/{id}         → Delete product
GET    /health                → Health check
```

### cart-service
```
GET    /cart/{user_id}                      → Get cart for user
POST   /cart/{user_id}/items                → Add item to cart
DELETE /cart/{user_id}/items/{product_id}   → Remove item from cart
DELETE /cart/{user_id}                      → Clear cart
GET    /health                              → Health check
```

### order-service
```
GET    /orders                → List all orders
GET    /orders/{id}           → Get single order
POST   /orders                → Create order from cart
PATCH  /orders/{id}/status    → Update order status
GET    /health                → Health check
```

### payment-service
```
POST   /payments/process      → Process a payment
GET    /payments/{id}         → Get payment status
GET    /health                → Health check
```

### inventory-service
```
GET    /inventory                   → List all inventory
GET    /inventory/{product_id}      → Get stock for product
PUT    /inventory/{product_id}      → Update stock level
POST   /inventory/{product_id}/reserve  → Reserve stock for order
GET    /health                      → Health check
```

---

## Dockerfiles

Each service has a `Dockerfile`. Your first DevOps task is understanding them:

```dockerfile
# All services follow this pattern
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE <port>
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "<port>"]
```

**Questions to think about:**
- Why `python:3.11-slim` and not `python:3.11`?
- What does `--no-cache-dir` do and why does it matter in containers?
- Why `--host 0.0.0.0` instead of the default `127.0.0.1`?
- How would you reduce the image size further?
- What's missing for production? (hints: non-root user, health check, multi-stage build)
