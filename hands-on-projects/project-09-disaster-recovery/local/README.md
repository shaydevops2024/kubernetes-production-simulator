# Local — Running the DR Stack with Docker Compose

Get the full disaster recovery stack running on your machine. By the end of this step you'll have:
- A critical business service with live data in two PostgreSQL instances
- MinIO running as a local S3-compatible backup store
- A monitoring dashboard at http://localhost:4545

---

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose v2)
- At least 3 GB of free RAM
- Ports 4545, 5432, 5433, 9000, 9001 not in use

```bash
docker --version        # Docker 24+
docker compose version  # v2+
```

---

## Run It

```bash
# From this directory (local/)
docker compose up --build
```

First build takes ~2 minutes. Once all services are healthy:

| Service | URL | Purpose |
|---------|-----|---------|
| **DR Dashboard** | http://localhost:4545 | The critical app you're protecting |
| **MinIO Console** | http://localhost:9001 | Backup storage browser (admin/minioadmin) |
| **Postgres Primary** | localhost:5432 | Primary region database |
| **Postgres Secondary** | localhost:5433 | DR region database |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Docker Compose Network (dr-net)                 │
│                                                                  │
│  ┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐ │
│  │  DR App      │   │ postgres-primary │   │  MinIO           │ │
│  │  (port 4545) │──▶│ (port 5432)      │   │  (ports 9000/1)  │ │
│  │              │   └─────────────────┘   └──────────────────┘ │
│  │              │   ┌──────────────────┐        ▲              │
│  │              │──▶│ postgres-secondary│        │              │
│  │              │   │ (port 5433)       │   Backup bucket       │
│  └──────────────┘   └──────────────────┘   "dr-backups"        │
└─────────────────────────────────────────────────────────────────┘
```

---

## DevOps Tasks

### Task 1 — Explore the Stack

```bash
# See all running containers
docker compose ps

# Watch logs from all services
docker compose logs -f

# Watch only the app logs
docker compose logs -f app
```

**Question:** How does the app discover the database by hostname `postgres-primary`? What Docker feature makes this work?

---

### Task 2 — Inspect the Databases

```bash
# Connect to the primary database
docker compose exec postgres-primary psql -U dr -d dr_primary

# Inside psql:
\dt                              -- list tables
SELECT * FROM critical_records;  -- see seeded records
\q

# Check secondary database (should be empty until a restore)
docker compose exec postgres-secondary psql -U dr -d dr_secondary -c "SELECT COUNT(*) FROM critical_records;"
```

**Question:** Why does the primary have 10 records and the secondary has 0? What is the secondary's purpose?

---

### Task 3 — Explore MinIO

```bash
# List buckets using the mc CLI inside the minio container
docker compose exec minio mc ls local/

# See the dr-backups bucket
docker compose exec minio mc ls local/dr-backups/
```

Open the MinIO console at http://localhost:9001 (login: minioadmin / minioadmin) and explore the `dr-backups` bucket.

**Question:** MinIO is "S3-compatible". What does that mean? Why does Velero work with both MinIO and AWS S3 without code changes?

---

### Task 4 — Simulate a Manual Backup

In the real Kubernetes setup, Velero handles backups automatically. Here we simulate the concept by copying the database dump to MinIO:

```bash
# Dump the primary database
docker compose exec postgres-primary pg_dump -U dr dr_primary > backup_$(date +%Y%m%d_%H%M%S).sql

# Upload to MinIO
docker compose exec minio mc cp /dev/stdin local/dr-backups/manual-backup.sql < backup_*.sql

# List backups
docker compose exec minio mc ls local/dr-backups/
```

**Question:** This is a basic backup. What are the limitations of this approach vs. Velero? What does Velero back up that pg_dump misses?

---

### Task 5 — Simulate a Failure and Restore

```bash
# 1. Delete all records from the primary (simulate data loss)
docker compose exec postgres-primary psql -U dr -d dr_primary -c "DELETE FROM critical_records;"

# 2. Verify data is gone
docker compose exec postgres-primary psql -U dr -d dr_primary -c "SELECT COUNT(*) FROM critical_records;"
# Should return: 0

# 3. Restore from the backup
docker compose exec postgres-primary psql -U dr -d dr_primary < backup_*.sql

# 4. Verify recovery
docker compose exec postgres-primary psql -U dr -d dr_primary -c "SELECT COUNT(*) FROM critical_records;"
# Should return: 10

# 5. Refresh the dashboard
# Open http://localhost:4545 — records should reappear
```

**Question:** How long did the restore take? That's your local RTO. What would make this faster in production?

---

### Task 6 — RPO Calculation

**Recovery Point Objective** = how much data you can afford to lose.

```bash
# Add some new records
curl -X POST http://localhost:4545/api/records \
  -H "Content-Type: application/json" \
  -d '{"category":"financial","description":"New Q1 invoice batch","severity":"high"}'

# Now simulate a backup (note the time)
docker compose exec postgres-primary pg_dump -U dr dr_primary > backup_new.sql
BACKUP_TIME=$(date +%s)

# Wait 5 minutes, then add more records
sleep 10
curl -X POST http://localhost:4545/api/records \
  -H "Content-Type: application/json" \
  -d '{"category":"compliance","description":"GDPR deletion request","severity":"medium"}'

# Now simulate primary failure and restore from old backup
# Records added after BACKUP_TIME are LOST — that gap is your actual RPO
```

**Question:** If your backup runs every hour, what is your worst-case RPO? How do you reduce it?

---

### Task 7 — Health Checks

```bash
# Check the app health endpoint
curl http://localhost:4545/health

# Inspect health check details
docker inspect dr-app | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d[0]['State']['Health'], indent=2))"

# Check all service statuses
curl http://localhost:4545/api/status | python3 -m json.tool
```

**Question:** What happens to the dashboard if you stop postgres-primary? Does the app crash or degrade gracefully?

---

### Task 8 — Scale and Persistence

```bash
# Stop everything
docker compose down

# Restart WITHOUT the -v flag (data survives)
docker compose up -d

# Check records still exist
docker compose exec postgres-primary psql -U dr -d dr_primary -c "SELECT COUNT(*) FROM critical_records;"

# Now stop and remove volumes (data lost)
docker compose down -v
docker compose up -d

# Records are gone — just like a real disaster
docker compose exec postgres-primary psql -U dr -d dr_primary -c "SELECT COUNT(*) FROM critical_records;"
```

**Question:** `docker compose down` vs `docker compose down -v` — what's the difference? Which simulates data loss?

---

## Common Issues

**Port conflict:**
```bash
# Find what's using port 4545
lsof -i :4545

# Change the port in docker-compose.yml: "4546:4545"
```

**App in demo mode (mock data):**
The app shows "Running in demo mode" when it can't reach the database. Wait for `postgres-primary` to be healthy, then restart the app:
```bash
docker compose restart app
```

**MinIO init fails:**
```bash
docker compose logs minio-init
# Usually the minio service just needs a few more seconds
docker compose up minio-init  # re-run it
```

---

## Next Step

Once you're comfortable with the local setup, move on to [../main/README.md](../main/README.md) to deploy everything to Kubernetes and implement real disaster recovery with Velero.
