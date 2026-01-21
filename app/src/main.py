# app/src/main.py
from database import get_db, check_db_connection, get_db_stats, User, Task, init_db
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel
import asyncio
import os
import logging
import subprocess
from datetime import datetime
from collections import deque
from pathlib import Path

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
    """Get Kubernetes cluster statistics"""
    namespace = "k8s-multi-demo"
    
    # Get pods count
    pods_output = run_kubectl_command(f"kubectl get pods -n {namespace} -o json")
    pods_count = 0
    pods_list = []
    if pods_output:
        import json
        try:
            pods_data = json.loads(pods_output)
            pods_count = len(pods_data.get('items', []))
            pods_list = [
                {
                    'name': pod['metadata']['name'],
                    'status': pod['status']['phase'],
                    'ready': sum(1 for c in pod['status'].get('containerStatuses', []) if c.get('ready', False))
                }
                for pod in pods_data.get('items', [])
            ]
        except:
            pass
    
    # Get nodes count
    nodes_output = run_kubectl_command("kubectl get nodes -o json")
    nodes_count = 0
    nodes_list = []
    if nodes_output:
        import json
        try:
            nodes_data = json.loads(nodes_output)
            nodes_count = len(nodes_data.get('items', []))
            nodes_list = [
                {
                    'name': node['metadata']['name'],
                    'status': next((c['type'] for c in node['status'].get('conditions', []) if c['status'] == 'True'), 'Unknown')
                }
                for node in nodes_data.get('items', [])
            ]
        except:
            pass
    
    # Get deployment replicas
    replicas_output = run_kubectl_command(f"kubectl get deployment k8s-demo-app -n {namespace} -o json")
    replicas_count = 0
    replicas_desired = 0
    replicas_list = []
    if replicas_output:
        import json
        try:
            deployment_data = json.loads(replicas_output)
            replicas_desired = deployment_data['spec'].get('replicas', 0)
            replicas_count = deployment_data['status'].get('readyReplicas', 0)
            
            # Get pod names for this deployment
            pods_for_deployment = run_kubectl_command(f"kubectl get pods -n {namespace} -l app=k8s-demo-app -o json")
            if pods_for_deployment:
                pods_deployment_data = json.loads(pods_for_deployment)
                replicas_list = [
                    {
                        'name': pod['metadata']['name'],
                        'status': pod['status']['phase']
                    }
                    for pod in pods_deployment_data.get('items', [])
                ]
        except:
            pass
    
    return {
        "pods": {
            "count": pods_count,
            "list": pods_list
        },
        "nodes": {
            "count": nodes_count,
            "list": nodes_list
        },
        "replicas": {
            "current": replicas_count,
            "desired": replicas_desired,
            "list": replicas_list
        }
    }

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
    
    logger.info(f"Application ready")
    logger.info(f"========================================")

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