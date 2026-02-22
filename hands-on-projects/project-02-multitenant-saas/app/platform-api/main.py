from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import uuid
import re
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(
    title="Platform API",
    description="Multi-tenant SaaS platform management — create, suspend, and delete tenants",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./platform.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

PLAN_LIMITS = {
    "starter":    {"cpu": "500m",  "memory": "512Mi",  "pods": 5},
    "pro":        {"cpu": "2",     "memory": "2Gi",    "pods": 20},
    "enterprise": {"cpu": "8",     "memory": "8Gi",    "pods": 100},
}

SEED_TENANTS = [
    {
        "name": "Alice Corp",
        "slug": "alice-corp",
        "plan": "enterprise",
        "contact_email": "admin@alicecorp.com",
        "status": "active",
    },
    {
        "name": "Bob Industries",
        "slug": "bob-industries",
        "plan": "pro",
        "contact_email": "ops@bobindustries.com",
        "status": "active",
    },
    {
        "name": "Charlie Ltd",
        "slug": "charlie-ltd",
        "plan": "starter",
        "contact_email": "hello@charlieltd.com",
        "status": "suspended",
    },
]


class TenantModel(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    plan = Column(String, default="starter")
    status = Column(String, default="active")
    contact_email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def seed_data(db: Session):
    if db.query(TenantModel).count() == 0:
        for t in SEED_TENANTS:
            tenant = TenantModel(
                id=str(uuid.uuid4()),
                name=t["name"],
                slug=t["slug"],
                plan=t["plan"],
                contact_email=t["contact_email"],
                status=t["status"],
                created_at=datetime.utcnow(),
            )
            db.add(tenant)
        db.commit()


with SessionLocal() as _db:
    seed_data(_db)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class TenantCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    plan: str = "starter"
    contact_email: Optional[str] = None


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    contact_email: Optional[str]
    created_at: datetime
    resource_limits: dict

    class Config:
        from_attributes = True


def to_response(t: TenantModel) -> TenantResponse:
    return TenantResponse(
        id=t.id,
        name=t.name,
        slug=t.slug,
        plan=t.plan,
        status=t.status,
        contact_email=t.contact_email,
        created_at=t.created_at,
        resource_limits=PLAN_LIMITS.get(t.plan, PLAN_LIMITS["starter"]),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "healthy", "service": "platform-api"}


@app.get("/tenants", response_model=List[TenantResponse])
def list_tenants(db: Session = Depends(get_db)):
    tenants = db.query(TenantModel).all()
    return [to_response(t) for t in tenants]


@app.post("/tenants", response_model=TenantResponse, status_code=201)
def create_tenant(body: TenantCreate, db: Session = Depends(get_db)):
    slug = body.slug or make_slug(body.name)
    if not slug:
        raise HTTPException(status_code=400, detail="Could not generate a valid slug from the tenant name")
    if body.plan not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail=f"plan must be one of: {list(PLAN_LIMITS)}")
    if db.query(TenantModel).filter(TenantModel.slug == slug).first():
        raise HTTPException(status_code=409, detail=f"Tenant with slug '{slug}' already exists")

    tenant = TenantModel(
        id=str(uuid.uuid4()),
        name=body.name,
        slug=slug,
        plan=body.plan,
        contact_email=body.contact_email,
        created_at=datetime.utcnow(),
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return to_response(tenant)


@app.get("/tenants/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: str, db: Session = Depends(get_db)):
    tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return to_response(tenant)


@app.patch("/tenants/{tenant_id}/suspend", response_model=TenantResponse)
def suspend_tenant(tenant_id: str, db: Session = Depends(get_db)):
    tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.status = "suspended"
    db.commit()
    db.refresh(tenant)
    return to_response(tenant)


@app.patch("/tenants/{tenant_id}/activate", response_model=TenantResponse)
def activate_tenant(tenant_id: str, db: Session = Depends(get_db)):
    tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.status = "active"
    db.commit()
    db.refresh(tenant)
    return to_response(tenant)


@app.delete("/tenants/{tenant_id}", status_code=204)
def delete_tenant(tenant_id: str, db: Session = Depends(get_db)):
    tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(tenant)
    db.commit()


@app.get("/plans")
def list_plans():
    return [
        {"name": k, "limits": v}
        for k, v in PLAN_LIMITS.items()
    ]
