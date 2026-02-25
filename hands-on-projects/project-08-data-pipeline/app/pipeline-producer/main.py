"""
IoT Sensor Event Producer
Simulates 50 sensors publishing telemetry events to a Kafka topic.
Also exposes HTTP endpoints for health checks, metrics, and control.
"""

import json
import os
import random
import time
import threading
from datetime import datetime, timezone
from fastapi import FastAPI
from kafka import KafkaProducer
import uvicorn

# ── Config ──────────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor-events")
EVENTS_PER_SECOND = int(os.getenv("EVENTS_PER_SECOND", "10"))
NUM_SENSORS = int(os.getenv("NUM_SENSORS", "50"))
PORT = int(os.getenv("PORT", "8090"))

LOCATIONS = ["warehouse-A", "warehouse-B", "factory-floor", "cold-storage", "loading-dock"]

# ── State ────────────────────────────────────────────────────────────────────
stats = {
    "events_published": 0,
    "errors": 0,
    "paused": False,
    "started_at": datetime.now(timezone.utc).isoformat(),
}

# ── Kafka producer ────────────────────────────────────────────────────────────
def create_producer():
    for attempt in range(30):
        try:
            p = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            print(f"[producer] Connected to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")
            return p
        except Exception as e:
            print(f"[producer] Kafka not ready (attempt {attempt+1}/30): {e}")
            time.sleep(5)
    raise RuntimeError("Could not connect to Kafka after 30 attempts")


def generate_event(sensor_id: str) -> dict:
    location = LOCATIONS[hash(sensor_id) % len(LOCATIONS)]
    base_temp = 20 + (hash(sensor_id) % 60)
    return {
        "sensor_id": sensor_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": round(base_temp + random.uniform(-5, 5), 2),
        "pressure": round(14.5 + random.uniform(-0.5, 0.5), 3),
        "humidity": round(50 + random.uniform(-20, 20), 1),
        "location": location,
        "status": random.choices(["ok", "warning", "error"], weights=[90, 8, 2])[0],
    }


def publish_loop(producer: KafkaProducer):
    sensors = [f"sensor-{i:03d}" for i in range(NUM_SENSORS)]
    delay = 1.0 / EVENTS_PER_SECOND

    while True:
        if stats["paused"]:
            time.sleep(0.5)
            continue

        sensor = random.choice(sensors)
        event = generate_event(sensor)
        try:
            producer.send(KAFKA_TOPIC, value=event, key=sensor.encode())
            stats["events_published"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"[producer] Send error: {e}")

        time.sleep(delay)


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Pipeline Producer", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "events_published": stats["events_published"]}


@app.get("/stats")
def get_stats():
    return {**stats, "kafka_topic": KAFKA_TOPIC, "num_sensors": NUM_SENSORS}


@app.get("/metrics")
def metrics():
    return (
        f"# HELP events_total Total events published\n"
        f"# TYPE events_total counter\n"
        f"events_total {stats['events_published']}\n"
        f"# HELP producer_errors_total Total send errors\n"
        f"# TYPE producer_errors_total counter\n"
        f"producer_errors_total {stats['errors']}\n"
    )


@app.post("/control/pause")
def pause():
    stats["paused"] = True
    return {"status": "paused"}


@app.post("/control/resume")
def resume():
    stats["paused"] = False
    return {"status": "running"}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    producer = create_producer()
    t = threading.Thread(target=publish_loop, args=(producer,), daemon=True)
    t.start()
    print(f"[producer] Publishing {EVENTS_PER_SECOND} events/sec from {NUM_SENSORS} sensors")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
