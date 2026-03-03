# Phase 2 — Run Locally with Docker Compose

This Docker Compose setup simulates a **full multi-region disaster recovery environment** on your laptop.

You don't need a Kubernetes cluster for this phase. Just Docker.

---

## Architecture

```
                     You (browser)
                          │
                   http://localhost:5858
                          │
                    ┌─────▼──────┐
                    │   nginx    │  ← "global load balancer"
                    │ (router)   │     routes to active region
                    └──┬──────┬──┘
                       │      │
              (primary)│      │(secondary)
                       │      │
            ┌──────────▼─┐  ┌─▼──────────────┐
            │ app-primary │  │ app-secondary  │
            │ eu-west-1   │  │ us-east-1      │
            │ port 5860   │  │ port 5861      │
            └──────┬──────┘  └───────┬────────┘
                   │                 │
         ┌─────────▼──┐    ┌─────────▼──┐
         │  postgres  │    │  postgres  │
         │  (primary) │    │ (secondary)│
         └────────────┘    └────────────┘
                   │
             ┌─────▼──────┐
             │    MinIO   │  ← simulates S3 (Velero backup target)
             │  port 9000 │    console at port 9001
             └────────────┘
```

**The three access points:**

| URL | Description |
|-----|-------------|
| http://localhost:5858 | **LIVE** — nginx routes to active region (primary by default) |
| http://localhost:5860 | Direct access to **PRIMARY** region |
| http://localhost:5861 | Direct access to **SECONDARY** region |
| http://localhost:9001 | **MinIO Console** — inspect backup storage (user: `minioadmin` / `minioadmin`) |

---

## Step 1 — Start Everything

```bash
cd hands-on-projects/project-11-multi-region-disaster-recovery/local
docker compose up --build
```

Wait for all containers to report healthy (takes ~30 seconds):

```
✔ minio           healthy
✔ postgres-primary   healthy
✔ postgres-secondary healthy
✔ app-primary        healthy
✔ app-secondary      healthy
✔ nginx              started
```

---

## Step 2 — Explore the Dashboard

Open **http://localhost:5858** in your browser.

You should see the **RegionWatch** dashboard showing:
- **eu-west-1** as the active region (PRIMARY, blue theme)
- Database health: UP
- Replication lag: ~0.1–0.5 s (simulated)
- Last backup: a few minutes ago

Now open **http://localhost:5861** (direct secondary access).
You see the **us-east-1** dashboard — same app, different role (STANDBY, gray theme).

**Question to ask yourself:** What is different between the two dashboards? Why?

---

## Step 3 — Simulate a Backup

Click **"Trigger Backup"** on the primary region dashboard.
Watch the "Last Backup" metric reset to "0s ago".

In a real environment, this is Velero snapshotting your entire cluster state to S3.

Check **http://localhost:9001** (MinIO Console) — in the Kubernetes phase, your Velero backups will appear here as objects in the `velero` bucket.

---

## Step 4 — Simulate a Failover (Dashboard Button)

On the **http://localhost:5858** dashboard, click **"Simulate Failover"**.

This simulates the application-level awareness of a failover — the "active region" toggles. But nginx still routes to `app-primary`.

**Question:** Why does clicking the button not change which server nginx talks to?

> Because nginx is a separate system. In production, failover requires updating DNS records or a load balancer rule — the application itself doesn't control routing.

---

## Step 5 — Simulate a Real Failover (nginx)

This is the hands-on DR test. We'll switch nginx to route to the secondary region.

**1. Edit `nginx/nginx.conf`:**

Find line:
```nginx
proxy_pass  http://primary_region;   # ← CHANGE to secondary_region to failover
```
Change it to:
```nginx
proxy_pass  http://secondary_region;
```

**2. Reload nginx (zero-downtime):**

```bash
docker compose exec nginx nginx -s reload
```

**3. Verify:**
```bash
curl http://localhost:5858/health
# Should now show: "region_role": "secondary", "region_name": "us-east-1"
```

Open http://localhost:5858 — you are now on the **SECONDARY** region.
The primary region is still running at http://localhost:5860 — instant rollback available.

**4. Rollback:**

Change `nginx.conf` back to `primary_region`, reload:
```bash
docker compose exec nginx nginx -s reload
```

---

## Step 6 — Measure Your RTO

Time how long the failover takes:

```bash
# Start a watch loop
while true; do
  curl -s http://localhost:5858/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['region_role'], d['region_name'])"
  sleep 0.5
done
```

While this is running, change the nginx config and reload.
Count how many requests fail (if any). That's your practical RTO.

**Key insight:** nginx reload is near-zero-downtime.
In Kubernetes, changing a Service selector is also near-instant.
DNS-based failover can take 30–300 seconds depending on TTL.

---

## Step 7 — Check RPO

RPO = how much data would be lost if the primary died right now.

```bash
# Check backup age
curl -s http://localhost:5860/api/status | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Backup age:', d['backup_age_seconds'], 'seconds')
print('RPO exposure:', d['backup_age_seconds'], 'seconds of data could be lost')
"
```

If your last backup was 45 minutes ago, you could lose up to 45 minutes of data.
This is why Velero's scheduled backups (every 15 min, 30 min, 1 hour) matter.

---

## Common Commands

```bash
# Start everything
docker compose up --build

# Check all container health
docker compose ps

# View logs (follow)
docker compose logs -f app-primary
docker compose logs -f app-secondary

# Check primary status
curl -s http://localhost:5860/api/status | python3 -m json.tool

# Check secondary status
curl -s http://localhost:5861/api/status | python3 -m json.tool

# Reload nginx after config change
docker compose exec nginx nginx -s reload

# Stop everything
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Port 5858 refused | nginx not started | `docker compose ps` — check if nginx container is up |
| App shows "Loading…" forever | App container still starting | Wait 30s, refresh; run `docker compose logs app-primary` |
| MinIO Console login fails | Wrong credentials | Use `minioadmin` / `minioadmin` |
| Port already in use | Another container using 5858/5860/5861 | `docker ps` to find conflicts; stop with `docker stop <id>` |
| Build fails | Missing Python dep | Run `docker compose build --no-cache` |

---

## What You Learned

After completing this phase you should understand:

1. **Why two identical instances** — same image, different env vars = different regions
2. **The role of nginx** — external load balancer / DNS proxy, not the application itself
3. **RTO mechanics** — nginx reload or K8s Service selector patch = near-zero RTO
4. **RPO mechanics** — backup frequency determines how much data you can lose
5. **MinIO as S3** — object storage for Velero backup artifacts
6. **Replication lag** — always non-zero; the secondary is always slightly behind

---

## Next Step

**→ Go to [../main/README.md](../main/README.md) to deploy this to Kubernetes — across two Kind clusters.**
