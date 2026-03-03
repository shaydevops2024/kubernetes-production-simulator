# RegionWatch — Application Overview

RegionWatch is a **Multi-Region Disaster Recovery Dashboard** — a Python FastAPI web application that visualises the real-time health and status of a multi-region deployment.

Two instances run simultaneously to simulate **primary** and **secondary** regions. The same Docker image is used for both; the region's role is controlled entirely by environment variables.

---

## What It Does

```
┌─────────────────────────────────────────────────────────────┐
│                   RegionWatch Dashboard                      │
│                                                             │
│   Region: EU-WEST-1  (PRIMARY)          ● ACTIVE           │
│   ─────────────────────────────────────────────────────    │
│   DB Health       Replication Lag   Last Backup   Uptime   │
│    ● UP               0.12 s          23m ago     2h 14m   │
│                                                             │
│   [ Trigger Backup ]        [ Simulate Failover ]          │
│                                                             │
│   RTO: 5m  │  RPO: 1h  │  Backup count: 7                 │
│                                                             │
│   Failover History:                                         │
│   PRIMARY → SECONDARY  RTO: 42s    14 days ago             │
└─────────────────────────────────────────────────────────────┘
```

The dashboard auto-refreshes every 5 seconds and shows:
- **Active region** — which region is currently serving production traffic
- **DB Health** — simulated database connectivity
- **Replication Lag** — simulated PostgreSQL streaming replication lag (0.05–2.5 s)
- **Last Backup / Next Backup** — simulated Velero backup schedule
- **RTO / RPO gauges** — current vs target recovery objectives
- **Failover History** — log of every simulated failover with RTO achieved

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/`          | Dashboard HTML |
| `GET`  | `/health`    | Health check (returns JSON) |
| `GET`  | `/metrics`   | Prometheus metrics |
| `GET`  | `/api/status`    | Full JSON status object |
| `POST` | `/api/failover`  | Simulate a failover event |
| `POST` | `/api/backup`    | Simulate triggering a backup |

### `/api/status` response

```json
{
  "region_name": "eu-west-1",
  "region_role": "primary",
  "is_active": true,
  "active_region": "primary",
  "version": "v1",
  "environment": "production",
  "uptime_seconds": 3600,
  "db_healthy": true,
  "replication_lag": 0.123,
  "last_backup_time": "2024-01-01T10:00:00+00:00",
  "next_backup_time": "2024-01-01T11:00:00+00:00",
  "backup_age_seconds": 3600,
  "backup_count": 7,
  "rto_target": 300,
  "rpo_target": 3600,
  "failover_history": [...]
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REGION_NAME` | `primary` | Human-readable region label (e.g. `eu-west-1`) |
| `REGION_ROLE` | `primary` | `primary` or `secondary` — controls dashboard theme and logic |
| `APP_VERSION` | `v1` | Displayed in the UI |
| `APP_ENV` | `production` | `production` or `development` |
| `DATABASE_URL` | *(empty)* | PostgreSQL connection string |
| `REPLICA_DB_URL` | *(empty)* | Replica DB URL (used on the secondary) |
| `MINIO_ENDPOINT` | `http://minio:9000` | MinIO S3 endpoint for Velero backups |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |

> **Note:** Database and MinIO connections are used for health display purposes.
> The replication lag and backup schedule shown in the dashboard are simulated so the app
> works even if databases are not connected (useful for the `local/` phase).

---

## Why Two Instances?

The **exact same Docker image** is deployed twice:

```
                  Same image
                      │
          ┌───────────┴───────────┐
          │                       │
   REGION_ROLE=primary     REGION_ROLE=secondary
   REGION_NAME=eu-west-1   REGION_NAME=us-east-1
          │                       │
   Blue UI theme          Gray UI theme
   Shows "● ACTIVE"       Shows "Standby" when not active
```

This mirrors how real multi-region deployments work:
- Same application code runs everywhere
- Region-specific configuration comes from the environment
- An external load balancer or DNS entry decides which region is "active"

---

## Running the App Directly

```bash
# Install dependencies
pip install -r requirements.txt

# Run as primary
REGION_NAME=eu-west-1 REGION_ROLE=primary uvicorn main:app --port 5000

# Run as secondary (in another terminal)
REGION_NAME=us-east-1 REGION_ROLE=secondary uvicorn main:app --port 5001
```

**→ Go to [../local/README.md](../local/README.md) for the Docker Compose setup.**
