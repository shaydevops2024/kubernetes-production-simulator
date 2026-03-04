# Project 08 — Real-Time Data Pipeline: Explained

---

## 1. The App

You are deploying a **production-grade streaming data pipeline** using Apache Kafka and Apache Spark on Kubernetes. The pipeline ingests simulated IoT sensor events, processes them in real time, stores aggregated results in a time-series database, and displays live metrics on a web dashboard.

```
[Pipeline Producer]
  │  Simulates IoT sensor events (temperature, humidity, pressure)
  │  Publishes 100+ events/second to Kafka topic: sensor-data
  ▼
[Kafka (Strimzi Operator)]
  │  Message broker — durably stores events, decouples producer from processor
  │  Topic: sensor-data (3 partitions, replication factor 1)
  ▼
[Pipeline Processor — Spark Structured Streaming]
  │  Consumes Kafka topic in micro-batches
  │  Aggregates: avg temp, max humidity, event count per sensor per minute
  │  Writes results to TimescaleDB
  ▼
[TimescaleDB (PostgreSQL + time-series extension)]
  │  Stores aggregated metrics with automatic time partitioning
  ▼
[Dashboard UI]
  │  Live charts showing pipeline metrics, sensor readings, Kafka lag
  └─▶ Browser
```

| Component | What it does |
|-----------|-------------|
| **pipeline-producer** | Python script that generates and publishes simulated IoT sensor events to Kafka |
| **pipeline-processor** | PySpark Structured Streaming job — reads from Kafka, windowed aggregation, writes to DB |
| **dashboard-ui** | HTML/JS live dashboard — shows real-time sensor data, pipeline throughput, Kafka consumer lag |
| **Kafka (Strimzi)** | Managed Kafka cluster on K8s, deployed via Strimzi Operator |
| **TimescaleDB** | PostgreSQL with time-series superpowers — fast range queries, automatic chunking |

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-08-data-pipeline/local/

docker compose up --build
```

Startup order matters — Kafka takes ~30 seconds to be ready. Wait for:
```
pipeline-producer | Successfully connected to Kafka
pipeline-processor | Spark job started, consuming from sensor-data
```

| UI | URL |
|----|-----|
| Dashboard | http://localhost:8080 |
| Kafka UI (if included) | http://localhost:8090 |

**Watch the pipeline in action:**
1. Open the dashboard at http://localhost:8080
2. You'll see live sensor readings updating every few seconds
3. The "Pipeline Stats" section shows events/second, processing lag
4. The "Kafka Consumer Lag" chart shows how far behind the processor is

**Control the producer rate:**
```bash
# Increase event production rate
docker compose exec pipeline-producer \
  python -c "import os; os.environ['EVENTS_PER_SECOND']='500'"

# Or via environment variable (restart required)
EVENTS_PER_SECOND=500 docker compose up -d pipeline-producer
```

### Phase 2 — Deploy to Kubernetes

```bash
cd hands-on-projects/project-08-data-pipeline/main/

# Install Strimzi Operator (manages Kafka clusters)
kubectl apply -f solution/strimzi/  # or via Helm

# Create Kafka cluster (Strimzi CRD)
kubectl apply -f solution/kafka/kafka-cluster.yaml

# Wait for Kafka to be ready (~3-5 minutes)
kubectl wait kafka/data-pipeline-kafka --for=condition=Ready \
  --timeout=300s -n data-pipeline

# Create Kafka topics
kubectl apply -f solution/kafka/topics.yaml

# Deploy Spark Operator
helm install spark-operator spark-operator/spark-operator \
  -n spark-operator --create-namespace

# Deploy the Spark application (SparkApplication CRD)
kubectl apply -f solution/spark/

# Deploy TimescaleDB
kubectl apply -f solution/timescaledb/

# Deploy Producer and Dashboard
kubectl apply -f solution/app/
```

---

## 3. How to Test It

### Verify Kafka is Receiving Events

```bash
# Consume from Kafka topic and print events (local)
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic sensor-data \
  --max-messages 10 \
  --from-beginning

# K8s: use Strimzi's kafka-console-consumer
kubectl exec -n data-pipeline kafka-0 -- bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic sensor-data \
  --max-messages 5
```

### Verify Spark is Processing

```bash
# Check Spark job is running
docker compose ps pipeline-processor

# Check Spark logs for processing activity
docker compose logs pipeline-processor | grep "Batch"
# Should see: "Batch: 1", "Batch: 2", etc.

# K8s: check SparkApplication status
kubectl get sparkapplication -n data-pipeline
kubectl describe sparkapplication pipeline-processor -n data-pipeline
```

### Verify Data in TimescaleDB

```bash
# Connect to TimescaleDB
docker compose exec timescaledb \
  psql -U pipeline -d sensordb -c \
  "SELECT sensor_id, AVG(temperature), COUNT(*), MAX(ts)
   FROM sensor_readings
   WHERE ts > NOW() - INTERVAL '5 minutes'
   GROUP BY sensor_id
   ORDER BY sensor_id;"
