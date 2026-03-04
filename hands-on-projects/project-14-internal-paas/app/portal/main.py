"""
Developer Portal — Internal PaaS
A mock developer self-service portal for the hands-on project.
Provides a REST API with realistic mock data.
"""
import os
import time
import random
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Developer Portal API", version="1.0.0")

# ─── Mock Data ────────────────────────────────────────────────────────────────

TEAMS = [
    {
        "id": "team-alpha",
        "name": "Team Alpha",
        "namespace": "alpha",
        "color": "#6366f1",
        "members": 4,
        "lead": "alice@company.com",
        "description": "Frontend & API services",
        "status": "active",
        "created_at": "2024-01-15",
    },
    {
        "id": "team-beta",
        "name": "Team Beta",
        "namespace": "beta",
        "color": "#10b981",
        "members": 6,
        "lead": "bob@company.com",
        "description": "Data pipelines & analytics",
        "status": "active",
        "created_at": "2024-02-01",
    },
    {
        "id": "team-gamma",
        "name": "Team Gamma",
        "namespace": "gamma",
        "color": "#f59e0b",
        "members": 3,
        "lead": "carol@company.com",
        "description": "Infrastructure & platform",
        "status": "active",
        "created_at": "2024-03-10",
    },
]

NAMESPACES = [
    {
        "name": "alpha",
        "team": "team-alpha",
        "status": "Active",
        "cpu_limit": "4",
        "cpu_used": "1.8",
        "memory_limit": "8Gi",
        "memory_used": "3.2Gi",
        "pod_limit": 20,
        "pod_count": 8,
        "created_at": "2024-01-15",
    },
    {
        "name": "beta",
        "team": "team-beta",
        "status": "Active",
        "cpu_limit": "8",
        "cpu_used": "5.4",
        "memory_limit": "16Gi",
        "memory_used": "9.1Gi",
        "pod_limit": 40,
        "pod_count": 22,
        "created_at": "2024-02-01",
    },
    {
        "name": "gamma",
        "team": "team-gamma",
        "status": "Active",
        "cpu_limit": "2",
        "cpu_used": "0.6",
        "memory_limit": "4Gi",
        "memory_used": "1.1Gi",
        "pod_limit": 10,
        "pod_count": 3,
        "created_at": "2024-03-10",
    },
    {
        "name": "vault",
        "team": "platform",
        "status": "Active",
        "cpu_limit": "2",
        "cpu_used": "0.4",
        "memory_limit": "4Gi",
        "memory_used": "0.8Gi",
        "pod_limit": 10,
        "pod_count": 3,
        "created_at": "2024-01-01",
    },
    {
        "name": "monitoring",
        "team": "platform",
        "status": "Active",
        "cpu_limit": "4",
        "cpu_used": "2.1",
        "memory_limit": "8Gi",
        "memory_used": "4.5Gi",
        "pod_limit": 20,
        "pod_count": 11,
        "created_at": "2024-01-01",
    },
]

SERVICES = [
    {
        "id": "svc-001",
        "name": "api-gateway",
        "team": "team-alpha",
        "namespace": "alpha",
        "image": "harbor.internal/alpha/api-gateway:v2.1.0",
        "replicas": 3,
        "ready": 3,
        "status": "Running",
        "type": "api",
        "port": 8080,
        "ingress": "api.internal.company.com",
        "cpu": "450m",
        "memory": "512Mi",
        "uptime": "14d 6h",
        "last_deploy": "2024-11-28T10:30:00Z",
    },
    {
        "id": "svc-002",
        "name": "user-service",
        "team": "team-alpha",
        "namespace": "alpha",
        "image": "harbor.internal/alpha/user-service:v1.4.2",
        "replicas": 2,
        "ready": 2,
        "status": "Running",
        "type": "backend",
        "port": 8001,
        "ingress": None,
        "cpu": "180m",
        "memory": "256Mi",
        "uptime": "7d 2h",
        "last_deploy": "2024-12-01T09:00:00Z",
    },
    {
        "id": "svc-003",
        "name": "dashboard-ui",
        "team": "team-alpha",
        "namespace": "alpha",
        "image": "harbor.internal/alpha/dashboard:v3.0.1",
        "replicas": 2,
        "ready": 2,
        "status": "Running",
        "type": "frontend",
        "port": 80,
        "ingress": "dashboard.internal.company.com",
        "cpu": "80m",
        "memory": "128Mi",
        "uptime": "3d 14h",
        "last_deploy": "2024-12-05T16:45:00Z",
    },
    {
        "id": "svc-004",
        "name": "data-processor",
        "team": "team-beta",
        "namespace": "beta",
        "image": "harbor.internal/beta/processor:v4.2.0",
        "replicas": 5,
        "ready": 5,
        "status": "Running",
        "type": "worker",
        "port": 8100,
        "ingress": None,
        "cpu": "1200m",
        "memory": "2Gi",
        "uptime": "21d 8h",
        "last_deploy": "2024-11-22T08:00:00Z",
    },
    {
        "id": "svc-005",
        "name": "analytics-api",
        "team": "team-beta",
        "namespace": "beta",
        "image": "harbor.internal/beta/analytics:v2.0.0",
        "replicas": 2,
        "ready": 1,
        "status": "Degraded",
        "type": "api",
        "port": 8200,
        "ingress": "analytics.internal.company.com",
        "cpu": "900m",
        "memory": "1Gi",
        "uptime": "5d 1h",
        "last_deploy": "2024-12-03T14:00:00Z",
    },
    {
        "id": "svc-006",
        "name": "config-service",
        "team": "team-gamma",
        "namespace": "gamma",
        "image": "harbor.internal/gamma/config:v1.1.0",
        "replicas": 1,
        "ready": 1,
        "status": "Running",
        "type": "backend",
        "port": 8300,
        "ingress": None,
        "cpu": "60m",
        "memory": "128Mi",
        "uptime": "30d 0h",
        "last_deploy": "2024-11-13T11:00:00Z",
    },
]

