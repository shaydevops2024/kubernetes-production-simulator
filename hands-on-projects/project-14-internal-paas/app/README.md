# App — Developer Portal

This folder contains the source code for the **Developer Portal** — a self-service web application that acts as the "front door" to the Internal Developer Platform (IDP).

The portal gives engineering teams a single place to:
- See their team's namespace, resource usage, and cost
- View running services and their health
- Deploy new services using pre-built templates
- Request new namespaces
- Monitor CI/CD pipeline status

You do **not** write this application code. Your job is to containerize it, run it locally, and eventually deploy it to Kubernetes alongside all the platform tools.

---

## Architecture

```
Browser
   │
   ▼
portal (FastAPI + static HTML/CSS/JS)
   │
   ├── /           → serves index.html (the portal UI)
   ├── /api/*      → REST API with mock platform data
   ├── /static/*   → CSS, JS assets
   └── /health     → health check endpoint
```

In local/mock mode, all data is hardcoded in `main.py`. In the Kubernetes deployment, this portal would be wired to real Kubernetes APIs, Crossplane, and OpenCost for live data.

---

## Services Overview

| Path | Port | Technology | Description |
|------|------|-----------|-------------|
| `portal/` | 8000 | FastAPI + Uvicorn | Backend API + static file server |

---

## Running the Portal Standalone (no Docker)

```bash
cd app/portal
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open: **http://localhost:8000**

Swagger API docs: **http://localhost:8000/docs**

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard` | GET | High-level stats (services, pods, cost) |
| `/api/teams` | GET | All teams |
| `/api/teams/{id}` | GET | Single team |
| `/api/namespaces` | GET | All namespaces + resource usage |
| `/api/services` | GET | All services (filter by `?team_id=`) |
| `/api/pipelines` | GET | All CI/CD pipelines (filter by `?team_id=`) |
| `/api/catalog` | GET | Service templates catalog |
| `/api/costs` | GET | Per-team cost breakdown |
| `/api/deploy` | POST | Trigger a deploy (creates a record, mock) |
| `/api/namespaces/request` | POST | Request a new namespace (creates a record, mock) |

---

## Portal UI Sections

| Page | What it shows |
|------|--------------|
| **Dashboard** | Summary stats + recent pipelines + service health |
| **Teams** | All teams with namespace and member count |
| **Namespaces** | Cluster namespaces with CPU/memory/pod usage bars |
| **Services** | All running services with replica status |
| **Pipelines** | CI/CD pipeline runs with status and commit info |
| **Service Catalog** | Templates to deploy new services |
| **Costs** | Per-team monthly cost breakdown |

---

## Dockerfile

The `portal/Dockerfile` follows the standard pattern:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
COPY static/ ./static/
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Questions to think about:**
- Why is the static folder copied separately from `main.py`?
- How would you add a non-root user for production?
- What would a multi-stage build look like for this image?
- How would you connect the portal to a real Kubernetes API in production?

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Port to listen on |

---

## Next Step

→ Go to [../local/README.md](../local/README.md) to run the full stack with Docker Compose.
