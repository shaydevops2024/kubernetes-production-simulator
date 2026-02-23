import os
import time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="DevOps Projects Hub", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Version info (injected at build/deploy time) ──────────────
APP_VERSION   = os.getenv("APP_VERSION",   "v1")
BUILD_DATE    = os.getenv("BUILD_DATE",    "unknown")
GIT_COMMIT    = os.getenv("GIT_COMMIT",    "unknown")
ENVIRONMENT   = os.getenv("ENVIRONMENT",   "local")
REPLICA_ID    = os.getenv("HOSTNAME",      "unknown")  # pod name in K8s

START_TIME = time.time()


# ── Health & readiness ────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "uptime_seconds": round(time.time() - START_TIME, 1),
    }


@app.get("/ready")
def ready():
    return {"status": "ready"}


# ── Version info (used by frontend & Flagger analysis) ────────

@app.get("/api/version")
def version():
    return {
        "version":     APP_VERSION,
        "build_date":  BUILD_DATE,
        "git_commit":  GIT_COMMIT,
        "environment": ENVIRONMENT,
        "replica_id":  REPLICA_ID,
    }


# ── Projects data ─────────────────────────────────────────────

PROJECTS = [
    {
        "id": 1,
        "title": "Production-Ready Microservices E-Commerce Platform",
        "topics": ["Istio", "Distributed Tracing", "Circuit Breakers", "Rate Limiting"],
        "status": "available",
        "folder": "project-01-ecommerce-platform",
    },
    {
        "id": 2,
        "title": "Multi-Tenant SaaS Application Infrastructure",
        "topics": ["Namespaces", "RBAC", "ResourceQuota", "NetworkPolicy", "Multi-tenancy"],
        "status": "available",
        "folder": "project-02-multitenant-saas",
    },
    {
        "id": 3,
        "title": "Real-Time Chat / Messaging Platform",
        "topics": ["WebSockets", "Redis pub/sub", "MinIO/S3", "Horizontal Scaling"],
        "status": "available",
        "folder": "project-03-realtime-chat",
    },
    {
        "id": 4,
        "title": "Full GitOps CI/CD Pipeline with Progressive Delivery",
        "topics": ["GitHub Actions", "ArgoCD", "Flagger", "Canary Deployments", "Rollback"],
        "status": "available",
        "folder": "project-04-gitops-cicd",
    },
    {
        "id": 5,
        "title": "Zero-Trust Security Platform",
        "topics": ["OPA", "Network Policies", "Pod Security Standards"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 6,
        "title": "High-Availability Database Cluster",
        "topics": ["PostgreSQL HA", "Redis Cluster", "StatefulSets"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 7,
        "title": "Multi-Region Active-Active Setup",
        "topics": ["Federation", "Global Load Balancing"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 8,
        "title": "Autoscaling & Cost Optimization",
        "topics": ["HPA", "VPA", "KEDA", "Spot Instances"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 9,
        "title": "Disaster Recovery System",
        "topics": ["Velero", "Cross-Region Replication", "RTO/RPO"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 10,
        "title": "Platform Engineering (IDP)",
        "topics": ["Backstage", "Self-Service Infrastructure"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 11,
        "title": "MLOps Pipeline",
        "topics": ["Kubeflow", "Model Serving", "A/B Testing"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 12,
        "title": "Serverless on Kubernetes",
        "topics": ["Knative", "Event-Driven Architecture"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 13,
        "title": "Zero-Downtime Deployment Strategies",
        "topics": ["Argo Rollouts", "Canary", "Blue-Green"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 14,
        "title": "API Gateway & Rate Limiting",
        "topics": ["Kong", "OAuth2", "JWT", "Traffic Policies"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 15,
        "title": "SRE Practices Platform",
        "topics": ["SLOs", "Error Budgets", "Chaos Engineering"],
        "status": "coming_soon",
        "folder": "",
    },
    {
        "id": 16,
        "title": "Security Compliance & Audit",
        "topics": ["Falco", "OPA Gatekeeper", "CIS Benchmarks"],
        "status": "coming_soon",
        "folder": "",
    },
]


@app.get("/api/projects")
def projects():
    return {
        "total": len(PROJECTS),
        "available": sum(1 for p in PROJECTS if p["status"] == "available"),
        "projects": PROJECTS,
    }


# ── Serve static frontend ─────────────────────────────────────

app.mount("/", StaticFiles(directory="static", html=True), name="static")
