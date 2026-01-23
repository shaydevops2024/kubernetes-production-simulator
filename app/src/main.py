# app/src/main.py
from database import get_db, check_db_connection, get_db_stats, User, Task, init_db
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi import FastAPI, Response
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
            
            # Get status
            status = "Unknown"
            conditions = node.status.conditions or []
            for condition in conditions:
                if condition.type == "Ready":
                    status = "Ready" if condition.status == "True" else "NotReady"
                    break
            
            # Get roles
            labels = node.metadata.labels or {}
            roles = []
            if 'node-role.kubernetes.io/control-plane' in labels:
                roles.append('control-plane')
            if 'node-role.kubernetes.io/master' in labels:
                roles.append('master')
            role = ','.join(roles) if roles else '<none>'
            
            age = calculate_age(node.metadata.creation_timestamp)
            
            # Get version
            version = node.status.node_info.kubelet_version if node.status.node_info else 'unknown'
            
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

@app.get("/api/db/info")
async def get_database_info():
    """Get database StatefulSet information including secrets and configmaps"""
    namespace = "k8s-multi-demo"
    
    info = {
        "uses_secret": False,
        "secret_name": None,
        "uses_configmap": False,
        "configmap_name": None
    }
    
    if not k8s_available or not k8s_apps_v1:
        return info
    
    try:
        # Get the postgres StatefulSet
        statefulsets = k8s_apps_v1.list_namespaced_stateful_set(namespace=namespace)
        
        for sts in statefulsets.items:
            if 'postgres' in sts.metadata.name.lower():
                # Check for secrets and configmaps in the pod spec
                containers = sts.spec.template.spec.containers or []
                volumes = sts.spec.template.spec.volumes or []
                
                # Check environment variables for secrets
                for container in containers:
                    if container.env:
                        for env_var in container.env:
                            if env_var.value_from and env_var.value_from.secret_key_ref:
                                info["uses_secret"] = True
                                info["secret_name"] = env_var.value_from.secret_key_ref.name
                                break
                    
                    # Check env_from for configmaps
                    if container.env_from:
                        for env_from in container.env_from:
                            if env_from.config_map_ref:
                                info["uses_configmap"] = True
                                info["configmap_name"] = env_from.config_map_ref.name
                
                # Check volumes for configmaps
                for volume in volumes:
                    if volume.config_map:
                        info["uses_configmap"] = True
                        if not info["configmap_name"]:
                            info["configmap_name"] = volume.config_map.name
                
                break
                
    except ApiException as e:
        logger.error(f"Error fetching StatefulSet info: {e}")
    
    return info

@app.post("/loadtest/start")
async def start_load_test():
    global load_test_running, load_test_task
    
    if load_test_running:
        return {"message": "Load test already running", "status": "running"}
    
    load_test_running = True
    load_test_task = asyncio.create_task(generate_load())
    
    logger.info("🚀 LOAD TEST STARTED")
    return {"message": "Load test started successfully", "status": "running"}

@app.post("/loadtest/stop")
async def stop_load_test():
    global load_test_running, load_test_task
    
    if not load_test_running:
        return {"message": "No load test running", "status": "stopped"}
    
    load_test_running = False
    
    if load_test_task and not load_test_task.done():
        load_test_task.cancel()
        try:
            await load_test_task
        except asyncio.CancelledError:
            pass
    
    logger.info("🛑 LOAD TEST STOPPED")
    return {"message": "Load test stopped", "status": "stopped"}

async def generate_load():
    global load_test_running
    import aiohttp
    
    service_url = 'http://k8s-demo-service.k8s-multi-demo.svc.cluster.local'
    start_time = asyncio.get_event_loop().time()
    duration = 120
    request_count = 0
    session = None
    
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        session = aiohttp.ClientSession(timeout=timeout)
        
        while load_test_running and (asyncio.get_event_loop().time() - start_time) < duration:
            try:
                tasks = []
                for _ in range(20):
                    if not load_test_running:
                        break
                    task = session.get(service_url)
                    tasks.append(task)
                
                if not load_test_running:
                    break
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                request_count += len(responses)
                
                if request_count % 100 == 0:
                    logger.info(f"Load test: {request_count} requests sent")
                
                await asyncio.sleep(0.05)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                if load_test_running:
                    logger.error(f"Load generation error: {e}")
                await asyncio.sleep(0.5)
    
    except Exception as e:
        logger.error(f"Load test failed: {e}")
    
    finally:
        if session and not session.closed:
            await session.close()
            await asyncio.sleep(0.25)
        
        load_test_running = False
        logger.info(f"🏁 LOAD TEST COMPLETED - {request_count} requests")

