# app/src/main.py - Updated for self-contained scenarios
# Key changes:
# 1. Monitors BOTH "k8s-multi-demo" and "scenarios" namespaces
# 2. Reads YAML files from scenario directories
# 3. All scenarios marked with namespace: "scenarios"
# 4. Better error handling and logging

from database import get_db, check_db_connection, get_db_stats, User, Task, init_db
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel
import asyncio
import os
import logging
import subprocess
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="K8s Production Demo", version="2.0.0")

# Mount static files directory
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

REQUEST_COUNT = Counter('app_requests_total', 'Total app requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('app_request_duration_seconds', 'Request duration')

app_ready = True
app_healthy = True
load_test_running = False
load_test_task = None

log_buffer = deque(maxlen=100)

# Initialize Kubernetes client
try:
    config.load_incluster_config()
    k8s_apps_v1 = client.AppsV1Api()
    k8s_core_v1 = client.CoreV1Api()
    k8s_available = True
    logger.info("✅ Kubernetes client initialized successfully")
except Exception as e:
    logger.error(f"⚠️ Failed to initialize Kubernetes client: {e}")
    k8s_apps_v1 = None
    k8s_core_v1 = None
    k8s_available = False

class LogBufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_buffer.append({
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'message': log_entry
        })

buffer_handler = LogBufferHandler()
buffer_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(buffer_handler)

APP_ENV = os.getenv('APP_ENV', 'development')
APP_NAME = os.getenv('APP_NAME', 'k8s-demo-app')
SECRET_TOKEN = os.getenv('SECRET_TOKEN', 'no-secret-configured')
CONFIGMAP_VALUE = os.getenv('CONFIGMAP_VALUE', 'no-configmap-configured')

# Cached ArgoCD server status (only check cluster state, not CLI)
_argocd_server_cache = {"server_running": None, "installed": None, "checked": False}

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str

class TaskCreate(BaseModel):
    user_id: str
    title: str
    description: str
    status: str = "pending"
    priority: int = 1

def calculate_age(creation_timestamp):
    """Calculate age from creation timestamp"""
    try:
        if isinstance(creation_timestamp, str):
            created = datetime.fromisoformat(creation_timestamp.replace('Z', '+00:00'))
        else:
            created = creation_timestamp
        
        now = datetime.now(timezone.utc)
        delta = now - created
        days = delta.days
        hours = delta.seconds // 3600
        minutes = delta.seconds // 60
        
        if days > 0:
            return f"{days}d"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}m"
    except Exception as e:
        logger.error(f"Error calculating age: {e}")
        return "unknown"

@app.get("/")
async def root():
    return FileResponse(str(static_dir / "index.html"))

@app.get("/scenarios")
async def scenarios_page():
    return FileResponse(str(static_dir / "scenarios.html"))

@app.get("/scenario/{scenario_id}")
async def scenario_detail_page(scenario_id: str):
    return FileResponse(str(static_dir / "scenario-detail.html"))

@app.get("/argocd-scenarios")
async def argocd_scenarios_page():
    return FileResponse(str(static_dir / "argocd-scenarios.html"))

@app.get("/argocd-scenario/{scenario_id}")
async def argocd_scenario_detail_page(scenario_id: str):
    return FileResponse(str(static_dir / "argocd-scenario-detail.html"))

@app.get("/helm-scenarios")
async def helm_scenarios_page():
    return FileResponse(str(static_dir / "helm-scenarios.html"))

@app.get("/helm-scenario/{scenario_id}")
async def helm_scenario_detail_page(scenario_id: str):
    return FileResponse(str(static_dir / "helm-scenario-detail.html"))

@app.get("/gitlab-ci-scenarios")
async def gitlab_ci_scenarios_page():
    return FileResponse(str(static_dir / "gitlab-ci-scenarios.html"))

@app.get("/gitlab-ci-scenario/{scenario_id}")
async def gitlab_ci_scenario_detail_page(scenario_id: str):
    return FileResponse(str(static_dir / "gitlab-ci-scenario-detail.html"))

@app.get("/health")
async def health():
    REQUEST_COUNT.labels(method='GET', endpoint='/health').inc()
    if app_healthy:
        return {"status": "healthy"}
    return Response(content='{"status": "unhealthy"}', status_code=503)

@app.get("/ready")
async def ready():
    REQUEST_COUNT.labels(method='GET', endpoint='/ready').inc()
    if app_ready:
        return {"status": "ready"}
    return Response(content='{"status": "not ready"}', status_code=503)

@app.post("/simulate/crash")
async def simulate_crash():
    global app_healthy
    app_healthy = False
    logger.warning("🔴 Simulated pod crash - health check will fail")
    return {"status": "unhealthy", "message": "Pod health set to unhealthy"}

@app.post("/simulate/notready")
async def simulate_not_ready():
    global app_ready
    app_ready = False
    logger.warning("⏸️ Simulated pod not ready - readiness check will fail")
    return {"status": "not_ready", "message": "Pod readiness set to not ready"}

@app.post("/reset")
async def reset_health():
    global app_healthy, app_ready
    app_healthy = True
    app_ready = True
    logger.info("✅ Reset pod health and readiness to normal")
    return {"status": "healthy", "message": "Pod health and readiness reset to healthy"}

@app.get("/metrics")
async def metrics():
    REQUEST_COUNT.labels(method='GET', endpoint='/metrics').inc()
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/api/logs")
async def get_logs():
    return {"logs": list(log_buffer)}

@app.get("/api/config")
async def get_config():
    return {
        "app_env": APP_ENV,
        "app_name": APP_NAME,
        "secret_configured": SECRET_TOKEN != "no-secret-configured",
        "configmap_configured": CONFIGMAP_VALUE != "no-configmap-configured"
    }

