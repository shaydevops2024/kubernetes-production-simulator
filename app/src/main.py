# app/src/main.py
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
import shlex

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

def run_kubectl_command(command):
    """Execute kubectl command and return output"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return None
    except Exception as e:
        logger.error(f"Kubectl command failed: {e}")
        return None

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
    """Serve the main HTML page"""
    return FileResponse(str(static_dir / "index.html"))

@app.get("/scenarios")
async def scenarios_page():
    """Serve the scenarios list page"""
    return FileResponse(str(static_dir / "scenarios.html"))

@app.get("/scenario/{scenario_id}")
async def scenario_detail_page(scenario_id: str):
    """Serve the scenario detail page"""
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
    """Get application configuration"""
    return {
        "app_env": APP_ENV,
        "app_name": APP_NAME,
        "secret_configured": SECRET_TOKEN != "no-secret-configured"
    }

@app.get("/api/cluster/stats")
async def get_cluster_stats():
    """Get Kubernetes cluster statistics with detailed kubectl-style output"""
    namespace = "k8s-multi-demo"
    
    if not k8s_available or not k8s_apps_v1 or not k8s_core_v1:
        return {
            "deployments": {"count": 0, "details": []},
            "pods": {"count": 0, "details": []},
            "nodes": {"count": 0, "details": []}
        }
    
    deployments_info = {"count": 0, "details": []}
    pods_info = {"count": 0, "details": []}
    nodes_info = {"count": 0, "details": []}
    
    # Get deployments
    try:
        deployments = k8s_apps_v1.list_namespaced_deployment(namespace=namespace)
        deployments_info["count"] = len(deployments.items)
        
        for deployment in deployments.items:
            name = deployment.metadata.name
            spec_replicas = deployment.spec.replicas or 0
            ready_replicas = deployment.status.ready_replicas or 0
            updated_replicas = deployment.status.updated_replicas or 0
            available_replicas = deployment.status.available_replicas or 0
            age = calculate_age(deployment.metadata.creation_timestamp)
            
            deployments_info["details"].append({
                "name": name,
                "ready": f"{ready_replicas}/{spec_replicas}",
                "up_to_date": updated_replicas,
                "available": available_replicas,
                "age": age
            })
    except ApiException as e:
        logger.error(f"Error fetching deployments: {e}")
    
    # Get pods
    try:
        pods = k8s_core_v1.list_namespaced_pod(namespace=namespace)
        pods_info["count"] = len(pods.items)
        
        for pod in pods.items:
            name = pod.metadata.name
            status = pod.status.phase or "Unknown"
            
            # Calculate ready containers
            container_statuses = pod.status.container_statuses or []
            ready_count = sum(1 for c in container_statuses if c.ready)
            total_count = len(container_statuses)
            ready = f"{ready_count}/{total_count}"
            
            # Get restarts
            restarts = sum(c.restart_count for c in container_statuses)
            
            age = calculate_age(pod.metadata.creation_timestamp)
            
            pods_info["details"].append({
                "name": name,
                "ready": ready,
                "status": status,
                "restarts": restarts,
                "age": age
            })
    except ApiException as e:
        logger.error(f"Error fetching pods: {e}")
    
    # Get nodes
    try:
        nodes = k8s_core_v1.list_node()
        nodes_info["count"] = len(nodes.items)
        
        for node in nodes.items:
            name = node.metadata.name
            
            # Get node status
            conditions = node.status.conditions or []
            ready_condition = next((c for c in conditions if c.type == "Ready"), None)
            status = "Ready" if ready_condition and ready_condition.status == "True" else "NotReady"
            
            # Get roles
            labels = node.metadata.labels or {}
            roles = []
            if "node-role.kubernetes.io/control-plane" in labels or "node-role.kubernetes.io/master" in labels:
                roles.append("control-plane")
            if "node-role.kubernetes.io/worker" in labels:
                roles.append("worker")
            role = ",".join(roles) if roles else "worker"
            
            age = calculate_age(node.metadata.creation_timestamp)
            
            # Get version
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
        "nodes": nodes_info
    }

@app.post("/api/database/init")
async def initialize_database(db: Session = Depends(get_db)):
    """Initialize database with schema"""
    try:
        init_db()
        return {"message": "Database initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/status")
async def database_status(db: Session = Depends(get_db)):
    """Check database connection status"""
    try:
        is_connected = check_db_connection(db)
        stats = get_db_stats(db) if is_connected else {}
        
        return {
            "connected": is_connected,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Database status check error: {e}")
        return {
            "connected": False,
            "error": str(e)
        }

@app.post("/api/users")
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    try:
        db_user = User(
            username=user.username,
            email=user.email,
            full_name=user.full_name
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return {
            "id": str(db_user.id),
            "username": db_user.username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "created_at": db_user.created_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users")
async def list_users(db: Session = Depends(get_db)):
    """List all users"""
    try:
        users = db.query(User).all()
        return {
            "users": [
                {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "created_at": user.created_at.isoformat()
                }
                for user in users
            ]
        }
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks")
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    """Create a new task"""
    try:
        db_task = Task(
            user_id=task.user_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        
        return {
            "id": str(db_task.id),
            "user_id": str(db_task.user_id),
            "title": db_task.title,
            "description": db_task.description,
            "status": db_task.status,
            "priority": db_task.priority,
            "created_at": db_task.created_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks")
async def list_tasks(db: Session = Depends(get_db)):
    """List all tasks"""
    try:
        tasks = db.query(Task).all()
        return {
            "tasks": [
                {
                    "id": str(task.id),
                    "user_id": str(task.user_id),
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "created_at": task.created_at.isoformat()
                }
                for task in tasks
            ]
        }
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/load-test/start")
async def start_load_test():
    """Start load testing"""
    global load_test_running, load_test_task
    
    if load_test_running:
        return {"message": "Load test already running"}
    
    async def generate_load():
        global load_test_running
        logger.info("Load test started")
        
        while load_test_running:
            try:
                # Simulate some CPU load
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
    """Stop load testing"""
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
    """Get load test status"""
    return {
        "running": load_test_running,
        "status": "running" if load_test_running else "stopped"
    }

@app.get("/api/scenarios")
async def get_scenarios():
    """Get list of all available scenarios with enhanced metadata"""
    try:
        scenarios_dir = Path("/scenarios")
        
        if not scenarios_dir.exists():
            logger.warning(f"Scenarios directory does not exist: {scenarios_dir}")
            return {"scenarios": []}
        
        if not scenarios_dir.is_dir():
            logger.error(f"Scenarios path exists but is not a directory: {scenarios_dir}")
            return {"scenarios": []}
        
        scenarios = []
        
        # Get list of scenario directories
        try:
            scenario_dirs = sorted([d for d in scenarios_dir.iterdir() if d.is_dir()])
        except Exception as e:
            logger.error(f"Error listing scenarios directory: {e}")
            return {"scenarios": []}
        
        logger.info(f"Found {len(scenario_dirs)} scenario directories")
        
        # Process each scenario directory
        for scenario_dir in scenario_dirs:
            try:
                readme_path = scenario_dir / "README.md"
                commands_path = scenario_dir / "commands.json"
                
                # Basic scenario info
                scenario_info = {
                    "id": scenario_dir.name,
                    "name": scenario_dir.name.replace("-", " ").title(),
                    "description": "No description available",
                    "difficulty": "medium",
                    "duration": "20 min",
                    "special": "special" in scenario_dir.name.lower(),
                    "readme": "",
                    "command_count": 0
                }
                
                # Read README if it exists
                if readme_path.exists():
                    try:
                        with open(readme_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Extract first non-header paragraph as description
                            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
                            if lines:
                                scenario_info["description"] = lines[0][:200]
                            scenario_info["readme"] = content
                    except Exception as e:
                        logger.error(f"Error reading README for {scenario_dir.name}: {e}")
                        scenario_info["readme"] = f"Error loading README: {str(e)}"
                
                # Read commands.json if it exists
                if commands_path.exists():
                    try:
                        with open(commands_path, 'r', encoding='utf-8') as f:
                            commands_data = json.load(f)
                            scenario_info["command_count"] = len(commands_data.get("commands", []))
                            scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                            scenario_info["duration"] = commands_data.get("duration", "20 min")
                    except Exception as e:
                        logger.error(f"Error reading commands.json for {scenario_dir.name}: {e}")
                
                scenarios.append(scenario_info)
                
            except Exception as e:
                logger.error(f"Error processing scenario {scenario_dir.name}: {e}")
                continue
        
        logger.info(f"Successfully processed {len(scenarios)} scenarios")
        return {"scenarios": scenarios}
        
    except Exception as e:
        logger.error(f"Fatal error in get_scenarios: {e}", exc_info=True)
        return {"scenarios": [], "error": str(e)}

@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get detailed information about a specific scenario including YAML files"""
    try:
        scenario_dir = Path(f"/scenarios/{scenario_id}")
        
        if not scenario_dir.exists():
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        scenario_info = {
            "id": scenario_id,
            "name": scenario_id.replace("-", " ").title(),
            "readme": "",
            "commands": [],
            "yaml_files": [],
            "difficulty": "medium",
            "duration": "20 min"
        }
        
        # Read README
        readme_path = scenario_dir / "README.md"
        if readme_path.exists():
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    scenario_info["readme"] = f.read()
            except Exception as e:
                logger.error(f"Error reading README for {scenario_id}: {e}")
                scenario_info["readme"] = f"Error loading README: {str(e)}"
        
        # Read commands.json
        commands_path = scenario_dir / "commands.json"
        if commands_path.exists():
            try:
                with open(commands_path, 'r', encoding='utf-8') as f:
                    commands_data = json.load(f)
                    scenario_info["commands"] = commands_data.get("commands", [])
                    scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                    scenario_info["duration"] = commands_data.get("duration", "20 min")
            except Exception as e:
                logger.error(f"Error reading commands.json for {scenario_id}: {e}")
                scenario_info["commands"] = []
        
        # Find all YAML files in the scenario directory
        try:
            yaml_files = list(scenario_dir.glob("*.yaml")) + list(scenario_dir.glob("*.yml"))
            for yaml_file in yaml_files:
                try:
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        scenario_info["yaml_files"].append({
                            "name": yaml_file.name,
                            "content": content
                        })
                except Exception as e:
                    logger.error(f"Error reading YAML file {yaml_file.name}: {e}")
        except Exception as e:
            logger.error(f"Error finding YAML files for {scenario_id}: {e}")
        
        return scenario_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_scenario: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scenarios/{scenario_id}/validate")