PIPELINES = [
    {
        "id": "pipe-001",
        "name": "api-gateway",
        "repo": "alpha/api-gateway",
        "team": "team-alpha",
        "branch": "main",
        "status": "success",
        "stage": "deploy",
        "duration": "3m 42s",
        "triggered_by": "alice",
        "started_at": "2024-12-08T10:25:00Z",
        "commit": "a3f2c91",
        "commit_msg": "feat: add rate limiting middleware",
    },
    {
        "id": "pipe-002",
        "name": "user-service",
        "repo": "alpha/user-service",
        "team": "team-alpha",
        "branch": "main",
        "status": "success",
        "stage": "deploy",
        "duration": "2m 15s",
        "triggered_by": "alice",
        "started_at": "2024-12-08T09:00:00Z",
        "commit": "b7e1d44",
        "commit_msg": "fix: handle null user gracefully",
    },
    {
        "id": "pipe-003",
        "name": "analytics-api",
        "repo": "beta/analytics",
        "team": "team-beta",
        "branch": "main",
        "status": "failed",
        "stage": "test",
        "duration": "1m 08s",
        "triggered_by": "bob",
        "started_at": "2024-12-08T14:02:00Z",
        "commit": "c9a4f22",
        "commit_msg": "refactor: migrate to new schema",
    },
    {
        "id": "pipe-004",
        "name": "data-processor",
        "repo": "beta/processor",
        "team": "team-beta",
        "branch": "feature/v5",
        "status": "running",
        "stage": "build",
        "duration": "1m 34s",
        "triggered_by": "dave",
        "started_at": "2024-12-08T15:50:00Z",
        "commit": "d2b8e55",
        "commit_msg": "perf: optimize batch size",
    },
    {
        "id": "pipe-005",
        "name": "config-service",
        "repo": "gamma/config",
        "team": "team-gamma",
        "branch": "main",
        "status": "success",
        "stage": "deploy",
        "duration": "1m 55s",
        "triggered_by": "carol",
        "started_at": "2024-12-07T11:00:00Z",
        "commit": "e5c3a77",
        "commit_msg": "chore: bump dependencies",
    },
]

COSTS = {
    "period": "December 2024",
    "total_month": 847.50,
    "teams": [
        {
            "team": "team-alpha",
            "name": "Team Alpha",
            "month_cost": 312.40,
            "cpu_cost": 180.20,
            "memory_cost": 132.20,
            "trend": "+5%",
            "trend_direction": "up",
        },
        {
            "team": "team-beta",
            "name": "Team Beta",
            "month_cost": 421.80,
            "cpu_cost": 290.60,
            "memory_cost": 131.20,
            "trend": "+12%",
            "trend_direction": "up",
        },
        {
            "team": "team-gamma",
            "name": "Team Gamma",
            "month_cost": 113.30,
            "cpu_cost": 60.10,
            "memory_cost": 53.20,
            "trend": "-3%",
            "trend_direction": "down",
        },
    ],
}

SERVICE_CATALOG = [
    {
        "id": "tpl-api",
        "name": "REST API Service",
        "description": "FastAPI-based REST service with health checks, Prometheus metrics, and PostgreSQL connection.",
        "icon": "api",
        "tags": ["python", "fastapi", "postgresql"],
        "template_repo": "templates/rest-api",
    },
    {
        "id": "tpl-worker",
        "name": "Background Worker",
        "description": "Python worker with Kafka consumer, Redis queue support, and KEDA autoscaling.",
        "icon": "worker",
        "tags": ["python", "kafka", "redis", "keda"],
        "template_repo": "templates/worker",
    },
    {
        "id": "tpl-frontend",
        "name": "Frontend SPA",
        "description": "React/nginx static site served via CDN-ready container with ingress and TLS.",
        "icon": "frontend",
        "tags": ["react", "nginx", "ingress"],
        "template_repo": "templates/frontend-spa",
    },
    {
        "id": "tpl-grpc",
        "name": "gRPC Service",
        "description": "Go-based gRPC service with reflection, health protocol, and Protobuf code generation.",
        "icon": "grpc",
        "tags": ["go", "grpc", "protobuf"],
        "template_repo": "templates/grpc-service",
    },
    {
        "id": "tpl-db",
        "name": "PostgreSQL Database",
        "description": "CloudNativePG managed PostgreSQL cluster with automatic backups and failover.",
        "icon": "database",
        "tags": ["postgresql", "cloudnativepg", "ha"],
        "template_repo": "templates/postgresql",
    },
]

