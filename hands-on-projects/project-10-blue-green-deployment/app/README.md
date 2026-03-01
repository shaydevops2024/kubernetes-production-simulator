# App — DeployTrack

**DeployTrack** is the demo application you'll deploy using the Blue-Green strategy. It's a release tracking dashboard: a small FastAPI service with a visual UI that makes the concept of "two identical environments, one live at a time" tangible.

You do **not** write application code. Your job is to containerize it, run it, deploy it, and automate the traffic switching.

---

## What the App Does

DeployTrack tracks software releases. It shows:

- The **active version** (v1 or v2) and **environment color** (blue or green) in a bold header
- A **release history table** — past deployments, their colors, and statuses
- A **request counter** — live count of HTTP requests served (updates every 3s)
- A new **Dark Mode toggle** in the green/v2 version — proves the deployment worked

The app intentionally looks different depending on which version you're running:

| Environment | Color  | Version | Visual Theme | Extra Feature     |
|-------------|--------|---------|--------------|-------------------|
| Blue        | Blue   | v1      | Blue header  | —                 |
| Green       | Green  | v2      | Green header | Dark Mode toggle  |

This means when you switch traffic from blue → green, **you see it immediately** in the browser.

---

## How the Color/Version is Controlled

Everything is driven by environment variables — no code changes between blue and green:

| Variable       | Default    | Description                             |
|----------------|------------|-----------------------------------------|
| `APP_COLOR`    | `blue`     | `blue` or `green` — drives the UI theme |
| `APP_VERSION`  | `v1`       | `v1` or `v2` — shown in stats + /version |
| `APP_ENV`      | `production` | Label shown in the UI                |
| `DATABASE_URL` | SQLite     | `sqlite:///./deploytrack.db` or PostgreSQL URL |
| `PORT`         | `5000`     | Port the app listens on                 |

---

## API Endpoints

| Method  | Path                     | Description                        |
|---------|--------------------------|------------------------------------|
| `GET`   | `/`                      | Web UI (HTML dashboard)            |
| `GET`   | `/health`                | Health check — used by K8s probes  |
| `GET`   | `/version`               | Returns version, color, environment |
| `GET`   | `/stats`                 | Request count + uptime (JSON)      |
| `GET`   | `/api/releases`          | List all releases                  |
| `POST`  | `/api/releases`          | Record a new release               |
| `PATCH` | `/api/releases/{id}`     | Update a release status            |
| `GET`   | `/docs`                  | Swagger UI (auto-generated)        |

### Health Check Response
```json
{
  "status": "healthy",
  "version": "v1",
  "color": "blue",
  "environment": "production",
  "uptime_seconds": 3721
}
```

### Version Response
```json
{
  "version": "v2",
  "color": "green",
  "environment": "production",
  "build": "green-v2"
}
```

---

## Database

The app uses SQLAlchemy and works with both **SQLite** (local, no setup) and **PostgreSQL** (production).

The `releases` table:

| Column        | Type     | Description                                |
|---------------|----------|--------------------------------------------|
| `id`          | Integer  | Auto-increment primary key                 |
| `version`     | String   | e.g. `v1`, `v2`, `v2.1`                   |
| `color`       | String   | `blue` or `green`                          |
| `environment` | String   | `production`, `staging`, etc.              |
| `status`      | String   | `active`, `rolled_back`, `retired`         |
| `deployed_at` | DateTime | Deployment timestamp                       |
| `notes`       | Text     | Optional notes about the deployment        |

On first run, 3 seed rows are added automatically so the UI isn't empty.

---

## Run Without Docker (for understanding)

```bash
cd app/
pip install -r requirements.txt

# Run as blue/v1
APP_COLOR=blue APP_VERSION=v1 uvicorn main:app --reload --port 5000

# Open: http://localhost:5000
# API docs: http://localhost:5000/docs
```

Now run the same app as green/v2 on a different port:
```bash
APP_COLOR=green APP_VERSION=v2 uvicorn main:app --reload --port 5001
```

Open both side by side — same code, completely different look. This is the whole point of blue-green deployments.

---

## Dockerfile

The Dockerfile follows the same pattern as all other projects:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```

**Questions to think about before moving on:**
- How does `ENV APP_COLOR=blue` in the Dockerfile interact with `-e APP_COLOR=green` at runtime?
- The app uses SQLite by default. What changes when you point it at PostgreSQL?
- Why does the `/health` endpoint matter for blue-green deployments? What would happen without it?
- Why is the same Docker image used for both blue and green — just with different env vars?

---

## Next Step

Go to [../local/README.md](../local/README.md) to run blue and green side by side with Docker Compose.
