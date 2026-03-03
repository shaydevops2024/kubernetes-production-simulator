import os
import time
import random
import threading
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# ── Configuration ────────────────────────────────────────────────────────────
APP_VERSION = os.getenv("APP_VERSION", "v1")
APP_COLOR   = os.getenv("APP_COLOR", "blue" if APP_VERSION == "v1" else "green")
APP_PORT    = int(os.getenv("APP_PORT", "4545"))
INSTANCE_ID = os.getenv("HOSTNAME", "local")

# ── Runtime state ─────────────────────────────────────────────────────────────
_start_time  = time.time()
_error_rate  = float(os.getenv("ERROR_RATE", "0.0"))  # 0.0 – 1.0
_tasks: dict = {}
_task_seq    = 0
_lock        = threading.Lock()

# ── Prometheus metrics ────────────────────────────────────────────────────────
REQUEST_TOTAL = Counter(
    "app_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status", "version"],
)
REQUEST_DURATION = Histogram(
    "app_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint", "version"],
)
ERROR_TOTAL = Counter(
    "app_errors_total",
    "Total errors returned",
    ["endpoint", "version"],
)
ERROR_RATE_GAUGE = Gauge(
    "app_configured_error_rate",
    "Configured synthetic error rate (0‑1)",
    ["version"],
)
ERROR_RATE_GAUGE.labels(version=APP_VERSION).set(_error_rate)

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title=f"DeployInsight {APP_VERSION}", version="1.0.0")


# ── Pydantic models ───────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str
    priority: Optional[str] = "medium"   # v2 feature
    tags: Optional[list[str]] = []       # v2 feature


class Task(BaseModel):
    id: int
    title: str
    done: bool = False
    priority: Optional[str] = "medium"
    tags: Optional[list[str]] = []
    created_at: str


# ── Middleware: metrics ───────────────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    global _error_rate
    start = time.time()
    endpoint = request.url.path

    # Inject a synthetic error to simulate bad deployments
    if endpoint not in ("/metrics", "/health", "/ready", "/break", "/fix"):
        if random.random() < _error_rate:
            ERROR_TOTAL.labels(endpoint=endpoint, version=APP_VERSION).inc()
            REQUEST_TOTAL.labels(
                method=request.method,
                endpoint=endpoint,
                status="500",
                version=APP_VERSION,
            ).inc()
            return JSONResponse(
                {"error": "synthetic error injected for demo", "version": APP_VERSION},
                status_code=500,
            )

    response = await call_next(request)
    duration = time.time() - start

    REQUEST_TOTAL.labels(
        method=request.method,
        endpoint=endpoint,
        status=str(response.status_code),
        version=APP_VERSION,
    ).inc()
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=endpoint,
        version=APP_VERSION,
    ).observe(duration)

    return response


# ── Health / readiness ────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "color": APP_COLOR,
        "instance": INSTANCE_ID,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@app.get("/ready")
def ready():
    return {"ready": True, "version": APP_VERSION}


# ── Metrics endpoint ──────────────────────────────────────────────────────────
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Version info ──────────────────────────────────────────────────────────────
@app.get("/version")
def version():
    features = ["basic task CRUD", "health checks", "Prometheus metrics"]
    if APP_VERSION == "v2":
        features += ["task priority", "task tags", "enhanced dashboard"]
    return {
        "version": APP_VERSION,
        "color": APP_COLOR,
        "instance": INSTANCE_ID,
        "features": features,
        "error_rate": _error_rate,
    }


# ── Task CRUD ─────────────────────────────────────────────────────────────────
@app.get("/tasks")
def list_tasks():
    with _lock:
        tasks = list(_tasks.values())
    # v2 returns richer response
    if APP_VERSION == "v2":
        return {"tasks": tasks, "total": len(tasks), "version": APP_VERSION}
    return tasks


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    global _task_seq
    with _lock:
        _task_seq += 1
        task = Task(
            id=_task_seq,
            title=body.title,
            priority=body.priority if APP_VERSION == "v2" else None,
            tags=body.tags if APP_VERSION == "v2" else [],
            created_at=datetime.utcnow().isoformat(),
        )
        _tasks[_task_seq] = task.dict()
    return task


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    with _lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}/done")
def complete_task(task_id: int):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        task["done"] = True
    return task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    with _lock:
        if task_id not in _tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        del _tasks[task_id]


