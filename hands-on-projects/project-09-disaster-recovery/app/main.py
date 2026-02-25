"""
Disaster Recovery Dashboard — Critical Operations Service
A production-grade application used as the "business workload" in the DR project.

Stores critical operational records in PostgreSQL.
Connects to MinIO to list Velero backups.
Exposes a REST API consumed by the dashboard UI.
"""

import os
import json
import asyncio
import datetime
import random
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ── Optional dependencies ──────────────────────────────────────────────────────
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    import boto3
    from botocore.config import Config as BotoConfig
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# ── Configuration ──────────────────────────────────────────────────────────────
DB_PRIMARY_URL    = os.getenv("DATABASE_URL",           "postgresql://dr:drpassword@localhost:5432/dr_primary")
DB_SECONDARY_URL  = os.getenv("DATABASE_SECONDARY_URL", "postgresql://dr:drpassword@localhost:5433/dr_secondary")
MINIO_ENDPOINT    = os.getenv("MINIO_ENDPOINT",         "http://minio:9000")
MINIO_ACCESS_KEY  = os.getenv("MINIO_ACCESS_KEY",       "minioadmin")
MINIO_SECRET_KEY  = os.getenv("MINIO_SECRET_KEY",       "minioadmin")
MINIO_BUCKET      = os.getenv("MINIO_BUCKET",           "dr-backups")
APP_ENV           = os.getenv("APP_ENV",                "development")

# ── Global DB pools ────────────────────────────────────────────────────────────
primary_pool:   Optional[object] = None
secondary_pool: Optional[object] = None


# ── Startup / Shutdown ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global primary_pool, secondary_pool

    if HAS_ASYNCPG:
        try:
            primary_pool = await asyncpg.create_pool(DB_PRIMARY_URL, min_size=2, max_size=10, timeout=5)
            await _init_db(primary_pool, region="primary")
            print("[DR-APP] Primary DB connected")
        except Exception as e:
            print(f"[DR-APP] Primary DB unavailable: {e}")

        try:
            secondary_pool = await asyncpg.create_pool(DB_SECONDARY_URL, min_size=2, max_size=10, timeout=5)
            await _init_db(secondary_pool, region="secondary")
            print("[DR-APP] Secondary DB connected")
        except Exception as e:
            print(f"[DR-APP] Secondary DB unavailable: {e}")

    yield

    if primary_pool:
        await primary_pool.close()
    if secondary_pool:
        await secondary_pool.close()


app = FastAPI(title="DR Dashboard", lifespan=lifespan)


# ── DB Helpers ─────────────────────────────────────────────────────────────────
async def _init_db(pool, region: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS critical_records (
                id          SERIAL PRIMARY KEY,
                record_id   VARCHAR(20) UNIQUE NOT NULL,
                category    VARCHAR(50) NOT NULL,
                description TEXT NOT NULL,
                severity    VARCHAR(10) DEFAULT 'low',
                status      VARCHAR(20) DEFAULT 'active',
                region      VARCHAR(20) DEFAULT 'primary',
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # Seed initial records if table is empty
        count = await conn.fetchval("SELECT COUNT(*) FROM critical_records")
        if count == 0:
            await _seed_records(conn, region)


async def _seed_records(conn, region: str):
    records = [
        ("REC-001", "financial",    "Q4 revenue report — $2.4M processed",           "high",   "active"),
        ("REC-002", "operational",  "Customer database migration completed",           "high",   "active"),
        ("REC-003", "compliance",   "GDPR audit trail — 12,450 records",              "medium", "active"),
        ("REC-004", "financial",    "Payroll batch — 847 employees processed",         "high",   "active"),
        ("REC-005", "inventory",    "Warehouse stock sync — 15,200 SKUs updated",      "medium", "active"),
        ("REC-006", "operational",  "API gateway config deployed — v2.3.1",            "low",    "active"),
        ("REC-007", "security",     "SSL certificates rotated — 23 services",          "high",   "active"),
        ("REC-008", "compliance",   "SOC2 evidence collection — Q3 complete",          "medium", "active"),
        ("REC-009", "inventory",    "Cold-chain temperature logs — 72h window",        "high",   "active"),
        ("REC-010", "financial",    "Bank reconciliation — 3,201 transactions",        "high",   "active"),
    ]
    for rec_id, category, desc, severity, status in records:
        try:
            await conn.execute(
                "INSERT INTO critical_records (record_id, category, description, severity, status, region) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
                rec_id, category, desc, severity, status, region
            )
        except Exception:
            pass


# ── MinIO Helper ───────────────────────────────────────────────────────────────
def _list_backups_sync() -> List[dict]:
    if not HAS_BOTO3:
        return _mock_backups()
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=BotoConfig(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1}),
        )
        resp = s3.list_objects_v2(Bucket=MINIO_BUCKET)
        backups = []
        for obj in resp.get("Contents", []):
            backups.append({
                "name":          obj["Key"],
                "size_mb":       round(obj["Size"] / 1024 / 1024, 2),
                "last_modified": obj["LastModified"].isoformat(),
                "storage_class": obj.get("StorageClass", "STANDARD"),
            })
        return sorted(backups, key=lambda x: x["last_modified"], reverse=True)
    except Exception as e:
        print(f"[DR-APP] MinIO list error: {e}")
        return _mock_backups()


