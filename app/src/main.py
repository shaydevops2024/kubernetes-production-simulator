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

@app.get("/metrics")
async def metrics():
    REQUEST_COUNT.labels(method='GET', endpoint='/metrics').inc()
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/logs")
async def get_logs():
    return {"logs": list(log_buffer)}

@app.get("/api/config")
async def get_config():
    return {
        "app_env": APP_ENV,
        "app_name": APP_NAME,
        "secret_configured": SECRET_TOKEN != "no-secret-configured"
    }

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

# Database endpoints (unchanged)
@app.post("/api/database/init")
async def initialize_database(db: Session = Depends(get_db)):
    try:
        init_db()
        return {"message": "Database initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/status")
async def database_status(db: Session = Depends(get_db)):
    try:
        is_connected = check_db_connection(db)
        stats = get_db_stats(db) if is_connected else {}
        return {"connected": is_connected, "stats": stats}
    except Exception as e:
        logger.error(f"Database status check error: {e}")
        return {"connected": False, "error": str(e)}

@app.post("/api/users")
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        db_user = User(username=user.username, email=user.email, full_name=user.full_name)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return {"id": str(db_user.id), "username": db_user.username, "email": db_user.email, "full_name": db_user.full_name, "created_at": db_user.created_at.isoformat()}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users")
async def list_users(db: Session = Depends(get_db)):
    try:
        users = db.query(User).all()
        return {"users": [{"id": str(user.id), "username": user.username, "email": user.email, "full_name": user.full_name, "created_at": user.created_at.isoformat()} for user in users]}
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
        return {"id": str(db_task.id), "user_id": str(db_task.user_id), "title": db_task.title, "description": db_task.description, "status": db_task.status, "priority": db_task.priority, "created_at": db_task.created_at.isoformat()}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks")
async def list_tasks(db: Session = Depends(get_db)):
    try:
        tasks = db.query(Task).all()
        return {"tasks": [{"id": str(task.id), "user_id": str(task.user_id), "title": task.title, "description": task.description, "status": task.status, "priority": task.priority, "created_at": task.created_at.isoformat()} for task in tasks]}
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