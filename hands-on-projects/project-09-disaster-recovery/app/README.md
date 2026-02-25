# App — DR Operations Dashboard

This is the "critical business service" you will protect with a disaster recovery system. It's a FastAPI application that stores operational records in PostgreSQL and displays a live monitoring dashboard.

**You don't write any of this code.** Your job is to deploy it, back it up, and recover it.

---

## What the App Does

A production-style operations dashboard that:
- Stores critical business records in PostgreSQL (financial, compliance, inventory records)
- Connects to MinIO to list Velero backup objects
- Exposes a REST API consumed by the dashboard UI
- Shows real-time status of primary and secondary "regions"

```
Browser (http://localhost:4545)
        │
        ▼
  FastAPI App (port 4545)
        │
        ├── PostgreSQL Primary  (postgres-primary:5432)
        ├── PostgreSQL Secondary (postgres-secondary:5433)
        └── MinIO Object Storage (minio:9000)
```

---

## Running Standalone (without Docker)

Requires Python 3.11+ and no external services — the app falls back to mock data gracefully.

```bash
cd app/
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 4545 --reload
```

Open: http://localhost:4545

The dashboard shows **demo mode** when no database is connected — this is expected.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://dr:drpassword@localhost:5432/dr_primary` | Primary PostgreSQL |
| `DATABASE_SECONDARY_URL` | `postgresql://dr:drpassword@localhost:5433/dr_secondary` | Secondary PostgreSQL (DR target) |
| `MINIO_ENDPOINT` | `http://minio:9000` | MinIO S3-compatible endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | `dr-backups` | Bucket for backup listings |
| `APP_ENV` | `development` | Environment label |
| `PORT` | `4545` | Port to listen on |

---

## API Reference

```
GET  /              → Dashboard HTML
GET  /health        → Health check
GET  /api/status    → All region/storage status
GET  /api/records   → List critical records (?region=primary|secondary)
POST /api/records   → Create a new record
GET  /api/backups   → List backups from MinIO
GET  /api/metrics   → RPO/RTO metrics and history
```

---

## Key Design Decisions

**Why graceful degradation?**
The app is designed to run even without PostgreSQL or MinIO. When databases are disconnected, it returns realistic mock data so you can still see the UI during development. When you deploy the full stack, live data appears automatically.

**Why two PostgreSQL instances?**
One simulates the "primary region" and one simulates the "secondary/DR region". In a real DR setup, these would be in different data centers. Here, they both run locally but represent the same concept — your data must survive the loss of the primary.

**Why MinIO?**
MinIO is an S3-compatible object store that runs completely locally. Velero (the backup tool you'll install) uses S3 as its backend. This means your local setup is functionally identical to using AWS S3 in production — you just point Velero at a different endpoint.

---

## What You'll Do as a DevOps Engineer

The app is pre-built. Your tasks start here:

1. **Containerize and verify** — understand the Dockerfile and build the image
2. **Run locally** — use Docker Compose (`../local/`) to start the full stack
3. **Deploy to Kubernetes** — write manifests, deploy to your Kind cluster
4. **Install Velero** — configure backup to MinIO
5. **Schedule backups** — set up hourly incremental + daily full backups
6. **Test recovery** — simulate failure, restore, measure RTO
7. **Add chaos** — use LitmusChaos to inject failures and validate resilience
8. **Monitor** — add Prometheus metrics and Grafana dashboards

---

## Next Step

→ Go to [../local/README.md](../local/README.md) to run the full stack locally