async def validate_scenario(scenario_id: str):
    """Run validation script for a scenario"""
    try:
        logger.info(f"Validating scenario: {scenario_id}")
        
        scenario_dir = Path(f"/scenarios/{scenario_id}")
        validate_script = scenario_dir / "validate.sh"
        
        if not validate_script.exists():
            return {
                "success": False,
                "message": "No validation script found for this scenario",
                "output": "",
                "error": ""
            }
        
        try:
            result = subprocess.run(
                ["bash", str(validate_script)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(scenario_dir)
            )
            
            return {
                "success": result.returncode == 0,
                "message": "Validation completed successfully" if result.returncode == 0 else "Validation completed with failures",
                "output": result.stdout,
                "error": result.stderr,
                "returncode": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "Validation timed out after 60 seconds",
                "output": "",
                "error": "Timeout expired"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Validation error: {str(e)}",
                "output": "",
                "error": str(e)
            }
            
    except Exception as e:
        logger.error(f"Error in validate_scenario: {e}")
        return {
            "success": False,
            "message": f"Server error: {str(e)}",
            "output": "",
            "error": str(e)
        }

@app.post("/api/scenarios/{scenario_id}/reset")
async def reset_scenario(scenario_id: str):
    """Reset a scenario by cleaning up resources"""
    try:
        logger.info(f"Resetting scenario: {scenario_id}")
        
        scenario_dir = Path(f"/scenarios/{scenario_id}")
        cleanup_script = scenario_dir / "cleanup.sh"
        
        if not cleanup_script.exists():
            # If no cleanup script, try to provide generic cleanup based on scenario
            return {
                "success": False,
                "message": "No cleanup script found. Please manually clean up resources.",
                "output": "",
                "error": ""
            }
        
        try:
            result = subprocess.run(
                ["bash", str(cleanup_script)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(scenario_dir)
            )
            
            return {
                "success": result.returncode == 0,
                "message": "Scenario reset successfully" if result.returncode == 0 else "Reset completed with warnings",
                "output": result.stdout,
                "error": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "Reset timed out after 60 seconds",
                "output": "",
                "error": "Timeout expired"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Reset error: {str(e)}",
                "output": "",
                "error": str(e)
            }
            
    except Exception as e:
        logger.error(f"Error resetting scenario: {e}")
        return {
            "success": False,
            "message": f"Reset error: {str(e)}",
            "output": "",
            "error": str(e)
        }

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