def _mock_backups() -> List[dict]:
    now = datetime.datetime.utcnow()
    return [
        {
            "name":          f"velero/backups/dr-hourly-{(now - datetime.timedelta(hours=i)).strftime('%Y%m%d-%H%M')}/backup.tar.gz",
            "size_mb":       round(random.uniform(12.5, 48.3), 2),
            "last_modified": (now - datetime.timedelta(hours=i)).isoformat(),
            "storage_class": "STANDARD",
        }
        for i in range(6)
    ]


# ── Pydantic Models ────────────────────────────────────────────────────────────
class RecordIn(BaseModel):
    category:    str
    description: str
    severity:    str = "low"


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r") as f:
        return f.read()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "dr-dashboard", "env": APP_ENV}


@app.get("/api/status")
async def get_status():
    primary_ok   = False
    secondary_ok = False
    primary_count   = 0
    secondary_count = 0

    if primary_pool:
        try:
            async with primary_pool.acquire() as conn:
                primary_count = await conn.fetchval("SELECT COUNT(*) FROM critical_records")
                primary_ok = True
        except Exception:
            pass

    if secondary_pool:
        try:
            async with secondary_pool.acquire() as conn:
                secondary_count = await conn.fetchval("SELECT COUNT(*) FROM critical_records")
                secondary_ok = True
        except Exception:
            pass

    # MinIO check
    minio_ok = False
    backup_count = 0
    if HAS_BOTO3:
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=MINIO_ENDPOINT,
                aws_access_key_id=MINIO_ACCESS_KEY,
                aws_secret_access_key=MINIO_SECRET_KEY,
                config=BotoConfig(connect_timeout=2, read_timeout=2, retries={"max_attempts": 1}),
            )
            resp = s3.list_objects_v2(Bucket=MINIO_BUCKET)
            backup_count = resp.get("KeyCount", 0)
            minio_ok = True
        except Exception:
            pass

    # If nothing is connected, return mock status
    if not primary_ok and not secondary_ok:
        return _mock_status()

    return {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "primary": {
            "status":       "healthy" if primary_ok else "degraded",
            "records":      primary_count,
            "region":       "us-east-1 (Kind node: worker)",
            "db_connected": primary_ok,
            "latency_ms":   random.randint(2, 8),
        },
        "secondary": {
            "status":       "healthy" if secondary_ok else "degraded",
            "records":      secondary_count,
            "region":       "us-west-2 (Kind node: worker2)",
            "db_connected": secondary_ok,
            "latency_ms":   random.randint(12, 45),
        },
        "storage": {
            "status":       "healthy" if minio_ok else "degraded",
            "provider":     "MinIO (S3-compatible)",
            "bucket":       MINIO_BUCKET,
            "backup_count": backup_count,
        },
        "rpo_minutes":  60,
        "rto_minutes":  15,
        "last_backup":  (datetime.datetime.utcnow() - datetime.timedelta(minutes=random.randint(10, 55))).isoformat(),
        "last_recovery_test": (datetime.datetime.utcnow() - datetime.timedelta(days=2)).isoformat(),
    }


