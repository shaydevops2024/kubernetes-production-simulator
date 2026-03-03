# Local Setup — Docker Compose

Run the full stack locally before touching Kubernetes. This environment mirrors what you will
build in production, but uses Docker Compose + nginx weights instead of Argo Rollouts.

## What runs here

| Container    | Purpose                              | Local URL                       |
|--------------|--------------------------------------|---------------------------------|
| `app-v1`     | Blue version of DeployInsight        | http://localhost:4551 (direct)  |
| `app-v2`     | Green version of DeployInsight       | http://localhost:4552 (direct)  |
| `nginx-lb`   | Traffic splitter (canary simulator)  | http://localhost:4545 (main UI) |
| `prometheus` | Metrics collector                    | http://localhost:4447           |
| `grafana`    | Dashboards                           | http://localhost:4446           |

## Prerequisites

```bash
docker --version      # 24+
docker compose version # v2.x
```

## Start the stack

```bash
# From this directory (local/)
docker compose up --build -d

# Watch logs
docker compose logs -f
```

Wait ~15 seconds for health checks to pass, then open http://localhost:4545.

## Grafana setup

1. Open http://localhost:4446 and log in with `admin / admin`
2. The **Zero-Downtime Deployment Monitor** dashboard auto-loads — no manual import needed

## Exercise 1 — Understand the app

1. Open http://localhost:4545 — you see the **v1 blue** dashboard (nginx sends 100 % to v1)
2. Open http://localhost:4551 — v1 directly
3. Open http://localhost:4552 — v2 directly (notice the **green** header and extra task fields)
4. Create a few tasks, then hit **Simulate Bad Deployment** in v2 and watch the error gauge in Grafana spike

## Exercise 2 — Canary rollout (nginx weight edit)

This simulates Argo Rollouts canary steps, but manually so you understand what's happening.

**Step 1:** Start the canary — send 10 % of traffic to v2

Edit `nginx/nginx.conf`:
```nginx
upstream app_backend {
    server app-v1:4545 weight=9;
    server app-v2:4545 weight=1;   # ~10 % canary
}
```

Apply without downtime:
```bash
docker compose restart nginx-lb
```

Open http://localhost:4545 and refresh several times. Occasionally you'll see the **green** dashboard — that's v2.

**Step 2:** Check metrics in Grafana — v2 should be getting ~10 % of traffic.

**Step 3:** Promote to 50 %

```nginx
upstream app_backend {
    server app-v1:4545 weight=5;
    server app-v2:4545 weight=5;   # 50/50
}
```

**Step 4:** Full cutover — mark v1 as `down` so all traffic goes to v2

```nginx
upstream app_backend {
    server app-v1:4545 down;       # drain v1 (nginx rejects weight=0)
    server app-v2:4545 weight=10;  # 100 % v2
}
```

## Exercise 3 — Blue-Green rollout

In a true blue-green switch, traffic flips all at once — use the `down` flag to take a server out completely:

```nginx
# Blue active (before)
server app-v1:4545 weight=10;
server app-v2:4545 down;

# Green active (after) — single edit, zero downtime
server app-v1:4545 down;
server app-v2:4545 weight=10;
```

Compare this to canary: **higher risk, but instant rollback** by just flipping back.

## Exercise 4 — Simulate a bad deployment + rollback

1. Make sure v2 receives some traffic (weight ≥ 1)
2. Hit the **Simulate Bad Deployment** button on the v2 dashboard (http://localhost:4552)
3. Watch the **Error Rate v2** gauge in Grafana climb above 5 %
4. This is the threshold that triggers automatic rollback in production
5. Roll back manually by adding `down` to v2 (or setting weight=1→remove it); hit **Fix** to stop the errors
6. In the Kubernetes section this rollback happens automatically via Argo Rollouts

## Generate traffic for more interesting graphs

```bash
# From anywhere with curl installed
while true; do
  curl -s http://localhost:4545/tasks > /dev/null
  curl -s http://localhost:4545/health > /dev/null
  sleep 0.5
done
```

## Stop the stack

```bash
docker compose down
docker compose down -v   # also removes stored metrics/dashboards
```

## Key concepts practised here

| Concept              | How it maps to production Kubernetes            |
|----------------------|-------------------------------------------------|
| nginx weight=1/9     | Argo Rollouts `steps: setWeight: 10`            |
| nginx weight 0→10    | Argo Rollouts blue-green `autoPromotionEnabled` |
| Error rate > 5 %     | AnalysisTemplate `successCondition`             |
| `docker restart`     | Argo Rollouts automated rollback                |

> **Next step:** Deploy this to Kubernetes using Argo Rollouts → see `../main/README.md`
