# App — DevOps Projects Hub

This folder contains the source code for the **DevOps Projects Hub**: a small FastAPI web application that serves a dashboard listing all 16 hands-on projects in this series.

This is the application you will deploy through a full GitOps CI/CD pipeline with progressive delivery. You don't write this code — you containerize it, automate its build, scan its image, and deploy it with canary releases.

---

## What It Does

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Projects Hub web UI (HTML) |
| `/health` | GET | Health check (used by K8s liveness probe) |
| `/ready` | GET | Readiness check (used by K8s readiness probe) |
| `/api/version` | GET | Returns version, build date, git commit, environment |
| `/api/projects` | GET | Returns all 16 projects with status |

The UI displays:
- All 16 projects with status (Available / Coming Soon)
- The current **version** in the header and banner — key for canary demos
- A deployment info panel with build date, git commit, and replica ID
- During a canary deployment: refreshing shows v1 (blue) or v2 (green) randomly

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_VERSION` | `v1` | Version label shown in the UI |
| `BUILD_DATE` | `unknown` | Set by CI pipeline at build time |
| `GIT_COMMIT` | `unknown` | Git SHA injected by CI |
| `ENVIRONMENT` | `local` | `local`, `staging`, or `production` |
| `HOSTNAME` | (auto) | Pod name in Kubernetes, used as replica ID |

---

## Running Without Docker

```bash
cd app/
pip install -r requirements.txt
APP_VERSION=v1 uvicorn main:app --reload --port 8181
```

Then open: http://localhost:8181

---

## API Examples

```bash
# Health check
curl http://localhost:8181/health

# Version info
curl http://localhost:8181/api/version

# All projects
curl http://localhost:8181/api/projects | python3 -m json.tool
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
COPY static/ static/
EXPOSE 8080

# Build args — injected by CI pipeline
ARG APP_VERSION=v1
ARG BUILD_DATE=unknown
ARG GIT_COMMIT=unknown
ENV APP_VERSION=$APP_VERSION
ENV BUILD_DATE=$BUILD_DATE
ENV GIT_COMMIT=$GIT_COMMIT

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Questions to think about:**
- Why are `APP_VERSION`, `BUILD_DATE`, and `GIT_COMMIT` build args and not just env vars?
- What is the difference between `ARG` and `ENV` in a Dockerfile?
- How would the CI pipeline pass the git commit SHA into the image?
- What's missing for production? (hints: non-root user, multi-stage build, `.dockerignore`)

---

## The v1 → v2 Story

This app is designed to demonstrate **progressive delivery**. Here's how it works:

- **v1** — Blue theme. Shows all projects. This is the stable version.
- **v2** — Green theme. Same projects, but the UI accent color changes to signal a new version.

When Flagger does a canary deployment (10% → 30% → 50% → 100%), some requests hit v1 pods and some hit v2 pods. Refreshing the browser lets you observe the traffic split in real time — the color and version badge change.

To "release" v2, the CI pipeline builds a new image with:
```bash
docker build \
  --build-arg APP_VERSION=v2 \
  --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  -t yourregistry/projects-hub:v2 .
```

---

## File Structure

```
app/
├── README.md         ← This file
├── main.py           ← FastAPI application
├── requirements.txt
├── Dockerfile
└── static/
    ├── index.html    ← Projects Hub page structure
    ├── style.css     ← Styling + version-based theme (blue=v1, green=v2)
    └── app.js        ← Fetches /api/version and /api/projects, renders cards
```

---

## Next Step

**→ Go to [../local/README.md](../local/README.md) to run the full stack locally and simulate a canary deployment with Docker Compose**
