from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import uuid
import random
from datetime import datetime, date, timedelta
from pydantic import BaseModel
from typing import List

app = FastAPI(
    title="Billing Service",
    description="Usage metering and cost tracking per tenant.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./billing.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Cost per API call by plan (USD)
PLAN_RATES = {
    "starter":    0.001,
    "pro":        0.0005,
    "enterprise": 0.0001,
}

TENANT_PLANS = {
    "alice-corp":     "enterprise",
    "bob-industries": "pro",
    "charlie-ltd":    "starter",
}


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    service = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


Base.metadata.create_all(bind=engine)

ENDPOINTS = [
    "GET /tasks",
    "POST /tasks",
    "PUT /tasks/{id}",
    "DELETE /tasks/{id}",
    "GET /stats",
]


def seed_usage(db):
    if db.query(UsageEvent).count() > 0:
        return

    tenants_weights = [
        ("alice-corp", 55),      # enterprise — heavy user
        ("bob-industries", 35),  # pro — moderate user
        ("charlie-ltd", 10),     # starter / suspended — light user
    ]

    now = datetime.utcnow()
    events = []

    # Generate 300 events spread over today and the past 6 days
    for _ in range(300):
        tenant_id = random.choices(
            [t for t, _ in tenants_weights],
            weights=[w for _, w in tenants_weights],
        )[0]
        # Most events today, fewer in past days
        days_ago = random.choices(range(7), weights=[40, 15, 12, 10, 9, 8, 6])[0]
        hours_ago = random.randint(0, 23)
        ts = now - timedelta(days=days_ago, hours=hours_ago)

        events.append(
            UsageEvent(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                service="app-service",
                endpoint=random.choice(ENDPOINTS),
                timestamp=ts,
            )
        )

    db.bulk_save_objects(events)
    db.commit()


with SessionLocal() as _db:
    seed_usage(_db)


def today_range():
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


# ── Schemas ───────────────────────────────────────────────────────────────────


class RecordRequest(BaseModel):
    tenant_id: str
    service: str
    endpoint: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "healthy", "service": "billing-service"}


@app.post("/record", status_code=201)
def record_usage(body: RecordRequest):
    db = SessionLocal()
    try:
        event = UsageEvent(
            id=str(uuid.uuid4()),
            tenant_id=body.tenant_id,
            service=body.service,
            endpoint=body.endpoint,
            timestamp=datetime.utcnow(),
        )
        db.add(event)
        db.commit()
        return {"recorded": True}
    finally:
        db.close()


@app.get("/usage")
def get_all_usage():
    """Return aggregated usage for all tenants (total + today)."""
    db = SessionLocal()
    try:
        t_start, t_end = today_range()

        total_rows = (
            db.query(UsageEvent.tenant_id, func.count(UsageEvent.id).label("total"))
            .group_by(UsageEvent.tenant_id)
            .all()
        )

        today_rows = (
            db.query(UsageEvent.tenant_id, func.count(UsageEvent.id).label("today"))
            .filter(UsageEvent.timestamp >= t_start, UsageEvent.timestamp < t_end)
            .group_by(UsageEvent.tenant_id)
            .all()
        )

        today_map = {r.tenant_id: r.today for r in today_rows}

        result = []
        for row in total_rows:
            plan = TENANT_PLANS.get(row.tenant_id, "starter")
            rate = PLAN_RATES[plan]
            today_calls = today_map.get(row.tenant_id, 0)
            result.append(
                {
                    "tenant_id": row.tenant_id,
                    "total_calls": row.total,
                    "today_calls": today_calls,
                    "estimated_cost_today": round(today_calls * rate, 4),
                }
            )

        return result
    finally:
        db.close()


@app.get("/usage/{tenant_id}")
def get_tenant_usage(tenant_id: str):
    """Detailed usage breakdown for one tenant."""
    db = SessionLocal()
    try:
        total = (
            db.query(func.count(UsageEvent.id))
            .filter(UsageEvent.tenant_id == tenant_id)
            .scalar()
        )
        if total == 0:
            raise HTTPException(status_code=404, detail="No usage data for this tenant")

        t_start, t_end = today_range()
        today_count = (
            db.query(func.count(UsageEvent.id))
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.timestamp >= t_start,
                UsageEvent.timestamp < t_end,
            )
            .scalar()
        )

        endpoint_rows = (
            db.query(UsageEvent.endpoint, func.count(UsageEvent.id).label("count"))
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.timestamp >= t_start,
                UsageEvent.timestamp < t_end,
            )
            .group_by(UsageEvent.endpoint)
            .all()
        )

        plan = TENANT_PLANS.get(tenant_id, "starter")
        rate = PLAN_RATES[plan]

        return {
            "tenant_id": tenant_id,
            "plan": plan,
            "total_calls": total,
            "today_calls": today_count,
            "estimated_cost_today": round(today_count * rate, 4),
            "endpoints_today": [
                {"endpoint": r.endpoint, "count": r.count}
                for r in endpoint_rows
            ],
        }
    finally:
        db.close()
