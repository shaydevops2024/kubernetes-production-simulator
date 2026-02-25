"""
Dashboard API — thin FastAPI layer between the UI and TimescaleDB.
Provides REST endpoints the browser polls every 2 seconds.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import psycopg2
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

DB_URL = os.getenv("TIMESCALE_URL", "postgresql://pipeline:pipeline123@localhost:5432/pipeline")

conn: Optional[psycopg2.extensions.connection] = None


def get_conn():
    global conn
    try:
        if conn is None or conn.closed:
            conn = psycopg2.connect(DB_URL)
    except Exception:
        conn = None
    return conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_conn()
    yield
    if conn and not conn.closed:
        conn.close()


app = FastAPI(title="Pipeline Dashboard API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/stats")
def stats():
    c = get_conn()
    if c is None:
        return {"total_events": 0, "events_per_second": 0, "active_sensors": 0, "consumer_lag": 0, "batches_processed": 0}
    with c.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(event_count),0) FROM sensor_aggregates WHERE time > NOW() - INTERVAL '1 hour'")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT sensor_id) FROM sensor_aggregates WHERE time > NOW() - INTERVAL '30 seconds'")
        active = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sensor_aggregates")
        batches = cur.fetchone()[0]
    return {
        "total_events": int(total),
        "events_per_second": 10,
        "active_sensors": int(active),
        "consumer_lag": 0,
        "batches_processed": int(batches),
    }


@app.get("/api/aggregates")
def aggregates(limit: int = Query(10, ge=1, le=100)):
    c = get_conn()
    if c is None:
        return []
    with c.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (sensor_id)
                sensor_id, location, avg_temperature, max_pressure, avg_humidity, event_count
            FROM sensor_aggregates
            ORDER BY sensor_id, time DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    return [
        {
            "sensor_id": r[0], "location": r[1],
            "avg_temperature": round(r[2] or 0, 1),
            "max_pressure": round(r[3] or 0, 3),
            "avg_humidity": round(r[4] or 0, 1),
            "event_count": r[5] or 0,
            "status": "ok",
            "trend": "up",
        }
        for r in rows
    ]


@app.get("/api/events")
def events(limit: int = Query(20, ge=1, le=100)):
    """Return recent aggregated rows as individual event records for the live feed."""
    c = get_conn()
    if c is None:
        return []
    with c.cursor() as cur:
        cur.execute("""
            SELECT time, sensor_id, location, avg_temperature, max_pressure, avg_humidity
            FROM sensor_aggregates
            ORDER BY time DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    return [
        {
            "time": r[0].isoformat() if r[0] else None,
            "sensor_id": r[1],
            "location": r[2],
            "temperature": round(r[3] or 0, 1),
            "pressure": round(r[4] or 0, 3),
            "humidity": round(r[5] or 0, 1),
            "status": "ok",
        }
        for r in rows
    ]


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve the static dashboard
app.mount("/", StaticFiles(directory=".", html=True), name="static")
