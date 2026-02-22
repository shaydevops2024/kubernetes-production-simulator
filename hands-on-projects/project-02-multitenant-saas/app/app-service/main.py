from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import uuid
import httpx
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(
    title="App Service",
    description="Multi-tenant task management. Pass X-Tenant-ID header to scope all operations to a tenant.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
BILLING_SERVICE_URL = os.getenv("BILLING_SERVICE_URL", "http://localhost:8012")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SEED_TASKS = [
    # Alice Corp — enterprise tenant, many tasks
    {"tenant_id": "alice-corp", "title": "Set up CI/CD pipeline",             "status": "done",        "priority": "high",   "description": "Configure GitHub Actions to build, test, and deploy on every push."},
    {"tenant_id": "alice-corp", "title": "Configure staging environment",      "status": "in_progress", "priority": "high",   "description": "Mirror production setup in staging with separate databases."},
    {"tenant_id": "alice-corp", "title": "Implement monitoring dashboards",    "status": "in_progress", "priority": "medium", "description": "Set up Grafana dashboards for latency, error rate, and throughput."},
    {"tenant_id": "alice-corp", "title": "Security audit Q1",                 "status": "todo",        "priority": "high",   "description": "Run dependency vulnerability scan and penetration test."},
    {"tenant_id": "alice-corp", "title": "Optimize database indexes",         "status": "todo",        "priority": "low",    "description": "Profile slow queries and add missing indexes."},
    # Bob Industries — pro tenant
    {"tenant_id": "bob-industries", "title": "Migrate to microservices",      "status": "in_progress", "priority": "high",   "description": "Break the monolith into independently deployable services."},
    {"tenant_id": "bob-industries", "title": "Load testing campaign",         "status": "todo",        "priority": "medium", "description": "Use k6 to simulate 10k concurrent users and identify bottlenecks."},
    {"tenant_id": "bob-industries", "title": "Renew SSL certificates",        "status": "done",        "priority": "high",   "description": "All certs renewed and auto-renewal configured via cert-manager."},
    # Charlie Ltd — starter tenant, suspended
    {"tenant_id": "charlie-ltd", "title": "Onboarding setup",                 "status": "done",        "priority": "high",   "description": "Initial account configuration and team invitations."},
    {"tenant_id": "charlie-ltd", "title": "Team training session",            "status": "todo",        "priority": "medium", "description": "Schedule and run platform training for the engineering team."},
]


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="todo")      # todo | in_progress | done
    priority = Column(String, default="medium")  # low | medium | high
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def seed_data(db: Session):
    if db.query(TaskModel).count() == 0:
        for t in SEED_TASKS:
            task = TaskModel(
                id=str(uuid.uuid4()),
                tenant_id=t["tenant_id"],
                title=t["title"],
                description=t.get("description"),
                status=t["status"],
                priority=t["priority"],
                created_at=datetime.utcnow(),
            )
            db.add(task)
        db.commit()


with SessionLocal() as _db:
    seed_data(_db)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def record_usage(tenant_id: str, endpoint: str):
    """Fire-and-forget usage record to billing service."""
    try:
        httpx.post(
            f"{BILLING_SERVICE_URL}/record",
            json={"tenant_id": tenant_id, "endpoint": endpoint, "service": "app-service"},
            timeout=1.5,
        )
    except Exception:
        pass  # Never fail a user request because billing is down


# ── Schemas ───────────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    tenant_id: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "healthy", "service": "app-service"}


@app.get("/tasks", response_model=List[TaskResponse])
def list_tasks(x_tenant_id: str = Header(..., description="Tenant slug, e.g. alice-corp"), db: Session = Depends(get_db)):
    """
    List all tasks for a tenant.
    In local Docker Compose this is a single shared service — tenant isolation is enforced by the X-Tenant-ID header.
    In Kubernetes (main/), each tenant gets their own dedicated deployment + database, so no header is needed.
    """
    record_usage(x_tenant_id, "GET /tasks")
    return db.query(TaskModel).filter(TaskModel.tenant_id == x_tenant_id).all()


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    body: TaskCreate,
    x_tenant_id: str = Header(...),
    db: Session = Depends(get_db),
):
    if body.priority not in ("low", "medium", "high"):
        raise HTTPException(status_code=400, detail="priority must be low, medium, or high")
    task = TaskModel(
        id=str(uuid.uuid4()),
        tenant_id=x_tenant_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        created_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    record_usage(x_tenant_id, "POST /tasks")
    return task


@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    body: TaskUpdate,
    x_tenant_id: str = Header(...),
    db: Session = Depends(get_db),
):
    task = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id, TaskModel.tenant_id == x_tenant_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.status is not None:
        if body.status not in ("todo", "in_progress", "done"):
            raise HTTPException(status_code=400, detail="status must be todo, in_progress, or done")
        task.status = body.status
    if body.priority is not None:
        task.priority = body.priority
    db.commit()
    db.refresh(task)
    record_usage(x_tenant_id, f"PUT /tasks/{task_id}")
    return task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: str,
    x_tenant_id: str = Header(...),
    db: Session = Depends(get_db),
):
    task = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id, TaskModel.tenant_id == x_tenant_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    record_usage(x_tenant_id, f"DELETE /tasks/{task_id}")


@app.get("/stats")
def tenant_stats(x_tenant_id: str = Header(...), db: Session = Depends(get_db)):
    tasks = db.query(TaskModel).filter(TaskModel.tenant_id == x_tenant_id).all()
    record_usage(x_tenant_id, "GET /stats")
    return {
        "tenant_id": x_tenant_id,
        "total": len(tasks),
        "todo": sum(1 for t in tasks if t.status == "todo"),
        "in_progress": sum(1 for t in tasks if t.status == "in_progress"),
        "done": sum(1 for t in tasks if t.status == "done"),
    }
