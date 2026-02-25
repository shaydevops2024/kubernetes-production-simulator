-- TimescaleDB initialization
-- Runs automatically on first container start

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Raw events table (optional — useful for debugging)
CREATE TABLE IF NOT EXISTS sensor_events (
    time        TIMESTAMPTZ NOT NULL,
    sensor_id   TEXT NOT NULL,
    temperature DOUBLE PRECISION,
    pressure    DOUBLE PRECISION,
    humidity    DOUBLE PRECISION,
    location    TEXT,
    status      TEXT
);
SELECT create_hypertable('sensor_events', 'time', if_not_exists => TRUE);

-- Aggregated results from Spark
CREATE TABLE IF NOT EXISTS sensor_aggregates (
    time            TIMESTAMPTZ NOT NULL,
    sensor_id       TEXT NOT NULL,
    location        TEXT,
    avg_temperature DOUBLE PRECISION,
    max_pressure    DOUBLE PRECISION,
    avg_humidity    DOUBLE PRECISION,
    event_count     INTEGER
);
SELECT create_hypertable('sensor_aggregates', 'time', if_not_exists => TRUE);

-- Index for fast sensor lookups
CREATE INDEX IF NOT EXISTS idx_agg_sensor ON sensor_aggregates (sensor_id, time DESC);

-- Continuous aggregate for 1-minute summaries (TimescaleDB feature)
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    sensor_id,
    AVG(avg_temperature) AS avg_temp,
    MAX(max_pressure)    AS max_pressure,
    SUM(event_count)     AS total_events
FROM sensor_aggregates
GROUP BY bucket, sensor_id
WITH NO DATA;
