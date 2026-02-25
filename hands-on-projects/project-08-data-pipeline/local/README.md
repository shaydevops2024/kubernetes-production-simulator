# Local Setup — Docker Compose

Run the complete data pipeline on your laptop with a single command.

---

## What Runs Locally

| Service | Port | URL |
|---------|------|-----|
| Kafka (KRaft) | 9092 | — |
| Kafka UI | 8085 | http://localhost:8085 |
| TimescaleDB | 5432 | `postgresql://pipeline:pipeline123@localhost:5432/pipeline` |
| Pipeline Producer | 8090 | http://localhost:8090/stats |
| Pipeline Dashboard | 3000 | **http://localhost:3000** |

---

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- At least 4GB RAM available for Docker
- Ports 3000, 5432, 8085, 8090, 9092 free

---

## Start the Stack

```bash
cd hands-on-projects/project-08-data-pipeline/local
docker compose up --build
```

Wait about 60 seconds for Kafka and TimescaleDB to initialize.

Open the dashboard: **http://localhost:3000**

---

## Verify It Works

### 1. Check all containers are running
```bash
docker compose ps
```

Expected: all 5 services in `Up` or `healthy` state.

### 2. Check producer is publishing events
```bash
curl http://localhost:8090/stats
```

Expected: `events_published` counter increasing.

### 3. Browse Kafka topics (Kafka UI)

Open http://localhost:8085 → Topics → `sensor-events`

You should see messages flowing in. Click a message to inspect the JSON payload.

### 4. Check Kafka from CLI

```bash
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic sensor-events \
  --from-beginning \
  --max-messages 5
```

### 5. Check TimescaleDB

```bash
docker exec -it timescaledb psql -U pipeline -d pipeline -c \
  "SELECT sensor_id, avg_temperature, event_count, time FROM sensor_aggregates ORDER BY time DESC LIMIT 10;"
```

Once the Spark processor starts writing (after ~15–30 seconds), you'll see rows populating.

### 6. Check Spark processor logs

```bash
docker compose logs -f processor
```

Look for: `[processor] Batch N: wrote X aggregated rows`

---

## Useful Commands

```bash
# View logs for a specific service
docker compose logs -f producer
docker compose logs -f processor
docker compose logs -f dashboard

# Pause event generation (to simulate producer outage)
curl -X POST http://localhost:8090/control/pause

# Resume event generation
curl -X POST http://localhost:8090/control/resume

# Scale up the producer throughput (restart with new env)
docker compose up -d --no-deps -e EVENTS_PER_SECOND=50 producer

# Connect to TimescaleDB directly
docker exec -it timescaledb psql -U pipeline -d pipeline

# Check consumer lag manually
docker exec -it kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-processor \
  --describe
```

---

## Explore the Architecture

**Questions to answer while running locally:**

1. **Topic partitions** — Why does `sensor-events` have 3 partitions? How would you increase throughput by adding more?
2. **Consumer lag** — What happens to lag when you pause the producer? What if you kill the processor and restart it?
3. **Watermarking** — The Spark job uses a 10-second watermark. What does this mean for late-arriving events?
4. **Checkpointing** — Delete the `spark-checkpoints` volume. What happens to offsets when the processor restarts?
5. **Hypertable** — Run `SELECT * FROM timescaledb_information.hypertables;` — what does TimescaleDB do differently from plain PostgreSQL?

---

## Stop the Stack

```bash
# Stop and remove containers (keep volumes)
docker compose down

# Stop and remove everything including data
docker compose down -v
```

---

## Next Step

Once you understand the data flow locally, move to **`../main/README.md`** to deploy this on Kubernetes.