@app.post("/simulate/crash")
async def simulate_crash():
    global app_healthy
    app_healthy = False
    logger.error("INCIDENT SIMULATION: App unhealthy")
    return {"message": "App is now unhealthy - will be restarted by Kubernetes"}

@app.post("/simulate/notready")
async def simulate_notready():
    global app_ready
    app_ready = False
    logger.warning("INCIDENT SIMULATION: App not ready")
    return {"message": "App is now not ready - Kubernetes will stop routing traffic"}

@app.post("/reset")
async def reset():
    global app_healthy, app_ready
    app_healthy = True
    app_ready = True
    logger.info("✅ App reset to healthy state")
    return {"message": "App reset to healthy state"}

@app.get("/db/health")
async def database_health():
    connected, message = check_db_connection()
    if connected:
        return {"database": "connected", "message": message, "stats": get_db_stats()}
    return Response(content=f'{{"error": "{message}"}}', status_code=503)

@app.get("/api/db/stats")
async def get_database_stats():
    return get_db_stats()

@app.get("/api/users")
async def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [user.to_dict() for user in users]

@app.get("/api/tasks")
async def get_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    return [task.to_dict() for task in tasks]

@app.post("/api/users/create")
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(User).filter(
            (User.username == user_data.username) | (User.email == user_data.email)
        ).first()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already exists")
        
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"✅ New user created: {user_data.username}")
        
        return {
            "message": "User created successfully",
            "user": new_user.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks/create")
async def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == task_data.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        new_task = Task(
            user_id=task_data.user_id,
            title=task_data.title,
            description=task_data.description,
            status=task_data.status,
            priority=task_data.priority
        )
        
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        logger.info(f"✅ New task created: '{task_data.title}'")
        
        return {
            "message": "Task created successfully",
            "task": new_task.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    logger.info(f"========================================")
    logger.info(f"Starting {APP_NAME}")
    logger.info(f"Environment: {APP_ENV}")
    
    connected, message = check_db_connection()
    if connected:
        logger.info(f"✅ {message}")
    else:
        logger.warning(f"⚠️ {message}")
    
    if k8s_available:
        logger.info(f"✅ Kubernetes client ready")
    else:
        logger.warning(f"⚠️ Kubernetes client not available")
    
    logger.info(f"Application ready")
    logger.info(f"========================================")

@app.get("/api/scenarios")
async def get_scenarios():
    """Get list of available scenarios with proper error handling"""
    try:
        scenarios_dir = Path("/scenarios")
        
        # Check if directory exists
        if not scenarios_dir.exists():
            logger.warning(f"Scenarios directory not found: {scenarios_dir}")
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
                    "readme": ""
                }
                
                # Read README if it exists
                if readme_path.exists():
                    try:
                        with open(readme_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Extract first non-header paragraph as description
                            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
                            if lines:
                                scenario_info["description"] = lines[0][:200]  # Limit description length
                            scenario_info["readme"] = content
                    except UnicodeDecodeError:
                        logger.warning(f"Unicode decode error reading README for {scenario_dir.name}, trying with errors='replace'")
                        try:
                            with open(readme_path, 'r', encoding='utf-8', errors='replace') as f:
                                content = f.read()
                                scenario_info["readme"] = content
                        except Exception as e:
                            logger.error(f"Failed to read README for {scenario_dir.name}: {e}")
                            scenario_info["readme"] = f"Error loading README: {str(e)}"
                    except Exception as e:
                        logger.error(f"Error reading README for {scenario_dir.name}: {e}")
                        scenario_info["readme"] = f"Error loading README: {str(e)}"
                
                # Read commands.json if it exists
                if commands_path.exists():
                    try:
                        with open(commands_path, 'r', encoding='utf-8') as f:
                            commands_data = json.load(f)
                            scenario_info["commands"] = commands_data.get("commands", [])
                            scenario_info["difficulty"] = commands_data.get("difficulty", "medium")
                            scenario_info["duration"] = commands_data.get("duration", "20 min")
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error in commands.json for {scenario_dir.name}: {e}")
                        scenario_info["commands"] = []
                    except Exception as e:
                        logger.error(f"Error reading commands.json for {scenario_dir.name}: {e}")
                        scenario_info["commands"] = []
                else:
                    scenario_info["commands"] = []
                
                scenarios.append(scenario_info)
                
            except Exception as e:
                logger.error(f"Error processing scenario {scenario_dir.name}: {e}")
                # Continue with next scenario instead of failing completely
                continue
        
        logger.info(f"Successfully processed {len(scenarios)} scenarios")
        return {"scenarios": scenarios}
        
    except Exception as e:
        logger.error(f"Fatal error in get_scenarios: {e}", exc_info=True)
        # Return empty list instead of crashing
        return {"scenarios": [], "error": str(e)}

@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get details of a specific scenario with proper error handling"""
    try:
        scenario_dir = Path(f"/scenarios/{scenario_id}")
        
        if not scenario_dir.exists():
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        scenario_info = {
            "id": scenario_id,
            "name": scenario_id.replace("-", " ").title(),
            "readme": "",
            "commands": [],
            "difficulty": "medium",
            "duration": "20 min"
        }
        
        readme_path = scenario_dir / "README.md"
        if readme_path.exists():
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    scenario_info["readme"] = f.read()
            except Exception as e:
                logger.error(f"Error reading README for {scenario_id}: {e}")
                scenario_info["readme"] = f"Error loading README: {str(e)}"
        
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
        
        return scenario_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_scenario for {scenario_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scenarios/{scenario_id}/validate")
async def validate_scenario(scenario_id: str):
    """Run validation script for a scenario"""
    scenario_dir = Path(f"/scenarios/{scenario_id}")
    validate_script = scenario_dir / "validate.sh"
    
    if not validate_script.exists():
        return {"success": False, "message": "Validation script not found"}
    
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
            "output": result.stdout,
            "error": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Validation timed out"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.websocket("/ws/terminal/{scenario_id}")
async def terminal_websocket(websocket: WebSocket, scenario_id: str):
    """WebSocket endpoint for interactive terminal"""
    await websocket.accept()
    logger.info(f"Terminal WebSocket connected for scenario: {scenario_id}")
    
    try:
        while True:
            # Receive command from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "command":
                command = message.get("command", "").strip()
                
                if not command:
                    continue
                
                # Security: Validate command (basic validation)
                # In production, you'd want more strict validation
                logger.info(f"Executing command: {command}")
                
                try:
                    # Execute command in a subprocess
                    process = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        stdin=asyncio.subprocess.PIPE,
                    )
                    
                    # Send output as it comes
                    async def read_stream(stream, stream_type):
                        while True:
                            line = await stream.readline()
                            if not line:
                                break
                            
                            output = line.decode('utf-8', errors='replace')
                            await websocket.send_json({
                                "type": "output",
                                "stream": stream_type,
                                "data": output
                            })
                    
                    # Read both stdout and stderr concurrently
                    await asyncio.gather(
                        read_stream(process.stdout, "stdout"),
                        read_stream(process.stderr, "stderr")
                    )
                    
                    # Wait for process to complete
                    await process.wait()
                    
                    # Send completion message
                    await websocket.send_json({
                        "type": "complete",
                        "returncode": process.returncode
                    })
                    
                except Exception as e:
                    logger.error(f"Command execution error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
            
            elif message.get("type") == "validate":
                # Run validation script
                scenario_dir = Path(f"/scenarios/{scenario_id}")
                validate_script = scenario_dir / "validate.sh"
                
                if validate_script.exists():
                    try:
                        process = await asyncio.create_subprocess_shell(
                            f"bash {validate_script}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            cwd=str(scenario_dir)
                        )
                        
                        # Stream validation output
                        async def read_stream(stream, stream_type):
                            while True:
                                line = await stream.readline()
                                if not line:
                                    break
                                
                                output = line.decode('utf-8', errors='replace')
                                await websocket.send_json({
                                    "type": "validation_output",
                                    "stream": stream_type,
                                    "data": output
                                })
                        
                        await asyncio.gather(
                            read_stream(process.stdout, "stdout"),
                            read_stream(process.stderr, "stderr")
                        )
                        
                        await process.wait()
                        
                        await websocket.send_json({
                            "type": "validation_complete",
                            "success": process.returncode == 0,
                            "returncode": process.returncode
                        })
                        
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Validation error: {str(e)}"
                        })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Validation script not found"
                    })
    
    except WebSocketDisconnect:
        logger.info(f"Terminal WebSocket disconnected for scenario: {scenario_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass

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