@app.get("/api/argocd/url")
async def get_argocd_url():
    """Get the appropriate ArgoCD URL based on availability"""
    import socket

    # Try to check if the ingress hostname resolves
    try:
        socket.gethostbyname('k8s-multi-demo.argocd')
        # If hostname resolves, try the ingress URL
        primary_url = 'http://k8s-multi-demo.argocd'
        return {"url": primary_url, "type": "ingress"}
    except socket.gaierror:
        # If hostname doesn't resolve, use NodePort on localhost
        fallback_url = 'http://localhost:30800'
        return {"url": fallback_url, "type": "nodeport"}
    except Exception as e:
        logger.error(f"Error determining ArgoCD URL: {e}")
        # Default to NodePort
        return {"url": "http://localhost:30800", "type": "nodeport"}

@app.get("/api/tools/helm")
async def get_helm_status():
    """Get Helm installation status, version, and release count"""
    result = {
        "installed": False,
        "version": None,
        "release_count": 0,
        "error": None
    }

    # Check Helm CLI version
    try:
        helm_result = subprocess.run(
            ["helm", "version", "--short"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if helm_result.returncode == 0:
            result["installed"] = True
            version_output = helm_result.stdout.strip()
            # Parse version like "v3.17.1+g980d8ac" to get "v3.17.1"
            if version_output.startswith("v"):
                result["version"] = version_output.split("+")[0]
            else:
                result["version"] = version_output
    except FileNotFoundError:
        result["installed"] = False
        result["error"] = "Helm CLI not found"
    except subprocess.TimeoutExpired:
        result["error"] = "Helm version check timed out"
    except Exception as e:
        result["error"] = str(e)

    # Get release count from cluster
    if k8s_available and k8s_core_v1:
        try:
            secrets = k8s_core_v1.list_secret_for_all_namespaces(
                label_selector="owner=helm"
            )
            # Count unique releases (latest revision only)
            releases_dict = {}
            for secret in secrets.items:
                labels = secret.metadata.labels or {}
                name = labels.get("name", "")
                namespace = secret.metadata.namespace
                version = labels.get("version", "1")
                key = f"{namespace}/{name}"
                if key not in releases_dict or int(version) > int(releases_dict[key]):
                    releases_dict[key] = int(version)
            result["release_count"] = len(releases_dict)

            # If CLI not found but releases exist, consider Helm "available"
            if not result["installed"] and result["release_count"] > 0:
                result["installed"] = True
                if not result["version"]:
                    result["version"] = "N/A (releases exist)"
        except Exception as e:
            logger.debug(f"Error counting Helm releases: {e}")

    return result

@app.get("/api/tools/helm/releases")
async def get_helm_releases():
    """Get Helm releases from cluster using Kubernetes API (queries Helm secrets)"""
    result = {"releases": [], "release_count": 0, "error": None}

    if not k8s_available or not k8s_core_v1:
        result["error"] = "Kubernetes API not available"
        return result

    try:
        # Helm stores release data as secrets with label owner=helm
        secrets = k8s_core_v1.list_secret_for_all_namespaces(
            label_selector="owner=helm"
        )

        # Group by release name to get latest revision
        releases_dict = {}
        for secret in secrets.items:
            labels = secret.metadata.labels or {}
            name = labels.get("name", "")
            namespace = secret.metadata.namespace
            status = labels.get("status", "unknown")
            version = labels.get("version", "1")

            # Key by name+namespace to handle same release name in different namespaces
            key = f"{namespace}/{name}"

            # Keep the highest version (latest revision)
            if key not in releases_dict or int(version) > int(releases_dict[key].get("revision", "0")):
                releases_dict[key] = {
                    "name": name,
                    "namespace": namespace,
                    "status": status,
                    "chart": labels.get("chart", ""),
                    "app_version": "",
                    "revision": version
                }

        result["releases"] = list(releases_dict.values())
        result["release_count"] = len(result["releases"])

    except ApiException as e:
        if e.status == 403:
            result["error"] = "No permission to list secrets"
        else:
            result["error"] = f"API error: {e.status}"
        logger.debug(f"Error listing Helm releases: {e}")
    except Exception as e:
        result["error"] = str(e)
        logger.debug(f"Error listing Helm releases: {e}")

    return result

@app.get("/api/tools/argocd")
async def get_argocd_status():
    """Get ArgoCD installation status, version, server status, and app count"""
    global _argocd_server_cache

    result = {
        "installed": False,
        "version": None,
        "server_running": False,
        "app_count": 0,
        "error": None
    }

    # Check ArgoCD CLI version
    try:
        argocd_result = subprocess.run(
            ["argocd", "version", "--client", "--short"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if argocd_result.returncode == 0:
            result["installed"] = True
            version_output = argocd_result.stdout.strip()
            # Parse version like "argocd: v3.2.6+65b0293" or just "v3.2.6+65b0293"
            if ":" in version_output:
                version_output = version_output.split(":")[1].strip()
            if version_output.startswith("v"):
                result["version"] = version_output.split("+")[0]
            else:
                result["version"] = version_output
    except FileNotFoundError:
        # CLI not installed, check if server is running in cluster
        pass
    except subprocess.TimeoutExpired:
        result["error"] = "ArgoCD version check timed out"
    except Exception as e:
        logger.debug(f"ArgoCD CLI check error: {e}")

    if not k8s_available or not k8s_apps_v1:
        if not result["installed"]:
            result["error"] = "Kubernetes API not available"
        return result

    # Check if ArgoCD server is running in cluster
    try:
        deployments = k8s_apps_v1.list_namespaced_deployment(namespace="argocd")
        argocd_deployments = [d for d in deployments.items if "argocd" in d.metadata.name.lower()]

        if argocd_deployments:
            if not result["installed"]:
                result["installed"] = True
            server_dep = next((d for d in argocd_deployments if "server" in d.metadata.name.lower()), None)
            if server_dep:
                ready = server_dep.status.ready_replicas or 0
                desired = server_dep.spec.replicas or 1
                result["server_running"] = ready >= desired
                # Get version from image tag if not already set
                if not result["version"] and server_dep.spec.template.spec.containers:
                    image = server_dep.spec.template.spec.containers[0].image
                    if ":" in image:
                        tag = image.split(":")[-1]
                        if tag.startswith("v"):
                            result["version"] = tag.split("+")[0]
    except ApiException as e:
        if e.status == 404:
            pass  # Namespace doesn't exist
        elif e.status == 403:
            result["error"] = "No permission to check argocd namespace"
        else:
            logger.debug(f"Error checking ArgoCD deployments: {e}")
    except Exception as e:
        logger.debug(f"Error checking ArgoCD: {e}")

    # Get app count from ArgoCD Application CRDs
    try:
        custom_api = client.CustomObjectsApi()
        apps = custom_api.list_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argocd",
            plural="applications"
        )
        result["app_count"] = len(apps.get("items", []))
    except ApiException as e:
        if e.status not in [404, 403]:
            logger.debug(f"Error counting ArgoCD apps: {e}")
    except Exception as e:
        logger.debug(f"Error counting ArgoCD apps: {e}")

    # Cache the results
    _argocd_server_cache["checked"] = True
    _argocd_server_cache["installed"] = result["installed"]
    _argocd_server_cache["server_running"] = result["server_running"]

    return result

@app.get("/api/tools/argocd/apps")
async def get_argocd_apps():
    """Get ArgoCD applications from cluster using Kubernetes API (queries Application CRDs)"""
    result = {"applications": [], "app_count": 0, "error": None}

    if not k8s_available:
        result["error"] = "Kubernetes API not available"
        return result

    try:
        # Use CustomObjectsApi to query ArgoCD Application CRDs
        custom_api = client.CustomObjectsApi()
        apps = custom_api.list_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argocd",
            plural="applications"
        )

        items = apps.get("items", [])
        for app in items:
            metadata = app.get("metadata", {})
            status = app.get("status", {})
            health = status.get("health", {})
            sync = status.get("sync", {})

            result["applications"].append({
                "name": metadata.get("name", ""),
                "namespace": metadata.get("namespace", "argocd"),
                "health": health.get("status", "Unknown"),
                "sync": sync.get("status", "Unknown"),
                "revision": sync.get("revision", "")[:7] if sync.get("revision") else ""
            })
        result["app_count"] = len(result["applications"])

    except ApiException as e:
        if e.status == 404:
            # ArgoCD CRDs not installed or namespace doesn't exist
            result["error"] = None  # Not an error, just no ArgoCD
        elif e.status == 403:
            result["error"] = "No permission to list ArgoCD applications"
        else:
            result["error"] = f"API error: {e.status}"
        logger.debug(f"Error getting ArgoCD applications: {e}")
    except Exception as e:
        result["error"] = str(e)
        logger.debug(f"Error getting ArgoCD applications: {e}")

    return result

@app.get("/api/cluster/stats")
async def get_cluster_stats():
    """Get Kubernetes cluster statistics - monitors BOTH namespaces"""
    namespaces = ["k8s-multi-demo", "scenarios"]
    
    if not k8s_available or not k8s_apps_v1 or not k8s_core_v1:
        return {
            "deployments": {"count": 0, "details": []},
            "pods": {"count": 0, "details": []},
            "nodes": {"count": 0, "details": []},
            "namespaces": []
        }
    
    deployments_info = {"count": 0, "details": []}
    pods_info = {"count": 0, "details": []}
    nodes_info = {"count": 0, "details": []}
    namespace_info = []
    
    # Get deployments from both namespaces
    for namespace in namespaces:
        try:
            deployments = k8s_apps_v1.list_namespaced_deployment(namespace=namespace)
            deployments_info["count"] += len(deployments.items)
            
            for deployment in deployments.items:
                name = deployment.metadata.name
                spec_replicas = deployment.spec.replicas or 0
                ready_replicas = deployment.status.ready_replicas or 0
                updated_replicas = deployment.status.updated_replicas or 0
                available_replicas = deployment.status.available_replicas or 0
                age = calculate_age(deployment.metadata.creation_timestamp)
                
                deployments_info["details"].append({
                    "name": name,
                    "namespace": namespace,
                    "ready": f"{ready_replicas}/{spec_replicas}",
                    "up_to_date": updated_replicas,
                    "available": available_replicas,
                    "age": age
                })
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Error fetching deployments from {namespace}: {e}")
    
    # Get pods from both namespaces
    for namespace in namespaces:
        try:
            pods = k8s_core_v1.list_namespaced_pod(namespace=namespace)
            pods_info["count"] += len(pods.items)
            
            for pod in pods.items:
                name = pod.metadata.name
                status = pod.status.phase or "Unknown"
                
                container_statuses = pod.status.container_statuses or []
                ready_count = sum(1 for c in container_statuses if c.ready)
                total_count = len(container_statuses)
                ready = f"{ready_count}/{total_count}"
                
                restarts = sum(c.restart_count for c in container_statuses)
                age = calculate_age(pod.metadata.creation_timestamp)
                
                pods_info["details"].append({
                    "name": name,
                    "namespace": namespace,
                    "ready": ready,
                    "status": status,
                    "restarts": restarts,
                    "age": age
                })
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Error fetching pods from {namespace}: {e}")
    
    # Get namespace info
    for namespace in namespaces:
        try:
            ns = k8s_core_v1.read_namespace(name=namespace)
            namespace_info.append({
                "name": namespace,
                "status": ns.status.phase if ns.status else "Unknown",
                "age": calculate_age(ns.metadata.creation_timestamp)
            })
        except ApiException as e:
            if e.status == 404:
                namespace_info.append({
                    "name": namespace,
                    "status": "NotFound",
                    "age": "N/A"
                })
    
    # Get nodes
    try:
        nodes = k8s_core_v1.list_node()
        nodes_info["count"] = len(nodes.items)
        
        for node in nodes.items:
            name = node.metadata.name
            
            conditions = node.status.conditions or []
            ready_condition = next((c for c in conditions if c.type == "Ready"), None)
            status = "Ready" if ready_condition and ready_condition.status == "True" else "NotReady"
            
            labels = node.metadata.labels or {}
            roles = []
            if "node-role.kubernetes.io/control-plane" in labels or "node-role.kubernetes.io/master" in labels:
                roles.append("control-plane")
            if "node-role.kubernetes.io/worker" in labels:
                roles.append("worker")
            role = ",".join(roles) if roles else "worker"
            
            age = calculate_age(node.metadata.creation_timestamp)
            version = node.status.node_info.kubelet_version if node.status.node_info else "unknown"
            
            nodes_info["details"].append({
                "name": name,
                "status": status,
                "roles": role,
                "age": age,
                "version": version
            })
    except ApiException as e:
        logger.error(f"Error fetching nodes: {e}")
    
    return {
        "deployments": deployments_info,
        "pods": pods_info,
        "nodes": nodes_info,
        "namespaces": namespace_info
    }

# Database endpoints
@app.post("/api/database/init")
async def initialize_database(db: Session = Depends(get_db)):
    try:
        init_db()
        return {"message": "Database initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/status")
async def database_status():
    try:
        is_connected, message = check_db_connection()
        stats = get_db_stats() if is_connected else {}
        return {"connected": is_connected, "message": message, "stats": stats}
    except Exception as e:
        logger.error(f"Database status check error: {e}")
        return {"connected": False, "error": str(e)}

@app.get("/api/db/stats")
async def get_database_stats():
    """Get database statistics for the Stateful-DB tab"""
    try:
        stats = get_db_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"connected": False, "error": str(e)}

@app.get("/api/db/info")
async def get_database_info():
    """Get database StatefulSet, Secret, and ConfigMap information"""
    try:
        if not k8s_available or not k8s_apps_v1 or not k8s_core_v1:
            return {
                "uses_secret": False,
                "uses_configmap": False,
                "error": "Kubernetes API not available"
            }

        namespace = "k8s-multi-demo"
        info = {
            "uses_secret": False,
            "secret_name": None,
            "uses_configmap": False,
            "configmap_name": None
        }

        # Check if Secret exists
        try:
            secret = k8s_core_v1.read_namespaced_secret(name="postgres-secret", namespace=namespace)
            info["uses_secret"] = True
            info["secret_name"] = secret.metadata.name
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Error fetching Secret: {e}")

        # Check if ConfigMap exists
        try:
            configmap = k8s_core_v1.read_namespaced_config_map(name="postgres-config", namespace=namespace)
            info["uses_configmap"] = True
            info["configmap_name"] = configmap.metadata.name
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Error fetching ConfigMap: {e}")

        return info
    except Exception as e:
        logger.error(f"Error in get_database_info: {e}")
        return {
            "uses_secret": False,
            "uses_configmap": False,
            "error": str(e)
        }

@app.post("/api/users")
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        db_user = User(username=user.username, email=user.email, full_name=user.full_name)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user.to_dict()
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        # Check for specific database errors and provide user-friendly messages
        if "duplicate key" in error_msg.lower() and "username" in error_msg.lower():
            raise HTTPException(status_code=400, detail=f"Username '{user.username}' already exists. Please choose a different username.")
        elif "duplicate key" in error_msg.lower() and "email" in error_msg.lower():
            raise HTTPException(status_code=400, detail=f"Email '{user.email}' already exists. Please use a different email.")
        else:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(status_code=500, detail="Failed to create user. Please try again.")

@app.get("/api/users")
async def list_users(db: Session = Depends(get_db)):
    try:
        users = db.query(User).all()
        return {"users": [user.to_dict() for user in users]}
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks")
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    try:
        db_task = Task(user_id=task.user_id, title=task.title, description=task.description, status=task.status, priority=task.priority)
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task.to_dict()
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        logger.error(f"Error creating task: {e}")
        if "foreign key" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Invalid user ID. Please select a valid user.")
        else:
            raise HTTPException(status_code=500, detail="Failed to create task. Please try again.")

@app.get("/api/tasks")
async def list_tasks(db: Session = Depends(get_db)):
    try:
        tasks = db.query(Task).all()
        return {"tasks": [task.to_dict() for task in tasks]}
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Load test endpoints (unchanged)
@app.post("/api/load-test/start")
async def start_load_test():
    global load_test_running, load_test_task
    if load_test_running:
        return {"message": "Load test already running"}
    async def generate_load():
        global load_test_running
        logger.info("Load test started")
        while load_test_running:
            try:
                _ = sum(i * i for i in range(10000))
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Load test error: {e}")
                break
        logger.info("Load test stopped")
    load_test_running = True
    load_test_task = asyncio.create_task(generate_load())
    return {"message": "Load test started", "status": "running"}

@app.post("/api/load-test/stop")
async def stop_load_test():
    global load_test_running, load_test_task
    if not load_test_running:
        return {"message": "Load test not running"}
    load_test_running = False
    if load_test_task and not load_test_task.done():
        load_test_task.cancel()
        try:
            await load_test_task
        except asyncio.CancelledError:
            pass
    return {"message": "Load test stopped", "status": "stopped"}

@app.get("/api/load-test/status")
async def load_test_status():
    return {"running": load_test_running, "status": "running" if load_test_running else "stopped"}

@app.get("/api/scenarios")
async def get_scenarios():
    """Get list of all available scenarios"""
    try:
        # Try multiple possible locations for scenarios directory
        possible_paths = [
            Path("/scenarios"),  # Docker mount
            Path("/app/k8s-scenarios"),  # Alternative
            Path(__file__).parent.parent.parent / "k8s-scenarios"  # Dev
        ]
        
        scenarios_dir = None
        for path in possible_paths:
            if path.exists() and path.is_dir():
                scenarios_dir = path
                logger.info(f"Found scenarios at: {scenarios_dir}")
                break
        
        if not scenarios_dir:
            logger.warning("No scenarios directory found")
            return {"scenarios": []}
        
        scenarios = []
        scenario_dirs = sorted([d for d in scenarios_dir.iterdir() if d.is_dir()])
        logger.info(f"Found {len(scenario_dirs)} scenario directories")
        
        for scenario_dir in scenario_dirs:
            try:
                readme_path = scenario_dir / "README.md"
                commands_path = scenario_dir / "commands.json"
                
                scenario_info = {
                    "id": scenario_dir.name,
                    "name": scenario_dir.name.replace("-", " ").title(),
                    "description": "No description available",
                    "difficulty": "medium",
                    "duration": "20 min",
                    "special": "special" in scenario_dir.name.lower(),
                    "readme": "",
                    "command_count": 0,
                    "namespace": "scenarios"
                }
                
                # Read README
                if readme_path.exists():
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
                        if lines:
                            scenario_info["description"] = lines[0][:200]
                        scenario_info["readme"] = content
                
                # Read commands.json
                if commands_path.exists():
                    with open(commands_path, 'r', encoding='utf-8') as f:
                        commands_data = json.load(f)
                        scenario_info["command_count"] = len(commands_data.get("commands", []))
                        scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                        scenario_info["duration"] = commands_data.get("duration", "20 min")
                
                # Count YAML files
                yaml_files = list(scenario_dir.glob("*.yaml")) + list(scenario_dir.glob("*.yml"))
                scenario_info["yaml_file_count"] = len(yaml_files)
                
                scenarios.append(scenario_info)
            except Exception as e:
                logger.error(f"Error processing scenario {scenario_dir.name}: {e}")
                continue
        
        logger.info(f"Processed {len(scenarios)} scenarios")
        return {"scenarios": scenarios}
    except Exception as e:
        logger.error(f"Fatal error in get_scenarios: {e}", exc_info=True)
        return {"scenarios": [], "error": str(e)}

@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get detailed scenario info including YAML files"""
    try:
        possible_paths = [Path("/scenarios"), Path("/app/k8s-scenarios"), Path(__file__).parent.parent.parent / "k8s-scenarios"]
        
        scenario_dir = None
        for base_path in possible_paths:
            test_path = base_path / scenario_id
            if test_path.exists() and test_path.is_dir():
                scenario_dir = test_path
                break
        
        if not scenario_dir:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
        
        logger.info(f"Loading scenario from: {scenario_dir}")
        
        scenario_info = {
            "id": scenario_id,
            "name": scenario_id.replace("-", " ").title(),
            "readme": "",
            "commands": [],
            "yaml_files": [],
            "difficulty": "medium",
            "duration": "20 min",
            "namespace": "scenarios"
        }
        
        # Read README
        readme_path = scenario_dir / "README.md"
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                scenario_info["readme"] = f.read()
        else:
            scenario_info["readme"] = "# No README available"
        
        # Read commands.json
        commands_path = scenario_dir / "commands.json"
        if commands_path.exists():
            with open(commands_path, 'r', encoding='utf-8') as f:
                commands_data = json.load(f)
                scenario_info["commands"] = commands_data.get("commands", [])
                scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                scenario_info["duration"] = commands_data.get("duration", "20 min")
        
        # Read ALL YAML files
        yaml_files = list(scenario_dir.glob("*.yaml")) + list(scenario_dir.glob("*.yml"))
        
        # Sort: deployment/statefulset first, then service, then others
        def yaml_sort_key(p):
            name = p.name.lower()
            if 'deployment' in name or 'statefulset' in name:
                return (0, name)
            elif 'service' in name:
                return (1, name)
            else:
                return (2, name)
        
        yaml_files = sorted(yaml_files, key=yaml_sort_key)
        logger.info(f"Found {len(yaml_files)} YAML files for {scenario_id}")
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    scenario_info["yaml_files"].append({
                        "name": yaml_file.name,
                        "content": content
                    })
            except Exception as e:
                logger.error(f"Error reading {yaml_file.name}: {e}")
                scenario_info["yaml_files"].append({
                    "name": yaml_file.name,
                    "content": f"# Error loading file: {str(e)}"
                })
        
        logger.info(f"Scenario {scenario_id}: {len(scenario_info['commands'])} commands, {len(scenario_info['yaml_files'])} YAML files")
        return scenario_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_scenario: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scenarios/{scenario_id}/validate")
async def validate_scenario(scenario_id: str):
    """Run validation script"""
    try:
        logger.info(f"Validating scenario: {scenario_id}")
        
        possible_paths = [Path("/scenarios"), Path("/app/k8s-scenarios"), Path(__file__).parent.parent.parent / "k8s-scenarios"]
        
        scenario_dir = None
        for base_path in possible_paths:
            test_path = base_path / scenario_id
            if test_path.exists():
                scenario_dir = test_path
                break
        
        if not scenario_dir:
            return {"success": False, "message": f"Scenario not found: {scenario_id}", "output": "", "error": ""}
        
        validate_script = scenario_dir / "validate.sh"
        if not validate_script.exists():
            return {"success": False, "message": "No validation script found", "output": "", "error": ""}
        
        result = subprocess.run(["bash", str(validate_script)], capture_output=True, text=True, timeout=60, cwd=str(scenario_dir))
        
        return {
            "success": result.returncode == 0,
            "message": "Validation completed" if result.returncode == 0 else "Validation failed",
            "output": result.stdout,
            "error": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Validation timed out", "output": "", "error": "Timeout"}
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {"success": False, "message": f"Error: {str(e)}", "output": "", "error": str(e)}

@app.get("/api/argocd-scenarios")
async def get_argocd_scenarios():
    """Get list of all available ArgoCD scenarios"""
    try:
        possible_paths = [
            Path("/argocd-scenarios"),
            Path("/app/argocd-scenarios"),
            Path(__file__).parent.parent.parent / "argocd-scenarios"
        ]

        scenarios_dir = None
        for path in possible_paths:
            if path.exists() and path.is_dir():
                scenarios_dir = path
                logger.info(f"Found ArgoCD scenarios at: {scenarios_dir}")
                break

        if not scenarios_dir:
            logger.warning("No ArgoCD scenarios directory found")
            return {"scenarios": []}

        scenarios = []
        scenario_dirs = sorted([d for d in scenarios_dir.iterdir() if d.is_dir()])
        logger.info(f"Found {len(scenario_dirs)} ArgoCD scenario directories")

        for scenario_dir in scenario_dirs:
            try:
                readme_path = scenario_dir / "README.md"
                commands_path = scenario_dir / "commands.json"

                scenario_info = {
                    "id": scenario_dir.name,
                    "name": scenario_dir.name.replace("-", " ").title(),
                    "description": "No description available",
                    "difficulty": "medium",
                    "duration": "15 min",
                    "readme": "",
                    "command_count": 0,
                    "namespace": "argocd"
                }

                if readme_path.exists():
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
                        if lines:
                            scenario_info["description"] = lines[0][:200]
                        scenario_info["readme"] = content

                if commands_path.exists():
                    with open(commands_path, 'r', encoding='utf-8') as f:
                        commands_data = json.load(f)
                        scenario_info["command_count"] = len(commands_data.get("commands", []))
                        scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                        scenario_info["duration"] = commands_data.get("duration", "15 min")

                yaml_files = list(scenario_dir.glob("*.yaml")) + list(scenario_dir.glob("*.yml"))
                scenario_info["yaml_file_count"] = len(yaml_files)

                scenarios.append(scenario_info)
            except Exception as e:
                logger.error(f"Error processing ArgoCD scenario {scenario_dir.name}: {e}")
                continue

        logger.info(f"Processed {len(scenarios)} ArgoCD scenarios")
        return {"scenarios": scenarios}
    except Exception as e:
        logger.error(f"Fatal error in get_argocd_scenarios: {e}", exc_info=True)
        return {"scenarios": [], "error": str(e)}

@app.get("/api/argocd-scenarios/{scenario_id}")
async def get_argocd_scenario(scenario_id: str):
    """Get detailed ArgoCD scenario info including YAML files"""
    try:
        possible_paths = [
            Path("/argocd-scenarios"),
            Path("/app/argocd-scenarios"),
            Path(__file__).parent.parent.parent / "argocd-scenarios"
        ]

        scenario_dir = None
        for base_path in possible_paths:
            test_path = base_path / scenario_id
            if test_path.exists() and test_path.is_dir():
                scenario_dir = test_path
                break

        if not scenario_dir:
            raise HTTPException(status_code=404, detail=f"ArgoCD scenario '{scenario_id}' not found")

        logger.info(f"Loading ArgoCD scenario from: {scenario_dir}")

        scenario_info = {
            "id": scenario_id,
            "name": scenario_id.replace("-", " ").title(),
            "readme": "",
            "commands": [],
            "yaml_files": [],
            "difficulty": "medium",
            "duration": "15 min",
            "namespace": "argocd"
        }

        readme_path = scenario_dir / "README.md"
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                scenario_info["readme"] = f.read()
        else:
            scenario_info["readme"] = "# No README available"

        commands_path = scenario_dir / "commands.json"
        if commands_path.exists():
            with open(commands_path, 'r', encoding='utf-8') as f:
                commands_data = json.load(f)
                scenario_info["commands"] = commands_data.get("commands", [])
                scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                scenario_info["duration"] = commands_data.get("duration", "15 min")

        # Collect YAML files from scenario dir and subdirectories
        yaml_files = []
        for pattern in ["*.yaml", "*.yml"]:
            yaml_files.extend(scenario_dir.glob(pattern))
            yaml_files.extend(scenario_dir.glob(f"**/{pattern}"))

        # Deduplicate and sort
        seen = set()
        unique_yaml = []
        for f in yaml_files:
            if f.resolve() not in seen:
                seen.add(f.resolve())
                unique_yaml.append(f)

        def yaml_sort_key(p):
            name = p.name.lower()
            if 'application' in name or 'parent' in name:
                return (0, name)
            elif 'project' in name:
                return (1, name)
            elif 'deployment' in name or 'rollout' in name:
                return (2, name)
            elif 'service' in name:
                return (3, name)
            else:
                return (4, name)

        unique_yaml = sorted(unique_yaml, key=yaml_sort_key)
        logger.info(f"Found {len(unique_yaml)} YAML files for ArgoCD scenario {scenario_id}")

        for yaml_file in unique_yaml:
            try:
                rel_path = yaml_file.relative_to(scenario_dir)
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    scenario_info["yaml_files"].append({
                        "name": str(rel_path),
                        "content": content
                    })
            except Exception as e:
                logger.error(f"Error reading {yaml_file.name}: {e}")
                scenario_info["yaml_files"].append({
                    "name": yaml_file.name,
                    "content": f"# Error loading file: {str(e)}"
                })

        logger.info(f"ArgoCD scenario {scenario_id}: {len(scenario_info['commands'])} commands, {len(scenario_info['yaml_files'])} YAML files")
        return scenario_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_argocd_scenario: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/helm-scenarios")
async def get_helm_scenarios():
    """Get list of all available Helm scenarios"""
    try:
        possible_paths = [
            Path("/helm-scenarios"),
            Path("/app/helm-scenarios"),
            Path(__file__).parent.parent.parent / "helm-scenarios"
        ]

        scenarios_dir = None
        for path in possible_paths:
            if path.exists() and path.is_dir():
                scenarios_dir = path
                logger.info(f"Found Helm scenarios at: {scenarios_dir}")
                break

        if not scenarios_dir:
            logger.warning("No Helm scenarios directory found")
            return {"scenarios": []}

        scenarios = []
        scenario_dirs = sorted([d for d in scenarios_dir.iterdir() if d.is_dir()])
        logger.info(f"Found {len(scenario_dirs)} Helm scenario directories")

        for scenario_dir in scenario_dirs:
            try:
                readme_path = scenario_dir / "README.md"
                commands_path = scenario_dir / "commands.json"

                scenario_info = {
                    "id": scenario_dir.name,
                    "name": scenario_dir.name.replace("-", " ").title(),
                    "description": "No description available",
                    "difficulty": "medium",
                    "duration": "20 min",
                    "readme": "",
                    "command_count": 0,
                    "namespace": "helm-scenarios"
                }

                if readme_path.exists():
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
                        if lines:
                            scenario_info["description"] = lines[0][:200]
                        scenario_info["readme"] = content

                if commands_path.exists():
                    with open(commands_path, 'r', encoding='utf-8') as f:
                        commands_data = json.load(f)
                        scenario_info["command_count"] = len(commands_data.get("commands", []))
                        scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                        scenario_info["duration"] = commands_data.get("duration", "20 min")

                yaml_files = list(scenario_dir.glob("*.yaml")) + list(scenario_dir.glob("*.yml"))
                scenario_info["yaml_file_count"] = len(yaml_files)

                scenarios.append(scenario_info)
            except Exception as e:
                logger.error(f"Error processing Helm scenario {scenario_dir.name}: {e}")
                continue

        logger.info(f"Processed {len(scenarios)} Helm scenarios")
        return {"scenarios": scenarios}
    except Exception as e:
        logger.error(f"Fatal error in get_helm_scenarios: {e}", exc_info=True)
        return {"scenarios": [], "error": str(e)}

@app.get("/api/helm-scenarios/{scenario_id}")
async def get_helm_scenario(scenario_id: str):
    """Get detailed Helm scenario info including YAML files"""
    try:
        possible_paths = [
            Path("/helm-scenarios"),
            Path("/app/helm-scenarios"),
            Path(__file__).parent.parent.parent / "helm-scenarios"
        ]

        scenario_dir = None
        for base_path in possible_paths:
            test_path = base_path / scenario_id
            if test_path.exists() and test_path.is_dir():
                scenario_dir = test_path
                break

        if not scenario_dir:
            raise HTTPException(status_code=404, detail=f"Helm scenario '{scenario_id}' not found")

        logger.info(f"Loading Helm scenario from: {scenario_dir}")

        scenario_info = {
            "id": scenario_id,
            "name": scenario_id.replace("-", " ").title(),
            "readme": "",
            "commands": [],
            "yaml_files": [],
            "difficulty": "medium",
            "duration": "20 min",
            "namespace": "helm-scenarios"
        }

        readme_path = scenario_dir / "README.md"
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                scenario_info["readme"] = f.read()
        else:
            scenario_info["readme"] = "# No README available"

        commands_path = scenario_dir / "commands.json"
        if commands_path.exists():
            with open(commands_path, 'r', encoding='utf-8') as f:
                commands_data = json.load(f)
                scenario_info["commands"] = commands_data.get("commands", [])
                scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                scenario_info["duration"] = commands_data.get("duration", "20 min")

        # Collect YAML files from scenario dir and subdirectories
        yaml_files = []
        for pattern in ["*.yaml", "*.yml"]:
            yaml_files.extend(scenario_dir.glob(pattern))
            yaml_files.extend(scenario_dir.glob(f"**/{pattern}"))

        # Deduplicate and sort
        seen = set()
        unique_yaml = []
        for f in yaml_files:
            if f.resolve() not in seen:
                seen.add(f.resolve())
                unique_yaml.append(f)

        def yaml_sort_key(p):
            name = p.name.lower()
            if 'chart' in name:
                return (0, name)
            elif 'values' in name:
                return (1, name)
            elif 'deployment' in name:
                return (2, name)
            elif 'service' in name:
                return (3, name)
            else:
                return (4, name)

        unique_yaml = sorted(unique_yaml, key=yaml_sort_key)
        logger.info(f"Found {len(unique_yaml)} YAML files for Helm scenario {scenario_id}")

        for yaml_file in unique_yaml:
            try:
                rel_path = yaml_file.relative_to(scenario_dir)
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    scenario_info["yaml_files"].append({
                        "name": str(rel_path),
                        "content": content
                    })
            except Exception as e:
                logger.error(f"Error reading {yaml_file.name}: {e}")
                scenario_info["yaml_files"].append({
                    "name": yaml_file.name,
                    "content": f"# Error loading file: {str(e)}"
                })

        logger.info(f"Helm scenario {scenario_id}: {len(scenario_info['commands'])} commands, {len(scenario_info['yaml_files'])} YAML files")
        return scenario_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_helm_scenario: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gitlab-ci-scenarios")
async def get_gitlab_ci_scenarios():
    """Get list of all available GitLab CI scenarios"""
    try:
        possible_paths = [
            Path("/gitlab-ci-scenarios"),
            Path("/app/gitlab-ci-scenarios"),
            Path(__file__).parent.parent.parent / "gitlab-ci-scenarios"
        ]

        scenarios_dir = None
        for path in possible_paths:
            if path.exists() and path.is_dir():
                scenarios_dir = path
                logger.info(f"Found GitLab CI scenarios at: {scenarios_dir}")
                break

        if not scenarios_dir:
            logger.warning("No GitLab CI scenarios directory found")
            return {"scenarios": []}

        scenarios = []
        scenario_dirs = sorted([d for d in scenarios_dir.iterdir() if d.is_dir()])
        logger.info(f"Found {len(scenario_dirs)} GitLab CI scenario directories")

        for scenario_dir in scenario_dirs:
            try:
                readme_path = scenario_dir / "README.md"
                commands_path = scenario_dir / "commands.json"

                scenario_info = {
                    "id": scenario_dir.name,
                    "name": scenario_dir.name.replace("-", " ").title(),
                    "description": "No description available",
                    "difficulty": "medium",
                    "duration": "15 min",
                    "readme": "",
                    "command_count": 0,
                    "namespace": "gitlab-ci-scenarios"
                }

                if readme_path.exists():
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
                        if lines:
                            scenario_info["description"] = lines[0][:200]
                        scenario_info["readme"] = content

                if commands_path.exists():
                    with open(commands_path, 'r', encoding='utf-8') as f:
                        commands_data = json.load(f)
                        scenario_info["command_count"] = len(commands_data.get("commands", []))
                        scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                        scenario_info["duration"] = commands_data.get("duration", "15 min")

                yaml_files = list(scenario_dir.glob("*.yaml")) + list(scenario_dir.glob("*.yml"))
                scenario_info["yaml_file_count"] = len(yaml_files)

                scenarios.append(scenario_info)
            except Exception as e:
                logger.error(f"Error processing GitLab CI scenario {scenario_dir.name}: {e}")
                continue

        logger.info(f"Processed {len(scenarios)} GitLab CI scenarios")
        return {"scenarios": scenarios}
    except Exception as e:
        logger.error(f"Fatal error in get_gitlab_ci_scenarios: {e}", exc_info=True)
        return {"scenarios": [], "error": str(e)}

@app.get("/api/gitlab-ci-scenarios/{scenario_id}")
async def get_gitlab_ci_scenario(scenario_id: str):
    """Get detailed GitLab CI scenario info including YAML files"""
    try:
        possible_paths = [
            Path("/gitlab-ci-scenarios"),
            Path("/app/gitlab-ci-scenarios"),
            Path(__file__).parent.parent.parent / "gitlab-ci-scenarios"
        ]

        scenario_dir = None
        for base_path in possible_paths:
            test_path = base_path / scenario_id
            if test_path.exists() and test_path.is_dir():
                scenario_dir = test_path
                break

        if not scenario_dir:
            raise HTTPException(status_code=404, detail=f"GitLab CI scenario '{scenario_id}' not found")

        logger.info(f"Loading GitLab CI scenario from: {scenario_dir}")

        scenario_info = {
            "id": scenario_id,
            "name": scenario_id.replace("-", " ").title(),
            "readme": "",
            "commands": [],
            "yaml_files": [],
            "difficulty": "medium",
            "duration": "15 min",
            "namespace": "gitlab-ci-scenarios"
        }

        readme_path = scenario_dir / "README.md"
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                scenario_info["readme"] = f.read()
        else:
            scenario_info["readme"] = "# No README available"

        commands_path = scenario_dir / "commands.json"
        if commands_path.exists():
            with open(commands_path, 'r', encoding='utf-8') as f:
                commands_data = json.load(f)
                scenario_info["commands"] = commands_data.get("commands", [])
                scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                scenario_info["duration"] = commands_data.get("duration", "15 min")

        # Collect YAML files from scenario dir and subdirectories
        yaml_files = []
        for pattern in ["*.yaml", "*.yml"]:
            yaml_files.extend(scenario_dir.glob(pattern))
            yaml_files.extend(scenario_dir.glob(f"**/{pattern}"))

        # Deduplicate and sort
        seen = set()
        unique_yaml = []
        for f in yaml_files:
            if f.resolve() not in seen:
                seen.add(f.resolve())
                unique_yaml.append(f)

        def yaml_sort_key(p):
            name = p.name.lower()
            if 'pipeline' in name or 'gitlab-ci' in name:
                return (0, name)
            elif 'deployment' in name:
                return (1, name)
            elif 'service' in name:
                return (2, name)
            else:
                return (3, name)

        unique_yaml = sorted(unique_yaml, key=yaml_sort_key)
        logger.info(f"Found {len(unique_yaml)} YAML files for GitLab CI scenario {scenario_id}")

        for yaml_file in unique_yaml:
            try:
                rel_path = yaml_file.relative_to(scenario_dir)
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    scenario_info["yaml_files"].append({
                        "name": str(rel_path),
                        "content": content
                    })
            except Exception as e:
                logger.error(f"Error reading {yaml_file.name}: {e}")
                scenario_info["yaml_files"].append({
                    "name": yaml_file.name,
                    "content": f"# Error loading file: {str(e)}"
                })

        logger.info(f"GitLab CI scenario {scenario_id}: {len(scenario_info['commands'])} commands, {len(scenario_info['yaml_files'])} YAML files")
        return scenario_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_gitlab_ci_scenario: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    global load_test_running, load_test_task
    if load_test_running:
        load_test_running = False
        if load_test_task and not load_test_task.done():
            load_test_task.cancel()
            try:
                await load_test_task
            except asyncio.CancelledError:
                pass
    logger.info("Application shutting down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)