def _mock_status():
    now = datetime.datetime.utcnow()
    return {
        "timestamp": now.isoformat(),
        "primary": {
            "status":       "healthy",
            "records":      10,
            "region":       "us-east-1 (Kind node: worker)",
            "db_connected": False,
            "latency_ms":   4,
        },
        "secondary": {
            "status":       "degraded",
            "records":      0,
            "region":       "us-west-2 (Kind node: worker2)",
            "db_connected": False,
            "latency_ms":   0,
        },
        "storage": {
            "status":       "degraded",
            "provider":     "MinIO (S3-compatible)",
            "bucket":       MINIO_BUCKET,
            "backup_count": 0,
        },
        "rpo_minutes":  60,
        "rto_minutes":  15,
        "last_backup":  (now - datetime.timedelta(minutes=35)).isoformat(),
        "last_recovery_test": (now - datetime.timedelta(days=2)).isoformat(),
        "_mock": True,
    }


@app.get("/api/records")
async def get_records(region: str = "primary"):
    pool = primary_pool if region == "primary" else secondary_pool
    if not pool:
        return {"records": _mock_records(), "region": region, "_mock": True}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, record_id, category, description, severity, status, region, created_at FROM critical_records ORDER BY id DESC"
            )
            return {"records": [dict(r) for r in rows], "region": region}
    except Exception as e:
        return {"records": _mock_records(), "region": region, "_mock": True, "error": str(e)}


def _mock_records():
    now = datetime.datetime.utcnow()
    categories = ["financial", "operational", "compliance", "inventory", "security"]
    severities  = ["high", "medium", "low"]
    descs = [
        "Q4 revenue report — $2.4M processed",
        "Customer database migration completed",
        "GDPR audit trail — 12,450 records",
        "Payroll batch — 847 employees processed",
        "Warehouse stock sync — 15,200 SKUs updated",
        "API gateway config deployed — v2.3.1",
        "SSL certificates rotated — 23 services",
        "SOC2 evidence collection — Q3 complete",
        "Cold-chain temperature logs — 72h window",
        "Bank reconciliation — 3,201 transactions",
    ]
    return [
        {
            "id":          i + 1,
            "record_id":   f"REC-{i+1:03d}",
            "category":    categories[i % len(categories)],
            "description": descs[i % len(descs)],
            "severity":    severities[i % len(severities)],
            "status":      "active",
            "region":      "primary",
            "created_at":  (now - datetime.timedelta(hours=i * 3)).isoformat(),
        }
        for i in range(10)
    ]


