"""
Pipeline Processor — PySpark Structured Streaming Job
Reads sensor events from Kafka, aggregates in 5-second tumbling windows,
writes results to TimescaleDB (PostgreSQL).
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, avg, max as spark_max, count, to_timestamp
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, TimestampType
)

# ── Config ────────────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC             = os.getenv("KAFKA_TOPIC", "sensor-events")
KAFKA_GROUP_ID          = os.getenv("KAFKA_GROUP_ID", "spark-processor")
TIMESCALE_URL           = os.getenv("TIMESCALE_URL", "jdbc:postgresql://localhost:5432/pipeline")
TIMESCALE_USER          = os.getenv("TIMESCALE_USER", "pipeline")
TIMESCALE_PASSWORD      = os.getenv("TIMESCALE_PASSWORD", "pipeline123")
WINDOW_DURATION         = os.getenv("WINDOW_DURATION", "5 seconds")
TRIGGER_INTERVAL        = os.getenv("TRIGGER_INTERVAL", "5 seconds")

# ── Schema for incoming Kafka JSON messages ────────────────────────────────────
EVENT_SCHEMA = StructType([
    StructField("sensor_id",   StringType(),  nullable=False),
    StructField("timestamp",   StringType(),  nullable=False),
    StructField("temperature", DoubleType(),  nullable=True),
    StructField("pressure",    DoubleType(),  nullable=True),
    StructField("humidity",    DoubleType(),  nullable=True),
    StructField("location",    StringType(),  nullable=True),
    StructField("status",      StringType(),  nullable=True),
])


def write_to_timescale(batch_df, batch_id: int):
    """Write each micro-batch to TimescaleDB using JDBC."""
    if batch_df.count() == 0:
        return

    jdbc_props = {
        "user":     TIMESCALE_USER,
        "password": TIMESCALE_PASSWORD,
        "driver":   "org.postgresql.Driver",
    }

    # Flatten windowed results to match DB schema
    flat = batch_df.select(
        col("window.start").alias("time"),
        col("sensor_id"),
        col("location"),
        col("avg_temperature"),
        col("max_pressure"),
        col("avg_humidity"),
        col("event_count"),
    )

    flat.write.jdbc(
        url=TIMESCALE_URL,
        table="sensor_aggregates",
        mode="append",
        properties=jdbc_props,
    )
    print(f"[processor] Batch {batch_id}: wrote {flat.count()} aggregated rows")


def main():
    spark = (
        SparkSession.builder
        .appName("SensorPipelineProcessor")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.streaming.stopGracefullyOnShutdown", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # ── Read from Kafka ────────────────────────────────────────────────────────
    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("kafka.group.id", KAFKA_GROUP_ID)
        .option("startingOffsets", "latest")
        .load()
    )

    # ── Parse JSON payload ─────────────────────────────────────────────────────
    parsed = (
        raw
        .select(from_json(col("value").cast("string"), EVENT_SCHEMA).alias("data"))
        .select("data.*")
        .withColumn("event_time", to_timestamp(col("timestamp")))
    )

    # ── Aggregate in tumbling windows ──────────────────────────────────────────
    aggregated = (
        parsed
        .withWatermark("event_time", "10 seconds")
        .groupBy(
            window(col("event_time"), WINDOW_DURATION),
            col("sensor_id"),
            col("location"),
        )
        .agg(
            avg("temperature").alias("avg_temperature"),
            spark_max("pressure").alias("max_pressure"),
            avg("humidity").alias("avg_humidity"),
            count("*").alias("event_count"),
        )
    )

    # ── Write each micro-batch to TimescaleDB ──────────────────────────────────
    query = (
        aggregated
        .writeStream
        .outputMode("append")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .foreachBatch(write_to_timescale)
        .option("checkpointLocation", "/tmp/checkpoint/sensor-processor")
        .start()
    )

    print(f"[processor] Streaming from topic '{KAFKA_TOPIC}' → TimescaleDB")
    query.awaitTermination()


if __name__ == "__main__":
    main()
