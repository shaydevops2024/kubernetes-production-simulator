# App — Real-Time Data Pipeline

This folder contains the source code for all three application components. They are pre-built — **you don't write application code**. Your job is to containerize, deploy, and operate them.

---

## Components Overview

| Component | Port | Language | Role |
|-----------|------|----------|------|
| pipeline-producer | 8090 | Python | IoT event generator → Kafka |
| pipeline-processor | — | PySpark | Kafka consumer → aggregation → TimescaleDB |
| dashboard-ui | 3000 | HTML/JS/nginx | Live web dashboard (reads from TimescaleDB) |

---

## Architecture

```
pipeline-producer
    │  publishes JSON events every 100ms
    ▼
Kafka Topic: sensor-events
    │  Spark reads with micro-batch (5s window)
    ▼
pipeline-processor (PySpark)
    │  aggregates: avg temperature, max pressure per sensor
    ▼
TimescaleDB (PostgreSQL + time-series extension)
    │  dashboard-ui queries via REST API
    ▼
dashboard-ui (browser)
    ↑  polls /api/metrics every 2s
```

---

## pipeline-producer

A Python service that simulates 50 IoT sensors publishing telemetry events to Kafka.

### What it publishes (JSON per event)

```json
{
  "sensor_id": "sensor-042",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "temperature": 72.4,
  "pressure": 14.7,
  "humidity": 58.2,
  "location": "warehouse-A",
  "status": "ok"
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `KAFKA_TOPIC` | `sensor-events` | Topic to publish to |
| `EVENTS_PER_SECOND` | `10` | Throughput control |
| `NUM_SENSORS` | `50` | Number of simulated sensors |
| `PORT` | `8090` | HTTP health/metrics port |

### HTTP Endpoints

```
GET /health          → {"status": "ok", "events_published": 1234}
GET /metrics         → Prometheus metrics (events_total, lag)
GET /stats           → Current producer statistics
POST /control/pause  → Pause event generation
POST /control/resume → Resume event generation
```

---

## pipeline-processor

A PySpark Structured Streaming job that reads from Kafka, aggregates data in 5-second tumbling windows, and writes results to TimescaleDB.

### What it computes (per 5-second window, per sensor)

```python
aggregations = {
    "avg_temperature": avg("temperature"),
    "max_pressure":    max("pressure"),
    "avg_humidity":    avg("humidity"),
    "event_count":     count("*"),
    "window_start":    window.start,
    "window_end":      window.end
}
```

### Output Schema (TimescaleDB table: `sensor_aggregates`)

```sql
CREATE TABLE sensor_aggregates (
    time            TIMESTAMPTZ NOT NULL,
    sensor_id       TEXT,
    location        TEXT,
    avg_temperature DOUBLE PRECISION,
    max_pressure    DOUBLE PRECISION,
    avg_humidity    DOUBLE PRECISION,
    event_count     INTEGER
);
SELECT create_hypertable('sensor_aggregates', 'time');
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `KAFKA_TOPIC` | `sensor-events` | Topic to consume |
| `KAFKA_GROUP_ID` | `spark-processor` | Consumer group |
| `TIMESCALE_URL` | `jdbc:postgresql://localhost:5432/pipeline` | DB connection |
| `TIMESCALE_USER` | `pipeline` | DB user |
| `TIMESCALE_PASSWORD` | `pipeline123` | DB password |
| `WINDOW_DURATION` | `5 seconds` | Aggregation window |
| `TRIGGER_INTERVAL` | `5 seconds` | Spark micro-batch interval |

---

## dashboard-ui

A static web dashboard served by nginx that polls the TimescaleDB REST API (via a thin Python FastAPI layer) to show live charts.

### Pages

| Page | URL | What It Shows |
|------|-----|---------------|
| Overview | `/` | Pipeline health, total events, active sensors |
| Live Feed | `/live` | Real-time events table (last 100 events) |
| Metrics | `/metrics` | Temperature/pressure charts per sensor |
| Lag Monitor | `/lag` | Kafka consumer lag per partition |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:8091` | Backend API URL |
| `REFRESH_INTERVAL_MS` | `2000` | Dashboard refresh rate |

---

## Dockerfiles

Each component has a Dockerfile. Your first DevOps task is reviewing them:

### pipeline-producer Dockerfile pattern
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8090
CMD ["python", "main.py"]
```

### pipeline-processor Dockerfile pattern
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y default-jdk-headless curl procps
ENV JAVA_HOME=/usr/lib/jvm/default-java PYSPARK_PYTHON=python3
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
# pyspark installs spark-submit at /usr/local/bin/spark-submit
COPY . /app/
WORKDIR /app
CMD ["spark-submit", "--master", "local[*]", "main.py"]
```

**Questions to think about:**
- Why do we install Java (`default-jdk-headless`) in a Python image?
- How does Spark get the Kafka connector JAR at runtime?
- Why does the processor not expose an HTTP port?
- What's the difference between `local[*]` mode (local dev) vs cluster mode (K8s)?
- How would you pass Kafka JAR dependencies to the Spark operator in K8s?
