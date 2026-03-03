# DeployInsight — Sample Application

This is the pre-built application you will deploy, version, and roll out across the project.
Your job is **not** to write this code — your job is to make it run reliably at scale using
real DevOps tooling.

## What the app does

**DeployInsight** is a minimal task-management web app designed to demonstrate deployment
strategies visually. It intentionally has:

- A live dashboard at `/` that refreshes every 3 seconds
- A colour-coded header (blue = v1, green = v2) so you can **see** which version is serving traffic
- A "Simulate Bad Deployment" button that injects a 30 % error rate — this is what triggers
  the automated rollback in Argo Rollouts
- Prometheus metrics at `/metrics` so Grafana can graph traffic, errors and latency

## v1 vs v2

The same Docker image supports both versions via environment variables:

| Env variable  | v1           | v2             |
|---------------|--------------|----------------|
| `APP_VERSION` | `v1`         | `v2`           |
| `APP_COLOR`   | `blue`       | `green`        |

v2 adds task **priority** and **tags** fields to the API, and shows an enhanced dashboard.
This is just enough change to make a realistic upgrade story.

## API reference

| Method   | Path                | Description                                   |
|----------|---------------------|-----------------------------------------------|
| `GET`    | `/`                 | HTML dashboard (auto-refreshes every 3 s)     |
| `GET`    | `/health`           | Liveness probe — returns uptime and version   |
| `GET`    | `/ready`            | Readiness probe                               |
| `GET`    | `/metrics`          | Prometheus metrics                            |
| `GET`    | `/version`          | Version, colour, enabled features             |
| `GET`    | `/tasks`            | List all tasks                                |
| `POST`   | `/tasks`            | Create a task `{ title, priority, tags }`     |
| `PATCH`  | `/tasks/{id}/done`  | Mark task complete                            |
| `DELETE` | `/tasks/{id}`       | Remove a task                                 |
| `POST`   | `/break`            | Inject 30 % synthetic error rate (demo)       |
| `POST`   | `/fix`              | Reset error rate to 0                         |

## Prometheus metrics exposed

| Metric                          | Type      | Labels                              |
|---------------------------------|-----------|-------------------------------------|
| `app_requests_total`            | Counter   | `method`, `endpoint`, `status`, `version` |
| `app_request_duration_seconds`  | Histogram | `method`, `endpoint`, `version`     |
| `app_errors_total`              | Counter   | `endpoint`, `version`               |
| `app_configured_error_rate`     | Gauge     | `version`                           |

These are the metrics Argo Rollouts' AnalysisTemplate queries to decide whether to promote
or abort a canary/blue-green rollout.

## Run standalone (development only)

```bash
pip install -r requirements.txt

# v1
APP_VERSION=v1 APP_COLOR=blue python main.py

# v2
APP_VERSION=v2 APP_COLOR=green APP_PORT=4546 python main.py
```

Open http://localhost:4545 for v1, http://localhost:4546 for v2.

> **Note:** For a full local setup with load balancing and monitoring, use the `../local/` folder.
