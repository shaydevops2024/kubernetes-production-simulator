# Local — Run the Full Observability Stack

Run the complete observability stack on your machine with a single command. This is your playground before deploying to Kubernetes.

---

## What You'll Run

```
observe-app   → http://localhost:8000   (app dashboard + /metrics)
prometheus    → http://localhost:9090   (metrics store, PromQL)
grafana       → http://localhost:3000   (dashboards — admin/admin)
loki          → http://localhost:3100   (log store, internal)
promtail      → (no port — reads Docker logs, pushes to Loki)
jaeger        → http://localhost:16686  (trace UI)
alertmanager  → http://localhost:9093   (alert management)
```

---

## Quick Start

```bash
cd hands-on-projects/project-05-observability-stack/local
docker compose up --build
```

Wait about 30 seconds for all services to start, then open:

- **App Dashboard**: http://localhost:8000
- **Grafana**: http://localhost:3000 (login: admin / admin)
  - A pre-built **"ObserveApp Overview"** dashboard is already provisioned
- **Prometheus**: http://localhost:9090
- **Jaeger UI**: http://localhost:16686
- **AlertManager**: http://localhost:9093

---

## Step-by-Step Learning Guide

### Step 1 — Explore the App Dashboard

Open http://localhost:8000. You'll see:
- Live stats updating every 3 seconds (active sessions, queue depth)
- Simulation controls to trigger observable events
- A live log stream showing structured JSON logs

**Try it:** Click "Enable" on **Error Mode** and watch the logs turn red.

---

### Step 2 — Query Prometheus

Open http://localhost:9090 → Graph tab.

Run these queries one by one and observe the results:

```promql
# Total requests by status code
http_requests_total

# Request rate per second (last 1 minute)
rate(http_requests_total{job="observe-app"}[1m])

# Error rate %
100 * sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# P99 latency
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Active sessions
app_active_sessions
```

**Try it:** Enable **Error Mode** on the app, wait 30s, then re-run the error rate query.

---

### Step 3 — Explore the Grafana Dashboard

Open http://localhost:3000 → Dashboards → "ObserveApp Overview".

The dashboard shows:
- HTTP Request Rate (time series)
- Error Rate % (gauge, turns red above 20%)
- P99 Latency (stat, color-coded by threshold)
- Events Tracked by Type (time series)
- SLO: 30-minute Availability (stat)
- Application Logs (live Loki log panel at the bottom)

**Try it:** Enable **Slow Mode** on the app and watch the P99 latency panel change.

---

### Step 4 — Query Logs in Grafana with LogQL

In Grafana → Explore → select **Loki** as the datasource.

Try these LogQL queries:

```logql
# All app logs
{container="observe-app"}

# Only error logs
{container="observe-app"} |= "error"

# Filter by log level label (set by promtail)
{container="observe-app", level="ERROR"}

# Extract JSON fields and filter
{container="observe-app"} | json | status >= 400

# Count error rate over time
sum(rate({container="observe-app", level="ERROR"}[1m]))
```

---

### Step 5 — Explore Distributed Traces in Jaeger

Open http://localhost:16686.

1. Select service: **observe-app**
2. Click **Find Traces**
3. Click on any trace to see the request spans
4. Enable **Slow Mode** on the app and find slow traces (look for traces > 1s)

**Note:** Traces are only generated for HTTP requests to `/api/*` paths.

---

### Step 6 — Check Alerting Rules

Open Prometheus → Alerts (http://localhost:9090/alerts).

You'll see the rules defined in `prometheus/rules/app-alerts.yml`. When you enable **Error Mode** on the app, the `AppHighErrorRate` alert should fire after about 1 minute.

Then check AlertManager (http://localhost:9093) to see the active alert.

---

### Step 7 — Trigger Each Alert

| Simulation | Expected Alert | Wait |
|------------|---------------|------|
| Enable **Error Mode** | `AppHighErrorRate` → `AppCriticalErrorRate` | ~1 min |
| Enable **Slow Mode** | `AppHighP99Latency` | ~2 min |
| Enable **Error Mode** | `AppReportFailureRate` | ~2 min |

After triggering, reset simulations and watch alerts resolve.

---

## Task Checklist

Work through these tasks to build your understanding:

- [ ] Start the stack and confirm all services are reachable
- [ ] Open the Grafana pre-built dashboard and understand each panel
- [ ] Write 3 PromQL queries manually in Prometheus UI
- [ ] Enable Error Mode, find the alert firing in Prometheus, then in AlertManager
- [ ] Find a distributed trace in Jaeger UI for a `/api/report` request
- [ ] Query logs in Grafana's Explore view using LogQL
- [ ] Stop one service (`docker compose stop loki`) and observe the impact
- [ ] Add a new Grafana panel: total event count by type as a bar chart

---

## Common Issues

**Logs not appearing in Loki / Grafana:**
- Promtail needs access to the Docker socket. On some systems this requires running Docker with elevated permissions.
- Check Promtail logs: `docker compose logs promtail`
- Verify the `observe-app` container has the label `logging=promtail` (it does by default)

**Jaeger shows no traces:**
- Traces are only sent when HTTP requests hit `/api/*` endpoints.
- Go to http://localhost:8000 and use the simulation controls to generate traffic.
- Check the app logs for `"Tracing enabled"` on startup.

**Port already in use:**
- Change the host port in `docker-compose.yml` (left side of `HOST:CONTAINER`)

---

## Stopping

```bash
docker compose down          # Stop containers, keep volumes
docker compose down -v       # Stop and delete all data (reset everything)
```
