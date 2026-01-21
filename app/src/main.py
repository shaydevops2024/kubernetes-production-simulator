# app/src/main.py
# Main FastAPI application with production-ready endpoints and web UI
# COMPLETE VERSION: With Destroy All functionality, proper cleanup, auto-scroll logs
from database import get_db, check_db_connection, get_db_stats, User, Task
from sqlalchemy.orm import Session
from fastapi import Depends
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from prometheus_client import Counter, Histogram, generate_latest
import asyncio
import os
import logging
from datetime import datetime
from collections import deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="K8s Production Demo", version="1.0.0")

# Prometheus metrics
REQUEST_COUNT = Counter('app_requests_total', 'Total app requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('app_request_duration_seconds', 'Request duration')

# Application state
app_ready = True
app_healthy = True
load_test_running = False
load_test_task = None

# Log storage (last 100 log entries)
log_buffer = deque(maxlen=100)

# Custom log handler to capture logs
class LogBufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_buffer.append({
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'message': log_entry
        })

# Add handler to logger
buffer_handler = LogBufferHandler()
buffer_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(buffer_handler)

# Read configuration from environment
APP_ENV = os.getenv('APP_ENV', 'development')
APP_NAME = os.getenv('APP_NAME', 'k8s-demo-app')
SECRET_TOKEN = os.getenv('SECRET_TOKEN', 'no-secret-configured')

@app.get("/", response_class=HTMLResponse)
async def ui():
    """
    Serve a professional web UI dashboard
    Features: Status monitoring, load testing, incident simulation, live logs, CLI commands, destroy cluster
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
                max-width: 900px;
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
            
            .badge-warning {
                background: #fff3cd;
                color: #856404;
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
            
            .btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            
            .btn-primary {
                background: #667eea;
                color: white;
            }
            
            .btn-primary:hover:not(:disabled) {
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            
            .btn-success {
                background: #48bb78;
                color: white;
            }
            
            .btn-success:hover:not(:disabled) {
                background: #38a169;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(72, 187, 120, 0.4);
            }
            
            .btn-danger {
                background: #f56565;
                color: white;
            }
            
            .btn-danger:hover:not(:disabled) {
                background: #e53e3e;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(245, 101, 101, 0.4);
            }
            
            .btn-warning {
                background: #ed8936;
                color: white;
            }
            
            .btn-warning:hover:not(:disabled) {
                background: #dd6b20;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(237, 137, 54, 0.4);
            }
            
            .btn-destroy {
                background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
                color: white;
                border: 2px solid #dc2626;
                font-weight: 700;
                box-shadow: 0 4px 6px rgba(220, 38, 38, 0.3);
            }
            
            .btn-destroy:hover:not(:disabled) {
                background: linear-gradient(135deg, #991b1b 0%, #7f1d1d 100%);
                transform: translateY(-2px);
                box-shadow: 0 8px 16px rgba(220, 38, 38, 0.4);
            }
            
            .footer {
                text-align: center;
                margin-top: 30px;
                color: #999;
                font-size: 0.9em;
            }
            
            .footer a {
                color: #667eea;
                text-decoration: none;
            }
            
            .footer a:hover {
                text-decoration: underline;
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
            
            .destroy-section {
                margin-top: 40px;
                padding-top: 30px;
                border-top: 3px solid #fee2e2;
                background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
                padding: 25px;
                border-radius: 12px;
                margin-left: -40px;
                margin-right: -40px;
                margin-bottom: -40px;
            }
            
            .destroy-warning {
                background: #fee2e2;
                border-left: 5px solid #dc2626;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 8px;
            }
            
            .destroy-warning h3 {
                color: #991b1b;
                margin-bottom: 10px;
                font-size: 1.3em;
            }
            
            .destroy-warning p {
                color: #7f1d1d;
                margin: 8px 0;
                line-height: 1.6;
            }
            
            .destroy-warning ul {
                margin: 15px 0;
                padding-left: 25px;
            }
            
            .destroy-warning li {
                color: #7f1d1d;
                margin: 8px 0;
            }
            
            /* Modal Styles */
            .modal {
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
                overflow-y: auto;
                align-items: center;
                justify-content: center;
            }
            
            .modal-content {
                background-color: white;
                margin: 3% auto;
                padding: 0;
                border-radius: 15px;
                width: 90%;
                max-width: 900px;
                max-height: 90vh;
                display: flex;
                flex-direction: column;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            
            .destroy-confirmation-modal .modal-content {
                border: 3px solid #dc2626;
                max-width: 600px;
            }
            
            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 25px 30px;
                border-bottom: 2px solid #e0e0e0;
            }
            
            .destroy-confirmation-modal .modal-header {
                background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
                color: white;
                border-bottom: none;
            }
            
            .modal-header h2 {
                color: #333;
                margin: 0;
            }
            
            .destroy-confirmation-modal .modal-header h2 {
                color: white;
            }
            
            .close {
                color: #aaa;
                font-size: 32px;
                font-weight: bold;
                cursor: pointer;
                line-height: 1;
                transition: color 0.2s;
            }
            
            .destroy-confirmation-modal .close {
                color: white;
            }
            
            .close:hover {
                color: #000;
            }
            
            .destroy-confirmation-modal .close:hover {
                color: #f0f0f0;
            }
            
            .modal-body {
                padding: 25px 30px;
                overflow-y: auto;
                flex: 1;
            }
            
            .cli-commands-section {
                margin-bottom: 25px;
            }
            
            .cli-commands-section h3 {
                color: #333;
                font-size: 1.1em;
                margin-bottom: 15px;
            }
            
            .cli-command {
                background: #f8f9fa;
                padding: 12px 15px;
                border-radius: 6px;
                border: 2px solid #e0e0e0;
                cursor: pointer;
                transition: all 0.2s;
                position: relative;
                margin-bottom: 10px;
            }
            
            .cli-command:hover {
                border-color: #667eea;
                background: #f0f4ff;
            }
            
            .cli-command code {
                color: #333;
                font-size: 0.9em;
                font-family: 'Courier New', monospace;
            }
            
            .copy-hint {
                float: right;
                color: #667eea;
                font-size: 0.85em;
                font-weight: 600;
            }
            
            .cli-command.copied {
                border-color: #48bb78;
                background: #d4edda;
            }
            
            .logs-section h3 {
                color: #333;
                font-size: 1.1em;
                margin-bottom: 10px;
            }
            
            .logs-container {
                background: #1e1e1e;
                color: #d4d4d4;
                padding: 20px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 0.85em;
                overflow-y: auto;
                max-height: 400px;
                min-height: 200px;
            }
            
            .log-entry {
                margin-bottom: 8px;
                line-height: 1.6;
                word-wrap: break-word;
            }
            
            .log-timestamp {
                color: #858585;
                margin-right: 8px;
            }
            
            .log-level-INFO {
                color: #4ec9b0;
                font-weight: bold;
                margin-right: 8px;
            }
            
            .log-level-WARNING {
                color: #dcdcaa;
                font-weight: bold;
                margin-right: 8px;
            }
            
            .log-level-ERROR {
                color: #f48771;
                font-weight: bold;
                margin-right: 8px;
            }
            
            .refresh-btn {
                margin-top: 15px;
                width: 100%;
            }
            
            .info-box {
                background: #e7f3ff;
                border-left: 4px solid #667eea;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 4px;
            }
            
            .info-box p {
                margin: 5px 0;
                color: #333;
                line-height: 1.6;
            }
            
            .warning-box {
                background: #fff3cd;
                border-left: 4px solid #ed8936;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 4px;
            }
            
            .warning-box p {
                margin: 5px 0;
                color: #333;
                line-height: 1.6;
            }
            
            .destroy-info {
                background: #fff7ed;
                border-left: 4px solid #f59e0b;
                padding: 15px;
                margin: 15px 0;
                border-radius: 4px;
            }
            
            .destroy-list {
                background: #f9fafb;
                padding: 15px 20px;
                border-radius: 8px;
                margin: 15px 0;
            }
            
            .destroy-list ul {
                margin: 10px 0;
                padding-left: 25px;
            }
            
            .destroy-list li {
                margin: 8px 0;
                color: #374151;
                line-height: 1.6;
            }
            
            .destroy-list h4 {
                color: #374151;
                margin-bottom: 10px;
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
                    <span class="label">Load Test Status:</span>
                    <span class="value" id="load-status">
                        <span class="badge badge-info">Idle</span>
                    </span>
                </div>
            </div>
            
            <div class="section-title">🔥 HPA Load Testing</div>
            
            <div class="actions">
                <button class="btn btn-warning" id="start-load-btn" onclick="startLoadTest()">
                    🔥 Start Load Test
                </button>
                <button class="btn btn-danger" id="stop-load-btn" onclick="stopLoadTest()" disabled>
                    🛑 Stop Load Test
                </button>
                <button class="btn btn-primary" onclick="viewLogs()">
                    📋 View Live Logs & CLI
                </button>
            </div>
            
            <div class="section-title">⚠️ Incident Simulation</div>
            
            <div class="actions">
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
            
            <div class="section-title">📊 API & Metrics</div>
            
            <div class="actions">
                <a href="/docs" class="btn btn-primary" target="_blank">
                    📖 API Documentation
                </a>
                <a href="/metrics" class="btn btn-success" target="_blank">
                    📈 Prometheus Metrics
                </a>
            </div>
            
            <div class="destroy-section">
                <div class="section-title">🗑️ Cluster Cleanup</div>
                
                <div class="destroy-warning">
                    <h3>⚠️ DANGER ZONE</h3>
                    <p><strong>Use this when you're completely finished with the demo.</strong></p>
                    <p>This will provide instructions to destroy:</p>
                    <ul>
                        <li>The entire kind cluster (k8s-demo)</li>
                        <li>All Kubernetes resources (pods, services, deployments)</li>
                        <li>All configurations (ConfigMaps, Secrets, HPA)</li>
                        <li>Port-forward processes</li>
                        <li>Optionally: Docker images</li>
                    </ul>
                    <p><strong style="color: #dc2626;">⚠️ This requires running cleanup script on your host machine!</strong></p>
                </div>
                
                <div class="actions">
                    <button class="btn btn-destroy" onclick="showDestroyConfirmation()">
                        🗑️ Destroy Everything
                    </button>
                </div>
            </div>
            
            <div class="footer">
                Built for Kubernetes Production Learning | 
                <a href="https://github.com/shaydevops2024/kubernetes-production-simulator" target="_blank">View on GitHub</a>
            </div>
        </div>
        
        <!-- Logs & CLI Commands Modal -->
        <div id="logsModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>📋 Live Monitoring & CLI Commands</h2>
                    <span class="close" onclick="closeLogsModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <div class="info-box">
                        <p><strong>💡 Pro Tip:</strong> Run these commands in your terminal to watch auto-scaling in real-time!</p>
                        <p>Click any command below to copy it to your clipboard. Logs auto-refresh every 30 seconds.</p>
                    </div>
                    
                    <div class="cli-commands-section">
                        <h3>🖥️ Useful kubectl Commands (Click to Copy)</h3>
                        
                        <div class="cli-command" onclick="copyCommand(this)" data-command="kubectl get hpa -n k8s-multi-demo -w">
                            <code>kubectl get hpa -n k8s-multi-demo -w</code>
                            <span class="copy-hint">📋 Click to copy</span>
                        </div>
                        
                        <div class="cli-command" onclick="copyCommand(this)" data-command="kubectl get pods -n k8s-multi-demo -w">
                            <code>kubectl get pods -n k8s-multi-demo -w</code>
                            <span class="copy-hint">📋 Click to copy</span>
                        </div>
                        
                        <div class="cli-command" onclick="copyCommand(this)" data-command="kubectl top pods -n k8s-multi-demo">
                            <code>kubectl top pods -n k8s-multi-demo</code>
                            <span class="copy-hint">📋 Click to copy</span>
                        </div>
                        
                        <div class="cli-command" onclick="copyCommand(this)" data-command="kubectl logs -f -l app=k8s-demo-app -n k8s-multi-demo">
                            <code>kubectl logs -f -l app=k8s-demo-app -n k8s-multi-demo</code>
                            <span class="copy-hint">📋 Click to copy</span>
                        </div>
                        
                        <div class="cli-command" onclick="copyCommand(this)" data-command="kubectl describe hpa k8s-demo-hpa -n k8s-multi-demo">
                            <code>kubectl describe hpa k8s-demo-hpa -n k8s-multi-demo</code>
                            <span class="copy-hint">📋 Click to copy</span>
                        </div>
                    </div>
                    
                    <div class="cli-commands-section">
                        <h3>🔥 Manual Load Testing (Optional - Click to Copy)</h3>
                        
                        <div class="warning-box">
                            <p><strong>⚠️ Note:</strong> You can also use the UI buttons above, but manual CLI testing gives you more control.</p>
                        </div>
                        
                        <div class="cli-command" onclick="copyCommand(this)" data-command="for i in {1..50}; do (while true; do curl -s http://localhost:8080/ > /dev/null; sleep 0.1; done) & done">
                            <code>for i in {1..50}; do (while true; do curl -s http://localhost:8080/ > /dev/null; sleep 0.1; done) & done</code>
                            <span class="copy-hint">📋 Start load test</span>
                        </div>
                        
                        <div class="cli-command" onclick="copyCommand(this)" data-command="pkill curl">
                            <code>pkill curl</code>
                            <span class="copy-hint">📋 Stop load test</span>
                        </div>
                    </div>
                    
                    <div class="logs-section">
                        <h3>📊 Application Logs (Auto-refreshing every 30s)</h3>
                        <div class="logs-container" id="logs-container">
                            Loading logs...
                        </div>
                        <button class="btn btn-primary refresh-btn" onclick="refreshLogs()">
                            🔄 Refresh Logs Now
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Destroy Confirmation Modal -->
        <div id="destroyModal" class="modal destroy-confirmation-modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>🗑️ Destroy Kubernetes Cluster</h2>
                    <span class="close" onclick="closeDestroyModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <div class="destroy-warning">
                        <h3>⚠️ FINAL WARNING</h3>
                        <p>You are about to receive instructions to <strong>permanently delete</strong> the entire Kubernetes demo environment.</p>
                    </div>
                    
                    <div class="destroy-list">
                        <h4>This will remove:</h4>
                        <ul>
                            <li>✗ Kind cluster: <code>k8s-demo</code></li>
                            <li>✗ Namespace: <code>k8s-multi-demo</code></li>
                            <li>✗ All pods, services, deployments (2-10 pods)</li>
                            <li>✗ HPA auto-scaling configuration</li>
                            <li>✗ NGINX Ingress Controller</li>
                            <li>✗ Metrics Server</li>
                            <li>✗ ConfigMaps and Secrets</li>
                            <li>✗ All port-forward processes</li>
                            <li>✗ Temporary configuration files</li>
                            <li>✗ Docker image (optional)</li>
                        </ul>
                    </div>
                    
                    <div class="destroy-info">
                        <p><strong>💡 Good News:</strong> You can recreate everything anytime by running:</p>
                        <p style="margin-top: 10px;"><code>./kind_setup.sh</code></p>
                    </div>
                    
                    <div class="info-box" style="background: #fef2f2; border-color: #dc2626;">
                        <p><strong>📋 Next Steps:</strong></p>
                        <p>1. Click "Get Cleanup Instructions" below</p>
                        <p>2. Follow the instructions provided</p>
                        <p>3. Close this browser window</p>
                        <p>4. Run the cleanup script in your terminal</p>
                    </div>
                    
                    <div class="actions" style="margin-top: 25px;">
                        <button class="btn btn-destroy" onclick="executeDestroy()" style="width: 48%;">
                            🗑️ Get Cleanup Instructions
                        </button>
                        <button class="btn btn-primary" onclick="closeDestroyModal()" style="width: 48%;">
                            ← Cancel
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Fetch and display application status
            async function updateStatus() {
                try {
                    // Get config
                    const configRes = await fetch('/api/info');
                    if (!configRes.ok) throw new Error('Failed to fetch config');
                    const config = await configRes.json();
                    
                    document.getElementById('app-name').textContent = config.app_name;
                    document.getElementById('environment').innerHTML = 
                        `<span class="badge badge-info">${config.environment}</span>`;
                    
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
                    
                    // Check load test status
                    const loadRes = await fetch('/load-test/status');
                    if (!loadRes.ok) throw new Error('Failed to fetch load status');
                    const loadData = await loadRes.json();
                    const loadBadge = loadData.running ?
                        '<span class="badge badge-warning">🔥 Running</span>' :
                        '<span class="badge badge-info">Idle</span>';
                    document.getElementById('load-status').innerHTML = loadBadge;
                    
                    // Update buttons
                    document.getElementById('start-load-btn').disabled = loadData.running;
                    document.getElementById('stop-load-btn').disabled = !loadData.running;
                    
                } catch (error) {
                    console.error('Error updating status:', error);
                }
            }
            
            async function startLoadTest() {
                if (!confirm('🔥 Start Load Test?\\n\\nThis will generate traffic to trigger HPA auto-scaling.\\n\\nWatch scaling with:\\nkubectl get hpa -n k8s-multi-demo -w\\n\\nContinue?')) {
                    return;
                }
                
                try {
                    const response = await fetch('/load-test/start', { method: 'POST' });
                    const data = await response.json();
                    
                    if (response.ok) {
                        alert('✅ ' + data.message + '\\n\\n📊 Watch scaling:\\nkubectl get hpa -n k8s-multi-demo -w\\nkubectl get pods -n k8s-multi-demo -w');
                    } else {
                        alert('⚠️ ' + (data.message || 'Failed to start load test'));
                    }
                    updateStatus();
                } catch (error) {
                    console.error('Load test start error:', error);
                    alert('❌ Error starting load test: ' + error.message);
                }
            }
            
            async function stopLoadTest() {
                try {
                    const response = await fetch('/load-test/stop', { method: 'POST' });
                    if (!response.ok) {
                        throw new Error('Failed to stop load test');
                    }
                    const data = await response.json();
                    alert('✅ ' + data.message);
                    await updateStatus();
                } catch (error) {
                    console.error('Load test stop error:', error);
                    alert('❌ Error stopping load test: ' + error.message);
                    await updateStatus();
                }
            }
            
            function copyCommand(element) {
                const command = element.getAttribute('data-command');
                navigator.clipboard.writeText(command).then(() => {
                    element.classList.add('copied');
                    const hint = element.querySelector('.copy-hint');
                    const originalText = hint.textContent;
                    hint.textContent = '✅ Copied!';
                    
                    setTimeout(() => {
                        element.classList.remove('copied');
                        hint.textContent = originalText;
                    }, 2000);
                }).catch(err => {
                    console.error('Copy failed:', err);
                    alert('Failed to copy: ' + err);
                });
            }
            
            async function refreshLogs() {
                const container = document.getElementById('logs-container');
                const previousScrollHeight = container.scrollHeight;
                const wasAtBottom = container.scrollTop + container.clientHeight >= previousScrollHeight - 50;
                
                try {
                    const response = await fetch('/logs');
                    if (!response.ok) throw new Error('Failed to fetch logs');
                    const logs = await response.json();
                    
                    if (logs.length === 0) {
                        container.innerHTML = '<div class="log-entry"><span class="log-level-INFO">[INFO]</span>No logs available yet. Application just started or no activity recorded.</div>';
                    } else {
                        // Show last 50 logs, newest at bottom
                        const recentLogs = logs.slice(-50);
                        container.innerHTML = recentLogs.map(log => {
                            const timestamp = new Date(log.timestamp).toLocaleTimeString();
                            return `<div class="log-entry">
                                <span class="log-timestamp">${timestamp}</span>
                                <span class="log-level-${log.level}">[${log.level}]</span>
                                <span>${log.message}</span>
                            </div>`;
                        }).join('');
                    }
                    
                    // Auto-scroll to bottom if user was already at bottom
                    if (wasAtBottom) {
                        container.scrollTop = container.scrollHeight;
                    }
                } catch (error) {
                    console.error('Logs fetch error:', error);
                    container.innerHTML = `<div class="log-entry"><span class="log-level-ERROR">[ERROR]</span>Error loading logs: ${error.message}</div>`;
                }
            }
            
            let logsAutoRefreshInterval = null;
            
            async function viewLogs() {
                const modal = document.getElementById('logsModal');
                modal.style.display = 'flex';
                await refreshLogs();
                
                // Auto-scroll to bottom on first load
                const container = document.getElementById('logs-container');
                container.scrollTop = container.scrollHeight;
                
                // Auto-refresh logs every 30 seconds while modal is open
                if (logsAutoRefreshInterval) {
                    clearInterval(logsAutoRefreshInterval);
                }
                
                logsAutoRefreshInterval = setInterval(async () => {
                    if (modal.style.display === 'flex') {
                        await refreshLogs();
                    } else {
                        clearInterval(logsAutoRefreshInterval);
                        logsAutoRefreshInterval = null;
                    }
                }, 30000); // 30 seconds
            }
            
            function closeLogsModal() {
                const modal = document.getElementById('logsModal');
                modal.style.display = 'none';
                if (logsAutoRefreshInterval) {
                    clearInterval(logsAutoRefreshInterval);
                    logsAutoRefreshInterval = null;
                }
            }
            
            async function simulateCrash() {
                if (confirm('⚠️ This will make the app unhealthy.\\n\\nKubernetes will automatically restart the pod.\\n\\nContinue?')) {
                    try {
                        await fetch('/simulate/crash', { method: 'POST' });
                        alert('💥 App is now unhealthy!\\n\\n✅ Kubernetes will restart the pod automatically.\\n\\n📊 Watch it happen:\\nkubectl get pods -n k8s-multi-demo -w');
                        setTimeout(updateStatus, 1000);
                    } catch (error) {
                        alert('Error: ' + error);
                    }
                }
            }
            
            async function simulateNotReady() {
                if (confirm('⚠️ This will make the app not ready.\\n\\nKubernetes will stop routing traffic to this pod.\\n\\nContinue?')) {
                    try {
                        await fetch('/simulate/notready', { method: 'POST' });
                        alert('⚠️ App is now not ready!\\n\\n🚫 Kubernetes will stop sending traffic.\\n\\n📊 Check status:\\nkubectl describe pod <pod-name> -n k8s-multi-demo');
                        setTimeout(updateStatus, 1000);
                    } catch (error) {
                        alert('Error: ' + error);
                    }
                }
            }
            
            async function resetApp() {
                try {
                    await fetch('/reset', { method: 'POST' });
                    alert('✅ App reset to healthy state!\\n\\nAll probes are now passing.');
                    setTimeout(updateStatus, 1000);
                } catch (error) {
                    alert('Error: ' + error);
                }
            }
            
            // Destroy cluster functionality
            function showDestroyConfirmation() {
                document.getElementById('destroyModal').style.display = 'flex';
            }
            
            function closeDestroyModal() {
                document.getElementById('destroyModal').style.display = 'none';
            }
            
            async function executeDestroy() {
                try {
                    const response = await fetch('/admin/destroy-cluster', { method: 'POST' });
                    const data = await response.json();
                    
                    if (response.ok) {
                        // Show instructions in a nice alert
                        let instructions = '🗑️ CLUSTER CLEANUP INSTRUCTIONS\\n\\n';
                        instructions += '⚠️ ' + data.message + '\\n\\n';
                        instructions += '📋 STEPS TO FOLLOW:\\n\\n';
                        
                        data.next_steps.forEach((step, index) => {
                            instructions += step + '\\n';
                        });
                        
                        instructions += '\\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n\\n';
                        instructions += '🔴 Run this command in your terminal:\\n\\n';
                        instructions += '   ./cleanup.sh\\n\\n';
                        instructions += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n\\n';
                        instructions += '💡 This browser window will remain open.\\n';
                        instructions += 'Close it after running the cleanup script.\\n\\n';
                        instructions += '✅ You can recreate everything with: ./kind_setup.sh';
                        
                        alert(instructions);
                        
                        // Create a detailed instructions page
                        const instructionsWindow = window.open('', '_blank');
                        if (instructionsWindow) {
                            instructionsWindow.document.write(`
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <title>Cleanup Instructions</title>
                                    <style>
                                        body {
                                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                                            max-width: 800px;
                                            margin: 50px auto;
                                            padding: 30px;
                                            background: #f9fafb;
                                        }
                                        .container {
                                            background: white;
                                            padding: 40px;
                                            border-radius: 12px;
                                            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                                        }
                                        h1 {
                                            color: #dc2626;
                                            border-bottom: 3px solid #dc2626;
                                            padding-bottom: 15px;
                                        }
                                        .warning {
                                            background: #fee2e2;
                                            border-left: 5px solid #dc2626;
                                            padding: 20px;
                                            margin: 20px 0;
                                            border-radius: 8px;
                                        }
                                        .step {
                                            background: #f3f4f6;
                                            padding: 15px 20px;
                                            margin: 15px 0;
                                            border-radius: 8px;
                                            border-left: 4px solid #667eea;
                                        }
                                        .command {
                                            background: #1e1e1e;
                                            color: #4ec9b0;
                                            padding: 20px;
                                            border-radius: 8px;
                                            font-family: 'Courier New', monospace;
                                            font-size: 16px;
                                            margin: 20px 0;
                                            cursor: pointer;
                                        }
                                        .command:hover {
                                            background: #2d2d2d;
                                        }
                                        .success {
                                            background: #d1fae5;
                                            border-left: 4px solid #10b981;
                                            padding: 15px;
                                            margin: 20px 0;
                                            border-radius: 8px;
                                        }
                                        code {
                                            background: #f3f4f6;
                                            padding: 2px 6px;
                                            border-radius: 4px;
                                            font-family: 'Courier New', monospace;
                                        }
                                    </style>
                                </head>
                                <body>
                                    <div class="container">
                                        <h1>🗑️ Kubernetes Cluster Cleanup Instructions</h1>
                                        
                                        <div class="warning">
                                            <h3>⚠️ ${data.message}</h3>
                                            <p>The cleanup must be performed from your <strong>host machine terminal</strong>, not from within the Kubernetes pod.</p>
                                        </div>
                                        
                                        <h2>📋 Step-by-Step Instructions:</h2>
                                        
                                        ${data.next_steps.map((step, idx) => `
                                            <div class="step">
                                                <strong>${step}</strong>
                                            </div>
                                        `).join('')}
                                        
                                        <h2>🔴 Command to Run:</h2>
                                        <div class="command" onclick="navigator.clipboard.writeText('./cleanup.sh'); alert('✅ Copied to clipboard!');" title="Click to copy">
                                            ./cleanup.sh
                                            <div style="float: right; color: #858585;">📋 Click to copy</div>
                                        </div>
                                        
                                        <div class="success">
                                            <h3>✅ After Cleanup:</h3>
                                            <p>You can recreate the entire demo environment anytime by running:</p>
                                            <p><code>./kind_setup.sh</code></p>
                                        </div>
                                        
                                        <h2>🗑️ What Will Be Deleted:</h2>
                                        <ul style="line-height: 2;">
                                            <li>✗ Kind cluster: <code>k8s-demo</code></li>
                                            <li>✗ Namespace: <code>k8s-multi-demo</code></li>
                                            <li>✗ All pods and deployments</li>
                                            <li>✗ All services and ingress</li>
                                            <li>✗ HPA and metrics-server</li>
                                            <li>✗ ConfigMaps and Secrets</li>
                                            <li>✗ Port-forward processes</li>
                                            <li>✗ Docker image (optional)</li>
                                        </ul>
                                        
                                        <p style="margin-top: 30px; color: #6b7280;">
                                            <strong>Note:</strong> Close this browser window after running the cleanup script.
                                        </p>
                                    </div>
                                </body>
                                </html>
                            `);
                        }
                        
                        closeDestroyModal();
                    } else {
                        alert('❌ Error: ' + (data.message || 'Failed to get cleanup instructions'));
                    }
                } catch (error) {
                    console.error('Destroy error:', error);
                    alert('❌ Error: ' + error.message);
                }
            }
            
            // Close modal when clicking outside
            window.onclick = function(event) {
                const logsModal = document.getElementById('logsModal');
                const destroyModal = document.getElementById('destroyModal');
                
                if (event.target == logsModal) {
                    closeLogsModal();
                }
                if (event.target == destroyModal) {
                    closeDestroyModal();
                }
            }
            
            // Close modal with Escape key
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Escape') {
                    closeLogsModal();
                    closeDestroyModal();
                }
            });
            
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

@app.get("/logs")
async def get_logs():
    """
    Get recent application logs
    Returns last 100 log entries for the live log viewer
    """
    return list(log_buffer)

@app.get("/load-test/status")
async def load_test_status():
    """Check if load test is running"""
    global load_test_running
    return {"running": load_test_running}

@app.post("/load-test/start")
async def start_load_test():
    """
    Start a load test to trigger HPA scaling
    Generates HTTP requests to the Kubernetes service (distributed across all pods)
    """
    global load_test_running, load_test_task
    
    if load_test_running:
        return {"message": "Load test already running", "status": "running"}
    
    try:
        # Start background load generation
        load_test_running = True
        load_test_task = asyncio.create_task(generate_load())
        logger.warning("🔥 LOAD TEST STARTED - Generating traffic to trigger HPA scaling")
        logger.info("Load test will run for 2 minutes or until manually stopped")
        
        return {
            "message": "Load test started! Generating load for 2 minutes. Watch: kubectl get hpa -n k8s-multi-demo -w",
            "status": "started",
            "duration": "2 minutes (or until stopped)"
        }
    except Exception as e:
        load_test_running = False
        logger.error(f"Failed to start load test: {e}")
        return Response(
            content=f'{{"message": "Error: {str(e)}", "status": "error"}}',
            status_code=500,
            media_type="application/json"
        )

@app.post("/load-test/stop")
async def stop_load_test():
    """Stop the running load test with aggressive cleanup"""
    global load_test_running, load_test_task
    
    if not load_test_running:
        return {"message": "No load test running", "status": "idle"}
    
    try:
        # Set flag first to stop new requests
        load_test_running = False
        logger.info("🛑 Stopping load test...")
        
        # Cancel the task
        if load_test_task and not load_test_task.done():
            load_test_task.cancel()
            try:
                # Wait for task to cancel, with timeout
                await asyncio.wait_for(load_test_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("Load test task cancelled successfully")
            except Exception as e:
                logger.warning(f"Error cancelling task: {e}")
        
        load_test_task = None
        
        # Force garbage collection to clean up any lingering connections
        import gc
        gc.collect()
        
        # Wait a moment for connections to fully close
        await asyncio.sleep(0.5)
        
        logger.info("🛑 LOAD TEST STOPPED - All traffic generation ended")
        logger.info("All connections closed. CPU should drop within 30 seconds.")
        logger.info("Pods will scale down to minimum in ~5 minutes")
        
        return {
            "message": "Load test stopped. CPU will drop within 30s. Pods will scale down in ~5 minutes.",
            "status": "stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping load test: {e}")
        load_test_running = False
        load_test_task = None
        return {
            "message": f"Load test stopped (with error: {str(e)}). If CPU stays high, run: kubectl rollout restart deployment/k8s-demo-app -n k8s-multi-demo",
            "status": "stopped"
        }

async def generate_load():
    """
    Generate HTTP load by making requests to the Kubernetes service
    This distributes load across all pods and triggers HPA scaling
    """
    global load_test_running
    import aiohttp
    
    # Target the Kubernetes service (not localhost!)
    # This ensures requests are distributed across all pods
    service_url = 'http://k8s-demo-service.k8s-multi-demo.svc.cluster.local'
    
    logger.info(f"Load generator targeting: {service_url}")
    
    start_time = asyncio.get_event_loop().time()
    duration = 120  # 2 minutes
    request_count = 0
    session = None
    
    try:
        # Create aiohttp session
        timeout = aiohttp.ClientTimeout(total=5)
        session = aiohttp.ClientSession(timeout=timeout)
        
        while load_test_running and (asyncio.get_event_loop().time() - start_time) < duration:
            try:
                # Make 20 concurrent requests per batch
                tasks = []
                for _ in range(20):
                    if not load_test_running:  # Check flag frequently for quick stop
                        break
                    task = session.get(service_url)
                    tasks.append(task)
                
                if not load_test_running:  # Exit early if stopped
                    logger.info("Load test stopped by user - exiting immediately")
                    break
                
                # Execute all requests concurrently
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                request_count += len(responses)
                
                # Log progress every 100 requests
                if request_count % 100 == 0:
                    logger.info(f"Load test: {request_count} requests sent, {int(asyncio.get_event_loop().time() - start_time)}s elapsed")
                
                # Small delay to control request rate
                await asyncio.sleep(0.05)
                
            except asyncio.CancelledError:
                logger.info("Load test cancelled by user")
                break
            except Exception as e:
                if load_test_running:  # Only log if not intentionally stopped
                    logger.error(f"Load generation error: {e}")
                await asyncio.sleep(0.5)  # Back off on errors
    
    except Exception as e:
        logger.error(f"Load test failed: {e}")
    
    finally:
        # Clean up session properly
        if session and not session.closed:
            logger.info("Closing aiohttp session and all connections...")
            await session.close()
            # Give time for connections to properly close
            await asyncio.sleep(0.25)
        
        load_test_running = False
        elapsed = int(asyncio.get_event_loop().time() - start_time)
        logger.info(f"🏁 LOAD TEST COMPLETED - {request_count} requests in {elapsed}s")
        logger.info("All connections closed. CPU should drop to normal within 30 seconds.")
        logger.info("HPA will scale down pods to minimum in ~5 minutes")

@app.post("/simulate/crash")
async def simulate_crash():
    """
    Simulate app becoming unhealthy (for testing liveness probe)
    This is for incident simulation and learning purposes
    """
    global app_healthy
    app_healthy = False
    logger.error("INCIDENT SIMULATION: App health set to unhealthy - liveness probe will fail!")
    logger.warning("Kubernetes will detect this and restart the pod automatically")
    return {"message": "App is now unhealthy - will be restarted by Kubernetes"}

@app.post("/simulate/notready")
async def simulate_notready():
    """
    Simulate app becoming not ready (for testing readiness probe)
    This is for incident simulation and learning purposes
    """
    global app_ready
    app_ready = False
    logger.warning("INCIDENT SIMULATION: App readiness set to false - will stop receiving traffic!")
    logger.info("Kubernetes will stop routing traffic to this pod")
    return {"message": "App is now not ready - Kubernetes will stop routing traffic"}

@app.post("/reset")
async def reset():
    """
    Reset app to healthy state
    Restores both health and readiness to normal
    """
    global app_healthy, app_ready
    app_healthy = True
    app_ready = True
    logger.info("✅ App reset to healthy and ready state - all probes passing")
    return {"message": "App reset to healthy state"}

@app.post("/admin/destroy-cluster")
async def destroy_cluster():
    """
    DANGEROUS: Provides instructions to destroy the entire Kubernetes cluster
    This endpoint cannot actually destroy the cluster (pods can't destroy themselves)
    Instead, it provides instructions to run the cleanup script on the host
    """
    try:
        logger.warning("🔴 CLUSTER DESTRUCTION INSTRUCTIONS REQUESTED BY USER")
        logger.warning("Providing instructions for manual cleanup")
        
        return {
            "status": "instructions",
            "message": "Cluster destruction must be performed from your host machine terminal",
            "instructions": [
                "Exit the browser",
                "Return to your terminal",
                "Run the cleanup script: ./cleanup.sh",
                "Or manually delete: kind delete cluster --name k8s-demo",
                "",
                "The cleanup script will:",
                "- Stop all port-forwards",
                "- Delete the k8s-multi-demo namespace",
                "- Delete the kind cluster (k8s-demo)",
                "- Optionally remove Docker images",
                "- Clean up temporary files"
            ],
            "next_steps": [
                "1. Close this browser window",
                "2. Return to your terminal",
                "3. Run: ./cleanup.sh",
                "4. Confirm when prompted",
                "5. Everything will be removed"
            ]
        }
    except Exception as e:
        logger.error(f"Error in destroy endpoint: {e}")
        return Response(
            content=f'{{"message": "Error: {str(e)}", "status": "error"}}',
            status_code=500,
            media_type="application/json"
        )

@app.get("/db/health")
async def database_health():
    """Check database connection"""
    connected, message = check_db_connection()
    if connected:
        return {"database": "connected", "message": message, "stats": get_db_stats()}
    return Response(content=f'{{"error": "{message}"}}', status_code=503)

@app.get("/api/db/stats")
async def get_database_stats():
    """Get database statistics"""
    return get_db_stats()

@app.get("/api/users")
async def get_users(db: Session = Depends(get_db)):
    """Get all users"""
    users = db.query(User).all()
    return [user.to_dict() for user in users]

@app.get("/api/tasks")
async def get_tasks(db: Session = Depends(get_db)):
    """Get all tasks"""
    tasks = db.query(Task).all()
    return [task.to_dict() for task in tasks]

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info(f"========================================")
    logger.info(f"Starting {APP_NAME}")
    logger.info(f"Environment: {APP_ENV}")
    logger.info(f"Secret configured: {'yes' if SECRET_TOKEN != 'no-secret-configured' else 'no'}")
    logger.info(f"Application ready to accept requests")
    logger.info(f"========================================")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    global load_test_running, load_test_task
    
    if load_test_running:
        logger.info("Stopping load test on application shutdown...")
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
    # Run the app on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)