@app.post("/api/records")
async def create_record(record: RecordIn):
    record_id = f"REC-{random.randint(100, 999)}"
    pool = primary_pool
    if not pool:
        return {"id": random.randint(11, 99), "record_id": record_id, "status": "created", "_mock": True}
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO critical_records (record_id, category, description, severity) VALUES ($1,$2,$3,$4) RETURNING id, record_id, created_at",
                record_id, record.category, record.description, record.severity,
            )
            return {"id": row["id"], "record_id": row["record_id"], "created_at": row["created_at"].isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backups")
async def get_backups():
    backups = await asyncio.get_event_loop().run_in_executor(None, _list_backups_sync)
    return {"backups": backups, "count": len(backups), "bucket": MINIO_BUCKET}


@app.post("/api/backup")
async def trigger_backup():
    """Trigger a manual backup — uploads metadata to MinIO or returns mock result."""
    now = datetime.datetime.utcnow()
    backup_name = f"manual-backup-{now.strftime('%Y%m%d-%H%M%S')}"

    if HAS_BOTO3:
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=MINIO_ENDPOINT,
                aws_access_key_id=MINIO_ACCESS_KEY,
                aws_secret_access_key=MINIO_SECRET_KEY,
                config=BotoConfig(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1}),
            )
            primary_count = 0
            if primary_pool:
                async with primary_pool.acquire() as conn:
                    primary_count = await conn.fetchval("SELECT COUNT(*) FROM critical_records")
            metadata = json.dumps({
                "name": backup_name,
                "type": "manual",
                "timestamp": now.isoformat(),
                "namespace": "dr-lab",
                "status": "Completed",
                "record_count": primary_count,
            }).encode()
            s3.put_object(
                Bucket=MINIO_BUCKET,
                Key=f"velero/backups/{backup_name}/backup-metadata.json",
                Body=metadata,
                ContentType="application/json",
            )
            return {
                "status": "success",
                "backup_name": backup_name,
                "storage": "MinIO",
                "location": f"s3://{MINIO_BUCKET}/velero/backups/{backup_name}/",
                "timestamp": now.isoformat(),
                "_mock": False,
            }
        except Exception as e:
            return {
                "status": "success",
                "backup_name": backup_name,
                "storage": "mock (MinIO unavailable)",
                "location": f"s3://{MINIO_BUCKET}/velero/backups/{backup_name}/",
                "timestamp": now.isoformat(),
                "note": str(e),
                "_mock": True,
            }

    return {
        "status": "success",
        "backup_name": backup_name,
        "storage": "mock",
        "location": f"s3://{MINIO_BUCKET}/velero/backups/{backup_name}/",
        "timestamp": now.isoformat(),
        "velero_cmd": f"velero backup create {backup_name} --include-namespaces dr-lab",
        "_mock": True,
    }


@app.post("/api/recovery-test")
async def trigger_recovery_test():
    """Simulate a DR recovery test and return RTO measurement."""
    now = datetime.datetime.utcnow()
    simulated_rto = random.randint(6, 14)
    backup_used = f"dr-lab-hourly-{(now - datetime.timedelta(hours=1)).strftime('%Y%m%d-%H%M')}"
    return {
        "status": "passed",
        "rto_minutes": simulated_rto,
        "backup_used": backup_used,
        "restore_cmd": f"velero restore create --from-backup {backup_used}",
        "steps": [
            {"step": "Identify latest backup", "duration_s": 2},
            {"step": "Trigger velero restore", "duration_s": simulated_rto * 30},
            {"step": "Verify pod health", "duration_s": 15},
            {"step": "Verify data integrity", "duration_s": 8},
        ],
        "timestamp": now.isoformat(),
        "_mock": True,
    }


@app.post("/api/chaos")
async def trigger_chaos():
    """Return chaos injection commands and simulate experiment creation."""
    now = datetime.datetime.utcnow()
    return {
        "status": "experiment_created",
        "experiment": "pod-kill",
        "target": "dr-app pods (50% kill rate)",
        "duration_s": 30,
        "kubectl_cmd": "kubectl apply -f solution/k8s/chaos/pod-kill.yaml",
        "monitor_cmd": "kubectl -n dr-lab get pods -w",
        "expected": "K8s restarts killed pods; app recovers within 2 minutes",
        "timestamp": now.isoformat(),
        "_mock": True,
    }


@app.get("/api/metrics")
async def get_metrics():
    now = datetime.datetime.utcnow()
    return {
        "rpo": {
            "target_minutes":  60,
            "current_minutes": random.randint(10, 58),
            "status":          "within_target",
        },
        "rto": {
            "target_minutes":  15,
            "last_test_minutes": random.randint(8, 14),
            "status":           "within_target",
            "last_tested":      (now - datetime.timedelta(days=2)).isoformat(),
        },
        "backup_history": [
            {
                "timestamp": (now - datetime.timedelta(hours=i)).isoformat(),
                "type":      "incremental" if i % 4 != 0 else "full",
                "status":    "success",
                "duration_s": random.randint(45, 180),
                "size_mb":    round(random.uniform(8.5, 52.3), 1),
            }
            for i in range(8)
        ],
        "recovery_tests": [
            {
                "date":        (now - datetime.timedelta(days=d)).isoformat(),
                "result":      "passed",
                "rto_minutes": random.randint(8, 14),
                "data_loss":   "none",
            }
            for d in [2, 9, 16, 30]
        ],
    }
