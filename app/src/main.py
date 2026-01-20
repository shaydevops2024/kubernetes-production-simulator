# app/src/main.py
# Main FastAPI application with production-ready endpoints and web UI

from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, generate_latest
import time
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="K8s Production Demo", version="1.0.0")

# Prometheus metrics
REQUEST_COUNT = Counter('app_requests_total', 'Total app requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('app_request_duration_seconds', 'Request duration')

# Application state
app_ready = True
app_healthy = True

# Read configuration from environment
APP_ENV = os.getenv('APP_ENV', 'development')
APP_NAME = os.getenv('APP_NAME', 'k8s-demo-app')
SECRET_TOKEN = os.getenv('SECRET_TOKEN', 'no-secret-configured')

# Serve the UI at root
@app.get("/", response_class=HTMLResponse)
async def ui():
    """
    Serve a simple web UI dashboard
    This makes the app more visual and professional
    """
    REQUEST_COUNT.labels(method='GET', endpoint='/').inc()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>K8s Production Demo</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 800px;
                width: 100%;
                padding: 40px;
            }
            
            .header {
                text-align: center;
                margin-bottom: 40px;
            }
            
            .header h1 {
                color: #333;
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            .header .subtitle {
                color: #666;
                font-size: 1.1em;
            }
            
            .status-card {
                background: #f8f9fa;
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 20px;
            }
            
            .status-item {
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #e0e0e0;
            }
            
            .status-item:last-child {
                border-bottom: none;
            }
            
            .label {
                font-weight: 600;
                color: #555;
            }
            
            .value {
                color: #333;
                font-family: 'Courier New', monospace;
            }
            
            .badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 0.85em;
                font-weight: 600;
            }
            
            .badge-success {
                background: #d4edda;
                color: #155724;
            }
            
            .badge-danger {
                background: #f8d7da;
                color: #721c24;
            }
            
            .badge-info {
                background: #d1ecf1;
                color: #0c5460;
            }
            
            .actions {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 30px;
            }
            
            .btn {
                padding: 15px 20px;
                border: none;
                border-radius: 8px;
                font-size: 1em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                text-decoration: none;
                display: inline-block;
                text-align: center;
            }
            
            .btn-primary {
                background: #667eea;
                color: white;
            }
            
            .btn-primary:hover {
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            
            .btn-success {
                background: #48bb78;
                color: white;
            }
            
            .btn-success:hover {
                background: #38a169;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(72, 187, 120, 0.4);
            }
            
            .btn-danger {
                background: #f56565;
                color: white;
            }
            
            .btn-danger:hover {
                background: #e53e3e;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(245, 101, 101, 0.4);
            }
            
            .btn-warning {
                background: #ed8936;
                color: white;
            }
            
            .btn-warning:hover {
                background: #dd6b20;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(237, 137, 54, 0.4);
            }
            
            .footer {
                text-align: center;
                margin-top: 30px;
                color: #999;
                font-size: 0.9em;
            }
            
            .live-indicator {
                display: inline-block;
                width: 10px;
                height: 10px;
                background: #48bb78;
                border-radius: 50%;
                margin-right: 8px;
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            .section-title {
                font-size: 1.2em;
                color: #333;
                margin: 30px 0 15px 0;
                font-weight: 600;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Kubernetes Production Demo</h1>
                <p class="subtitle">
                    <span class="live-indicator"></span>
                    Application Running
                </p>
            </div>
            
            <div class="status-card">
                <div class="status-item">
                    <span class="label">Application Name:</span>
                    <span class="value" id="app-name">Loading...</span>
                </div>
                <div class="status-item">
                    <span class="label">Environment:</span>
                    <span class="value" id="environment">Loading...</span>
                </div>
                <div class="status-item">
                    <span class="label">Health Status:</span>
                    <span class="value" id="health-status">
                        <span class="badge badge-success">Checking...</span>
                    </span>
                </div>
                <div class="status-item">
                    <span class="label">Readiness Status:</span>
                    <span class="value" id="ready-status">
                        <span class="badge badge-success">Checking...</span>
                    </span>
                </div>
                <div class="status-item">
                    <span class="label">Secret Configured:</span>
                    <span class="value" id="secret-status">Loading...</span>
                </div>
            </div>
            
            <div class="section-title">📊 Quick Actions</div>
            
            <div class="actions">
                <a href="/docs" class="btn btn-primary" target="_blank">
                    📖 API Documentation
                </a>
                <a href="/metrics" class="btn btn-success" target="_blank">
                    📈 Prometheus Metrics
                </a>
                <button class="btn btn-warning" onclick="simulateNotReady()">
                    ⚠️ Simulate Not Ready
                </button>
                <button class="btn btn-danger" onclick="simulateCrash()">
                    💥 Simulate Crash
                </button>
                <button class="btn btn-success" onclick="resetApp()">
                    🔄 Reset to Healthy
                </button>
            </div>
            
            <div class="footer">
                Built for Kubernetes Production Learning | 
                <a href="https://github.com/shaydevops2024/kubernetes-production-simulator" target="_blank" style="color: #667eea;">View on GitHub</a>
            </div>
        </div>
        
        <script>
            // Fetch and display application status
            async function updateStatus() {
                try {
                    // Get config
                    const configRes = await fetch('/api/info');
                    const config = await configRes.json();
                    
                    document.getElementById('app-name').textContent = config.app_name;
                    document.getElementById('environment').innerHTML = 
                        `<span class="badge badge-info">${config.environment}</span>`;
                    document.getElementById('secret-status').textContent = config.secret_configured;
                    
                    // Check health
                    const healthRes = await fetch('/health');
                    const healthBadge = healthRes.ok ? 
                        '<span class="badge badge-success">✓ Healthy</span>' : 
                        '<span class="badge badge-danger">✗ Unhealthy</span>';
                    document.getElementById('health-status').innerHTML = healthBadge;
                    
                    // Check readiness
                    const readyRes = await fetch('/ready');
                    const readyBadge = readyRes.ok ? 
                        '<span class="badge badge-success">✓ Ready</span>' : 
                        '<span class="badge badge-danger">✗ Not Ready</span>';
                    document.getElementById('ready-status').innerHTML = readyBadge;
                    
                } catch (error) {
                    console.error('Error updating status:', error);
                }
            }
            
            async function simulateCrash() {
                if (confirm('This will make the app unhealthy. Kubernetes will restart the pod. Continue?')) {
                    await fetch('/simulate/crash', { method: 'POST' });
                    alert('App is now unhealthy! Watch Kubernetes restart the pod.');
                    setTimeout(updateStatus, 1000);
                }
            }
            
            async function simulateNotReady() {
                if (confirm('This will make the app not ready. Kubernetes will stop routing traffic. Continue?')) {
                    await fetch('/simulate/notready', { method: 'POST' });
                    alert('App is now not ready! Kubernetes will stop sending traffic.');
                    setTimeout(updateStatus, 1000);
                }
            }
            
            async function resetApp() {
                await fetch('/reset', { method: 'POST' });
                alert('App reset to healthy state!');
                setTimeout(updateStatus, 1000);
            }
            
            // Update status every 3 seconds
            updateStatus();
            setInterval(updateStatus, 3000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/info")
async def api_info():
    """API endpoint for the UI to fetch status"""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/info').inc()
    return {
        "app_name": APP_NAME,
        "environment": APP_ENV,
        "secret_configured": "yes" if SECRET_TOKEN != "no-secret-configured" else "no",
        "status": "running"
    }

@app.get("/health")
async def health():
    """
    Liveness probe endpoint
    Kubernetes uses this to know if the pod is alive
    If this fails, Kubernetes will restart the pod
    """
    REQUEST_COUNT.labels(method='GET', endpoint='/health').inc()
    
    if app_healthy:
        return {"status": "healthy"}
    else:
        return Response(content='{"status": "unhealthy"}', status_code=500)

@app.get("/ready")
async def ready():
    """
    Readiness probe endpoint
    Kubernetes uses this to know if the pod can receive traffic
    If this fails, Kubernetes stops sending traffic to this pod
    """
    REQUEST_COUNT.labels(method='GET', endpoint='/ready').inc()
    
    if app_ready:
        return {"status": "ready"}
    else:
        return Response(content='{"status": "not ready"}', status_code=503)

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    Exposes application metrics in Prometheus format
    """
    return Response(content=generate_latest(), media_type="text/plain")

@app.post("/simulate/crash")
async def simulate_crash():
    """
    Simulate app becoming unhealthy (for testing liveness probe)
    This is for incident simulation in Stage 7
    """
    global app_healthy
    app_healthy = False
    logger.error("App health set to unhealthy - liveness probe will fail!")
    return {"message": "App is now unhealthy - will be restarted by Kubernetes"}

@app.post("/simulate/notready")
async def simulate_notready():
    """
    Simulate app becoming not ready (for testing readiness probe)
    This is for incident simulation in Stage 7
    """
    global app_ready
    app_ready = False
    logger.warning("App readiness set to false - will stop receiving traffic!")
    return {"message": "App is now not ready - Kubernetes will stop routing traffic"}

@app.post("/reset")
async def reset():
    """Reset app to healthy state"""
    global app_healthy, app_ready
    app_healthy = True
    app_ready = True
    logger.info("App reset to healthy and ready state")
    return {"message": "App reset to healthy state"}

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {APP_NAME} in {APP_ENV} environment")
    logger.info("Application ready to accept requests")

if __name__ == "__main__":
    import uvicorn
    # Run the app on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