# ── Demo controls ─────────────────────────────────────────────────────────────
@app.post("/break")
def break_app():
    """Inject a 30 % error rate to simulate a bad deployment."""
    global _error_rate
    _error_rate = 0.30
    ERROR_RATE_GAUGE.labels(version=APP_VERSION).set(_error_rate)
    return {"message": "Error rate set to 30 % — watch Grafana / Argo Rollouts!", "error_rate": _error_rate}


@app.post("/fix")
def fix_app():
    """Reset error rate to 0."""
    global _error_rate
    _error_rate = 0.0
    ERROR_RATE_GAUGE.labels(version=APP_VERSION).set(_error_rate)
    return {"message": "Error rate reset to 0 — service healthy again.", "error_rate": _error_rate}


# ── Dashboard HTML ────────────────────────────────────────────────────────────
ACCENT = {"blue": "#3b82f6", "green": "#22c55e"}.get(APP_COLOR, "#6366f1")
BG     = {"blue": "#eff6ff", "green": "#f0fdf4"}.get(APP_COLOR, "#f5f3ff")

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DeployInsight {APP_VERSION}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',system-ui,sans-serif;background:{BG};color:#1e293b;min-height:100vh}}
    header{{background:{ACCENT};color:#fff;padding:1rem 2rem;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 8px rgba(0,0,0,.2)}}
    header h1{{font-size:1.4rem;font-weight:700;display:flex;align-items:center;gap:.6rem}}
    .badge{{background:rgba(255,255,255,.25);border-radius:999px;padding:.2rem .8rem;font-size:.8rem;font-weight:600}}
    .status-dot{{width:10px;height:10px;border-radius:50%;background:#4ade80;display:inline-block;animation:pulse 2s infinite}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
    main{{max-width:900px;margin:2rem auto;padding:0 1rem}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:2rem}}
    .card{{background:#fff;border-radius:12px;padding:1.25rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
    .card h3{{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;color:#64748b;margin-bottom:.4rem}}
    .card .value{{font-size:2rem;font-weight:700;color:{ACCENT}}}
    .card .sub{{font-size:.75rem;color:#94a3b8;margin-top:.25rem}}
    .section{{background:#fff;border-radius:12px;padding:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:1.5rem}}
    .section h2{{font-size:1rem;font-weight:600;margin-bottom:1rem;color:#374151}}
    .task-form{{display:flex;gap:.5rem;margin-bottom:1rem;flex-wrap:wrap}}
    .task-form input{{flex:1;min-width:180px;padding:.5rem .75rem;border:1px solid #e2e8f0;border-radius:8px;font-size:.9rem}}
    .task-form select{{padding:.5rem .75rem;border:1px solid #e2e8f0;border-radius:8px;font-size:.9rem;background:#fff}}
    .task-form button,.btn{{padding:.5rem 1rem;background:{ACCENT};color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.9rem;font-weight:600;transition:opacity .15s}}
    .btn:hover,.task-form button:hover{{opacity:.85}}
    .btn-danger{{background:#ef4444}}
    .btn-success{{background:#22c55e}}
    .btn-sm{{padding:.3rem .7rem;font-size:.8rem}}
    .task-list{{list-style:none;display:flex;flex-direction:column;gap:.5rem}}
    .task-item{{display:flex;align-items:center;gap:.75rem;padding:.6rem .75rem;border-radius:8px;background:#f8fafc;border:1px solid #e2e8f0}}
    .task-item.done{{opacity:.55;text-decoration:line-through}}
    .task-item .title{{flex:1;font-size:.9rem}}
    .priority{{font-size:.7rem;padding:.15rem .5rem;border-radius:999px;font-weight:600}}
    .priority-high{{background:#fee2e2;color:#dc2626}}
    .priority-medium{{background:#fef9c3;color:#ca8a04}}
    .priority-low{{background:#dcfce7;color:#16a34a}}
    .controls{{display:flex;gap:.75rem;flex-wrap:wrap;align-items:center}}
    .error-banner{{background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:.75rem 1rem;color:#dc2626;margin-bottom:1rem;display:none}}
    .version-badge{{font-size:.75rem;font-weight:600;padding:.2rem .6rem;border-radius:999px;background:{ACCENT};color:#fff}}
    footer{{text-align:center;padding:2rem;color:#94a3b8;font-size:.8rem}}
  </style>
</head>
<body>
<header>
  <h1>
    <span class="status-dot"></span>
    DeployInsight
    <span class="badge">{APP_VERSION}</span>
    <span class="badge" style="background:rgba(255,255,255,.15);text-transform:capitalize">{APP_COLOR}</span>
  </h1>
  <div style="display:flex;gap:.75rem;align-items:center;font-size:.85rem">
    <span>Instance: <strong>{INSTANCE_ID[:8]}</strong></span>
  </div>
</header>

<main>
  <div id="errorBanner" class="error-banner">
    ⚠️ High error rate detected! This simulates a bad deployment. Watch Argo Rollouts trigger an automatic rollback.
  </div>

  <!-- Stats row -->
  <div class="grid">
    <div class="card">
      <h3>Total Requests</h3>
      <div class="value" id="statRequests">—</div>
      <div class="sub">since startup</div>
    </div>
    <div class="card">
      <h3>Error Rate</h3>
      <div class="value" id="statErrorRate">—</div>
      <div class="sub">configured synthetic rate</div>
    </div>
    <div class="card">
      <h3>Uptime</h3>
      <div class="value" id="statUptime">—</div>
      <div class="sub">seconds</div>
    </div>
    <div class="card">
      <h3>App Version</h3>
      <div class="value" style="font-size:1.5rem">{APP_VERSION}</div>
      <div class="sub">{APP_COLOR} variant</div>
    </div>
  </div>

  <!-- Task Board -->
  <div class="section">
    <h2>📋 Task Board
      {'<span class="version-badge" style="margin-left:.5rem;font-size:.7rem">v2: priority + tags</span>' if APP_VERSION == "v2" else ""}
    </h2>
    <div class="task-form">
      <input type="text" id="taskInput" placeholder="New task title…" />
      {"<select id='taskPriority'><option value='low'>Low</option><option value='medium' selected>Medium</option><option value='high'>High</option></select>" if APP_VERSION == "v2" else ""}
      <button onclick="createTask()">+ Add Task</button>
    </div>
    <ul id="taskList" class="task-list"></ul>
  </div>

  <!-- Demo controls -->
  <div class="section">
    <h2>🧪 Deployment Demo Controls</h2>
    <p style="color:#64748b;font-size:.85rem;margin-bottom:1rem">
      These buttons let you simulate a bad deployment (30 % error rate) so you can watch
      Argo Rollouts automatically roll back based on Prometheus metrics.
    </p>
    <div class="controls">
      <button class="btn btn-danger" onclick="breakApp()">💥 Simulate Bad Deployment (30% errors)</button>
      <button class="btn btn-success" onclick="fixApp()">✅ Fix — Reset Errors</button>
    </div>
  </div>

  <!-- Endpoints reference -->
  <div class="section">
    <h2>🔌 API Endpoints</h2>
    <table style="width:100%;border-collapse:collapse;font-size:.85rem">
      <thead><tr style="border-bottom:2px solid #e2e8f0">
        <th style="text-align:left;padding:.4rem .6rem;color:#64748b">Method</th>
        <th style="text-align:left;padding:.4rem .6rem;color:#64748b">Path</th>
        <th style="text-align:left;padding:.4rem .6rem;color:#64748b">Description</th>
      </tr></thead>
      <tbody id="endpointTable"></tbody>
    </table>
  </div>
</main>

<footer>DeployInsight {APP_VERSION} &nbsp;·&nbsp; {APP_COLOR.capitalize()} variant &nbsp;·&nbsp; Instance: {INSTANCE_ID[:12]}</footer>

<script>
const ENDPOINTS = [
  {{method:"GET",  path:"/",         desc:"This dashboard"}},
  {{method:"GET",  path:"/health",   desc:"Health check (used by K8s liveness probe)"}},
  {{method:"GET",  path:"/ready",    desc:"Readiness check (used by K8s readiness probe)"}},
  {{method:"GET",  path:"/metrics",  desc:"Prometheus metrics"}},
  {{method:"GET",  path:"/version",  desc:"Version & feature info"}},
  {{method:"GET",  path:"/tasks",    desc:"List all tasks"}},
  {{method:"POST", path:"/tasks",    desc:"Create a task"}},
  {{method:"POST", path:"/break",    desc:"Inject 30 % error rate (demo)"}},
  {{method:"POST", path:"/fix",      desc:"Reset error rate to 0 (demo)"}},
];

const tbody = document.getElementById("endpointTable");
ENDPOINTS.forEach(e => {{
  const tr = document.createElement("tr");
  tr.style.borderBottom = "1px solid #f1f5f9";
  const color = e.method === "GET" ? "#3b82f6" : e.method === "POST" ? "#22c55e" : "#f59e0b";
  tr.innerHTML = `
    <td style="padding:.4rem .6rem"><span style="background:${{color}}20;color:${{color}};border-radius:4px;padding:.1rem .4rem;font-weight:600;font-family:monospace">${{e.method}}</span></td>
    <td style="padding:.4rem .6rem;font-family:monospace">${{e.path}}</td>
    <td style="padding:.4rem .6rem;color:#64748b">${{e.desc}}</td>`;
  tbody.appendChild(tr);
}});

// Stats refresh
async function refreshStats() {{
  try {{
    const v = await fetch("/version").then(r => r.json());
    document.getElementById("statErrorRate").textContent = (v.error_rate * 100).toFixed(0) + "%";
    const h = await fetch("/health").then(r => r.json());
    document.getElementById("statUptime").textContent = h.uptime_seconds;
    document.getElementById("errorBanner").style.display = v.error_rate > 0 ? "block" : "none";
  }} catch(e) {{}}
}}

// Task management
async function loadTasks() {{
  const r = await fetch("/tasks").then(r => r.json());
  const tasks = Array.isArray(r) ? r : (r.tasks || []);
  const list = document.getElementById("taskList");
  list.innerHTML = tasks.map(t => `
    <li class="task-item ${{t.done ? 'done' : ''}}" id="t${{t.id}}">
      <input type="checkbox" ${{t.done ? "checked" : ""}} onchange="toggleTask(${{t.id}})" />
      <span class="title">${{t.title}}</span>
      ${{t.priority ? `<span class="priority priority-${{t.priority}}">${{t.priority}}</span>` : ""}}
      ${{(t.tags||[]).map(tag => `<span style="font-size:.7rem;background:#f1f5f9;border-radius:4px;padding:.1rem .4rem">${{tag}}</span>`).join("")}}
      <button class="btn btn-danger btn-sm" onclick="deleteTask(${{t.id}})">✕</button>
    </li>`).join("");

  // Update request count (approx from task count)
  document.getElementById("statRequests").textContent = tasks.length * 2 + "+" ;
}}

async function createTask() {{
  const title = document.getElementById("taskInput").value.trim();
  if (!title) return;
  const priorityEl = document.getElementById("taskPriority");
  const body = {{ title, priority: priorityEl ? priorityEl.value : "medium", tags: [] }};
  await fetch("/tasks", {{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(body)}});
  document.getElementById("taskInput").value = "";
  loadTasks();
}}

async function toggleTask(id) {{
  await fetch(`/tasks/${{id}}/done`, {{method:"PATCH"}});
  loadTasks();
}}

async function deleteTask(id) {{
  await fetch(`/tasks/${{id}}`, {{method:"DELETE"}});
  loadTasks();
}}

async function breakApp() {{
  await fetch("/break", {{method:"POST"}});
  refreshStats();
  alert("💥 Error rate set to 30%!\\nWatch Prometheus metrics and Argo Rollouts dashboard.");
}}

async function fixApp() {{
  await fetch("/fix", {{method:"POST"}});
  refreshStats();
}}

document.getElementById("taskInput").addEventListener("keydown", e => {{
  if (e.key === "Enter") createTask();
}});

// Initial load + polling
loadTasks();
refreshStats();
setInterval(() => {{ loadTasks(); refreshStats(); }}, 3000);
</script>
</body>
</html>""")


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=False)
