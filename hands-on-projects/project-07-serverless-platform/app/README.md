# App — Serverless Functions Platform

This folder contains the source code for all three services. You do **not** write this code — your job is to containerize, deploy, and orchestrate it.

---

## Services Overview

| Service | Port | Language | Responsibility |
|---------|------|----------|----------------|
| `function-service` | 8001 | Python / FastAPI | Function registry, invocation routing, stats |
| `function-runner` | 8002 | Python / FastAPI | Executes functions, returns results |
| `frontend` | 80 | HTML/CSS/JS + nginx | Dashboard UI — marketplace, invoker, scaling demo |

---

## Architecture

```
Browser
    │
    ▼
Frontend (nginx :80)
    │  /api/* proxied to function-service
    ▼
function-service (:8001)    ← registry + stats + invoke router
    │  POST /run/{name}
    ▼
function-runner (:8002)     ← actual function execution
```

The frontend only ever talks to the function-service. The function-service calls the function-runner internally. This separation mirrors how real FaaS platforms work: a control plane (registry/routing) and a data plane (execution).

---

## Available Functions

| Function | Trigger | Description |
|----------|---------|-------------|
| `hello-world` | HTTP | Simple greeting — baseline function |
| `fibonacci` | HTTP | Computes Fibonacci(N), CPU-bound for scaling demos |
| `text-processor` | HTTP | Word count, sentiment, reading time analysis |
| `image-info` | HTTP | Mock image metadata from URL |
| `weather-report` | HTTP / Cron | Mock weather report + 3-day forecast |

---

## Running a Single Service (without Docker)

```bash
# function-runner (start this first — no dependencies)
cd function-runner
pip install -r requirements.txt
uvicorn main:app --reload --port 8002

# function-service (needs runner running)
cd function-service
pip install -r requirements.txt
FUNCTION_RUNNER_URL=http://localhost:8002 uvicorn main:app --reload --port 8001

# frontend — open index.html directly in a browser:
# Add ?api=http://localhost:8001 to the URL so it points to your local service
# e.g. file:///path/to/index.html?api=http://localhost:8001
```

Each service has automatic Swagger docs at `/docs` — e.g., `http://localhost:8001/docs`.

---

## API Contracts

### function-service (port 8001)

```
GET  /health                         → Health check
GET  /functions                      → List all functions with metadata
GET  /functions/{name}               → Get single function details
POST /functions/{name}/invoke        → Invoke a function
     Body: {"payload": {<fn-specific>}}
GET  /stats                          → Invocation counts + latency per function
```

### function-runner (port 8002)

```
GET  /health                         → Health check
GET  /functions                      → List available function handlers
POST /run/{name}                     → Execute a function
     Body: {"payload": {<fn-specific>}}
```

### Function payloads

```bash
# hello-world
{"name": "DevOps Engineer"}

# fibonacci (n between 0 and 40)
{"n": 35}

# text-processor
{"text": "Your text here..."}

# image-info
{"url": "https://example.com/photo.jpg"}

# weather-report
{"city": "Tel Aviv"}
```

---

## Environment Variables

### function-service

| Variable | Default | Description |
|----------|---------|-------------|
| `FUNCTION_RUNNER_URL` | `http://localhost:8002` | URL of the function-runner |
| `PORT` | `8001` | Port to listen on |

### function-runner

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8002` | Port to listen on |

---

## Dockerfiles

All services follow the same pattern:

```dockerfile
FROM python:3.11-slim        # slim = smaller image, no dev tools
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE <port>
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "<port>"]
```

**Questions to think about:**

- Why is `function-runner` separate from `function-service`? What would happen if you merged them?
- What changes in the Dockerfile would make this production-ready? (non-root user, health check, multi-stage build)
- In a real FaaS platform, each function runs in its own isolated container — how would you implement that?
- Why does `function-service` need to know the URL of `function-runner` at runtime? How does this translate to Kubernetes service discovery?

---

## What You Don't Touch (But Should Understand)

- The function implementations in `function-runner/main.py` — read them, but don't modify them
- The API routes in `function-service/main.py` — these are the contracts your K8s Services must expose
- The nginx config in `frontend/nginx.conf` — your Ingress will replicate this routing at the cluster level

**→ Go to [../local/README.md](../local/README.md) to run the full stack with Docker Compose**