```

### Kafka Consumer Lag Test

```bash
# Check consumer lag (how far behind the processor is)
docker compose exec kafka kafka-consumer-groups.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --group spark-processor-group

# LAG column shows number of unconsumed messages
# Should stay low (< 1000) if processor is keeping up
```

### Throughput Test

```bash
# Increase production rate and watch if processor keeps up
docker compose exec pipeline-producer \
  python -c "print('current rate')"

# Monitor the dashboard — watch Kafka lag chart
# If lag grows and doesn't stabilize, processor needs more resources/parallelism
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Apache Kafka** | Message broker | Receives IoT events from producer, durably stores them, feeds to Spark |
| **Strimzi Operator** | Kafka on K8s | Manages Kafka cluster lifecycle via `Kafka` CRDs — no manual JVM config |
| **Apache Spark** | Stream processing | Structured Streaming reads Kafka topic, applies windowed aggregations |
| **Spark Operator** | Spark on K8s | Manages Spark job lifecycle via `SparkApplication` CRDs |
| **TimescaleDB** | Time-series DB | PostgreSQL + time-series extension; fast queries on time-ranged sensor data |
| **Python (confluent-kafka)** | Producer | Publishes events to Kafka using Confluent's high-performance Kafka client |
| **PySpark** | Processor | Defines Structured Streaming pipeline in Python |
| **Docker Compose** | Local development | Runs all components with correct startup order and networking |

### Key Data Engineering Concepts Practiced

- **Event streaming vs batch processing**: Kafka decouples producers from consumers — processor can lag and catch up
- **Kafka partitions**: Parallelism — more partitions = more Spark tasks can run in parallel
- **Spark Structured Streaming**: Micro-batch processing with exactly-once semantics (with checkpointing)
- **Consumer group lag**: Key metric — tells you if your processor is keeping up with the producer
- **Time-series optimization**: TimescaleDB chunks data by time for fast range queries

---

## 5. Troubleshooting

### Kafka not starting (Docker Compose)

```bash
# Kafka needs ZooKeeper to be healthy first
docker compose logs zookeeper
docker compose logs kafka

# Common fix: increase startup timeout or wait longer
docker compose up -d zookeeper
# Wait 10 seconds
docker compose up -d kafka
docker compose up -d pipeline-producer pipeline-processor
```

### Producer "Connection refused" to Kafka

```bash
# Check Kafka is listening
docker compose exec kafka kafka-topics.sh \
  --bootstrap-server kafka:9092 --list

# Check KAFKA_ADVERTISED_LISTENERS environment variable
docker compose exec kafka env | grep KAFKA_ADVERTISED

# The advertised address must be reachable from the producer container
```

### Spark job not writing to TimescaleDB

```bash
# Check Spark processor logs for JDBC errors
docker compose logs pipeline-processor | grep -i "error\|exception"

# Verify TimescaleDB is accepting connections
docker compose exec timescaledb \
  psql -U pipeline -d sensordb -c "SELECT 1;"

# Check JDBC URL in processor config
docker compose exec pipeline-processor env | grep DB_URL
```

### Consumer lag growing infinitely

```bash
# Processor can't keep up — options:
# 1. Reduce producer rate
# 2. Increase Spark parallelism (more partitions, more executors)
# 3. Optimize Spark aggregation query

# Check current Spark tasks
docker compose logs pipeline-processor | tail -20
# Look for "Finished batch" messages — how fast?
```

### Kubernetes: Strimzi Kafka CRD not found

```bash
# Strimzi operator must be installed before applying Kafka CRD
kubectl get crd | grep kafka

# If not present, install Strimzi first
kubectl apply -f 'https://strimzi.io/install/latest?namespace=data-pipeline' \
  -n data-pipeline

# Wait for operator to be ready
kubectl wait deploy/strimzi-cluster-operator \
  --for=condition=Available -n data-pipeline --timeout=120s
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-08-data-pipeline/local/

# Stop everything
docker compose down

# Full reset (removes Kafka topics, Spark checkpoints, TimescaleDB data)
docker compose down -v
```

### Kubernetes

```bash
# Delete app resources
kubectl delete namespace data-pipeline

# Uninstall Spark Operator
helm uninstall spark-operator -n spark-operator
kubectl delete namespace spark-operator

# Uninstall Strimzi
kubectl delete -f 'https://strimzi.io/install/latest?namespace=data-pipeline' \
  -n data-pipeline

# Remove Strimzi CRDs
kubectl delete crd kafkas.kafka.strimzi.io
kubectl delete crd kafkatopics.kafka.strimzi.io
kubectl delete crd kafkausers.kafka.strimzi.io
```
