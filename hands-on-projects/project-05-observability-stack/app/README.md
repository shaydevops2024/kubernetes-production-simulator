# App — ObserveApp

ObserveApp is a pre-built Python/FastAPI application that simulates a SaaS analytics platform. It is already instrumented with Prometheus metrics, OpenTelemetry distributed tracing, and structured JSON logging.

**You do not write the application code.** Your job is to deploy it and observe it.

---

## What the App Does

ObserveApp simulates an analytics platform with background activity:

- **Active sessions** — a gauge that drifts between 20 and 80 users (or 300 in high traffic mode)
- **Event tracking** — counters for `page_view`, `button_click`, `form_submit`, `api_call`, `error_thrown`
- **Report generation** — periodic background jobs with measurable duration and failure rates
- **Processing queue** — a depth gauge that fluctuates over time

It also has a web UI at `http://localhost:8000` with live stats and simulation controls.

---

## Observability Signals

### Prometheus Metrics (exposed at /metrics)

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | All HTTP requests, labeled by method, path, and status code |
| `http_request_duration_seconds` | Histogram | Request latency with 10 buckets |
| `app_active_sessions` | Gauge | Simulated concurrent users |
| `app_events_tracked_total` | Counter | Analytics events by type |
| `app_reports_generated_total` | Counter | Reports by status (success/error) |
| `app_report_generation_seconds` | Histogram | Report duration |
| `app_queue_depth` | Gauge | Items waiting in the processing queue |
| `observe_app_info` | Info | App version and environment |

**Key PromQL queries to try:**
```
# Request rate per second
rate(http_requests_total{job="observe-app"}[1m])

# Error rate %
100 * sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# P99 latency
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# 30-minute availability SLO
1 - (sum(rate(http_requests_total{status=~"5.."}[30m])) / sum(rate(http_requests_total[30m])))
```

### Structured JSON Logs

Every log line is a JSON object written to stdout:
```json
{"timestamp": "2024-01-01T12:00:00.000Z", "level": "INFO", "name": "observe-app",
 "message": "request completed", "method": "GET", "path": "/api/stats",
 "status": 200, "duration_ms": 4.2, "request_id": "a1b2c3d4"}
```

Promtail collects these from Docker and ships them to Loki. In Grafana you can run:
```
{container="observe-app"}
{container="observe-app"} |= "error"
{container="observe-app"} | json | level = "ERROR"
```

### Distributed Traces (OpenTelemetry)

When the `OTLP_ENDPOINT` environment variable is set, the app sends traces to Jaeger (local) or Tempo (Kubernetes) via OTLP HTTP. Each HTTP request generates a trace with spans.

In Jaeger UI: search for service `observe-app`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard UI |
| GET | `/metrics` | Prometheus metrics |
| GET | `/health` | Health check |
| GET | `/api/stats` | Current stats (used by UI) |
| POST | `/api/track?event_type=X` | Track an analytics event |
| POST | `/api/report?report_type=X` | Generate a report (with latency) |
| POST | `/api/simulate/errors` | Toggle error injection (30% HTTP 500s) |
| POST | `/api/simulate/slowdown` | Toggle latency injection (0.8–3s) |
| POST | `/api/simulate/traffic` | Toggle high traffic simulation |
| POST | `/api/simulate/reset` | Reset all simulations |

OpenAPI docs are at `http://localhost:8000/docs`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `local` | Shown in app metrics and logs |
| `OTLP_ENDPOINT` | `` (disabled) | OTLP HTTP base URL for traces (e.g. `http://jaeger:4318`) |

---

## Running Standalone (without Docker)

```bash
cd app
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Open: http://localhost:8000
# Metrics: http://localhost:8000/metrics
```

Note: Without `OTLP_ENDPOINT` set, tracing is silently disabled. All other signals (metrics + logs) work without any external dependencies.

---

## Dockerfile

The app follows the standard pattern from this project:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Questions to think about:**
- Why is `python:3.11-slim` used instead of `python:3.11`?
- The app runs as root inside the container — what's the security implication?
- How would you add a `/health` check to the Dockerfile?
- What would a multi-stage build look like here?