# ─── In-memory state for demo deploys / namespace requests ────────────────────

deploy_requests = []
namespace_requests = []

# ─── Pydantic models ──────────────────────────────────────────────────────────

class DeployRequest(BaseModel):
    service_name: str
    team_id: str
    template_id: str
    replicas: int = 1
    image_tag: str = "latest"
    namespace: Optional[str] = None


class NamespaceRequest(BaseModel):
    team_name: str
    lead_email: str
    description: str
    cpu_limit: str = "2"
    memory_limit: str = "4Gi"


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("/app/static/index.html") as f:
        return f.read()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "developer-portal", "version": "1.0.0"}


@app.get("/api/teams")
async def get_teams():
    return TEAMS


@app.get("/api/teams/{team_id}")
async def get_team(team_id: str):
    team = next((t for t in TEAMS if t["id"] == team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@app.get("/api/namespaces")
async def get_namespaces():
    return NAMESPACES


@app.get("/api/namespaces/{name}")
async def get_namespace(name: str):
    ns = next((n for n in NAMESPACES if n["name"] == name), None)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    return ns


@app.get("/api/services")
async def get_services(team_id: Optional[str] = None, namespace: Optional[str] = None):
    result = SERVICES
    if team_id:
        result = [s for s in result if s["team"] == team_id]
    if namespace:
        result = [s for s in result if s["namespace"] == namespace]
    return result


@app.get("/api/services/{service_id}")
async def get_service(service_id: str):
    svc = next((s for s in SERVICES if s["id"] == service_id), None)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc


@app.get("/api/pipelines")
async def get_pipelines(team_id: Optional[str] = None):
    result = PIPELINES
    if team_id:
        result = [p for p in result if p["team"] == team_id]
    return result


@app.get("/api/costs")
async def get_costs():
    return COSTS


@app.get("/api/catalog")
async def get_catalog():
    return SERVICE_CATALOG


@app.get("/api/dashboard")
async def get_dashboard():
    running = sum(1 for s in SERVICES if s["status"] == "Running")
    degraded = sum(1 for s in SERVICES if s["status"] == "Degraded")
    failed_pipes = sum(1 for p in PIPELINES if p["status"] == "failed")
    running_pipes = sum(1 for p in PIPELINES if p["status"] == "running")
    total_pods = sum(n["pod_count"] for n in NAMESPACES)
    return {
        "teams": len(TEAMS),
        "namespaces": len(NAMESPACES),
        "services_running": running,
        "services_degraded": degraded,
        "total_pods": total_pods,
        "pipelines_running": running_pipes,
        "pipelines_failed": failed_pipes,
        "monthly_cost": COSTS["total_month"],
    }


@app.post("/api/deploy")
async def deploy_service(req: DeployRequest):
    team = next((t for t in TEAMS if t["id"] == req.team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    template = next((c for c in SERVICE_CATALOG if c["id"] == req.template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    deploy_id = f"deploy-{int(time.time())}"
    record = {
        "id": deploy_id,
        "service_name": req.service_name,
        "team": req.team_id,
        "namespace": req.namespace or team["namespace"],
        "template": template["name"],
        "replicas": req.replicas,
        "image_tag": req.image_tag,
        "status": "queued",
        "pipeline_url": f"http://woodpecker.internal/pipelines/{deploy_id}",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "message": f"Pipeline triggered. Deploying '{req.service_name}' to namespace '{req.namespace or team['namespace']}'.",
    }
    deploy_requests.append(record)
    return record


@app.get("/api/deploy")
async def list_deploys():
    return deploy_requests


@app.post("/api/namespaces/request")
async def request_namespace(req: NamespaceRequest):
    req_id = f"ns-req-{int(time.time())}"
    record = {
        "id": req_id,
        "team_name": req.team_name,
        "namespace": req.team_name.lower().replace(" ", "-"),
        "lead_email": req.lead_email,
        "description": req.description,
        "cpu_limit": req.cpu_limit,
        "memory_limit": req.memory_limit,
        "status": "pending_approval",
        "requested_at": datetime.utcnow().isoformat() + "Z",
        "message": "Namespace request submitted. Platform team will review within 24 hours.",
    }
    namespace_requests.append(record)
    return record


@app.get("/api/namespaces/requests/list")
async def list_namespace_requests():
    return namespace_requests


# ─── Mount static files ───────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="/app/static"), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
