"""
DeployTrack - Blue/Green Deployment Demo App

A simple release tracking dashboard that makes blue-green deployments visual.
The app changes color and branding based on environment variables:
  APP_COLOR  = "blue" | "green"
  APP_VERSION = "v1" | "v2"
  APP_ENV    = "production" | "staging"
"""

import os
import time
import threading
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# ── Config ────────────────────────────────────────────────────────────────────
APP_COLOR   = os.getenv("APP_COLOR", "blue")
APP_VERSION = os.getenv("APP_VERSION", "v1")
APP_ENV     = os.getenv("APP_ENV", "production")
PORT        = int(os.getenv("PORT", 5000))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./deploytrack.db")

# ── Database ──────────────────────────────────────────────────────────────────
Base = declarative_base()

class Release(Base):
    __tablename__ = "releases"
    id          = Column(Integer, primary_key=True, index=True)
    version     = Column(String(20), nullable=False)
    color       = Column(String(20), nullable=False)
    environment = Column(String(50), nullable=False)
    status      = Column(String(20), default="active")      # active | rolled_back | retired
    deployed_at = Column(DateTime, default=datetime.utcnow)
    notes       = Column(Text, default="")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)


def seed_initial_data():
    """Add seed releases so the dashboard isn't empty on first run."""
    db = Session()
    try:
        if db.query(Release).count() == 0:
            seed = [
                Release(version="v1", color="blue",  environment="production",
                        status="active",       notes="Initial production release",
                        deployed_at=datetime(2025, 1, 10, 9, 0, 0)),
                Release(version="v1", color="blue",  environment="staging",
                        status="retired",      notes="Staging validation passed",
                        deployed_at=datetime(2025, 1, 9, 15, 30, 0)),
                Release(version="v0.9", color="blue", environment="production",
                        status="rolled_back",  notes="Rolled back: memory leak detected",
                        deployed_at=datetime(2024, 12, 20, 11, 0, 0)),
            ]
            db.add_all(seed)
            db.commit()
    finally:
        db.close()

seed_initial_data()

# ── In-memory request counter ─────────────────────────────────────────────────
_counter_lock = threading.Lock()
_request_count = 0
_start_time    = time.time()

def bump():
    global _request_count
    with _counter_lock:
        _request_count += 1

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DeployTrack",
    description="Blue-Green Deployment Demo App",
    version=APP_VERSION,
)

class ReleaseCreate(BaseModel):
    version: str
    color: str
    environment: str
    notes: str = ""

class ReleaseUpdate(BaseModel):
    status: str
    notes: str = ""

# ── Theme constants ───────────────────────────────────────────────────────────
THEMES = {
    "blue": {
        "primary":     "#1d4ed8",
        "light":       "#dbeafe",
        "accent":      "#3b82f6",
        "gradient":    "linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #2563eb 100%)",
        "badge_bg":    "#eff6ff",
        "badge_text":  "#1d4ed8",
        "dot_color":   "#3b82f6",
        "label":       "BLUE",
        "feature_v2":  False,
    },
    "green": {
        "primary":     "#15803d",
        "light":       "#dcfce7",
        "accent":      "#22c55e",
        "gradient":    "linear-gradient(135deg, #14532d 0%, #15803d 50%, #16a34a 100%)",
        "badge_bg":    "#f0fdf4",
        "badge_text":  "#15803d",
        "dot_color":   "#22c55e",
        "label":       "GREEN",
        "feature_v2":  True,   # v2 / green gets a dark-mode toggle feature
    },
}

def t() -> dict:
    return THEMES.get(APP_COLOR, THEMES["blue"])

# ── HTML UI ───────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    bump()
    db = Session()
    try:
        releases = db.query(Release).order_by(Release.deployed_at.desc()).limit(10).all()
        uptime_s = int(time.time() - _start_time)
        uptime   = f"{uptime_s // 3600}h {(uptime_s % 3600) // 60}m {uptime_s % 60}s"
    finally:
        db.close()

    th = t()
    v2_feature_html = ""
    if th["feature_v2"]:
        v2_feature_html = """
        <div class="feature-banner">
            <span style="font-size:20px;">&#10024;</span>
            <div>
                <strong>New in v2 (Green):</strong> Dark Mode toggle now available!
                This feature only exists in the green environment — proving the new version deployed correctly.
            </div>
            <button id="dmBtn" onclick="toggleDark()" style="padding:6px 14px;border-radius:6px;border:1px solid rgba(255,255,255,.4);background:rgba(255,255,255,.15);color:white;cursor:pointer;font-weight:600;font-size:12px;white-space:nowrap;">Enable Dark Mode</button>
        </div>
        """

    rows_html = ""
    for r in releases:
        status_map = {
            "active":      ('<span class="badge badge-active">Active</span>',    "●"),
            "rolled_back": ('<span class="badge badge-rolled">Rolled Back</span>', "✕"),
            "retired":     ('<span class="badge badge-retired">Retired</span>',   "–"),
        }
        badge, dot = status_map.get(r.status, (r.status, "?"))
        deployed = r.deployed_at.strftime("%Y-%m-%d %H:%M") if r.deployed_at else "—"
        rows_html += f"""
        <tr>
            <td><code class="ver-code">{r.version}</code></td>
            <td><span class="color-dot color-{r.color}"></span> {r.color.title()}</td>
            <td>{r.environment}</td>
            <td>{badge}</td>
            <td class="ts">{deployed}</td>
            <td class="notes-td">{r.notes or "—"}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DeployTrack — {APP_COLOR.title()} / {APP_VERSION}</title>
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  :root{{
    --primary:{th["primary"]};
    --light:{th["light"]};
    --accent:{th["accent"]};
    --gradient:{th["gradient"]};
  }}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f8fafc;color:#1e293b;min-height:100vh;transition:background .3s,color .3s}}
  body.dark{{background:#0f172a;color:#e2e8f0}}
  body.dark .card{{background:#1e293b;border-color:#334155}}
  body.dark table{{background:#1e293b}}
  body.dark th{{background:#0f172a!important;color:#94a3b8}}
  body.dark td{{border-color:#334155;color:#e2e8f0}}
  body.dark .notes-td{{color:#94a3b8}}
  body.dark .ts{{color:#64748b}}
  .header{{background:var(--gradient);color:white;padding:0}}
  .header-inner{{max-width:1100px;margin:0 auto;padding:32px 24px 28px}}
  .header-top{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:20px}}
  .logo{{display:flex;align-items:center;gap:12px}}
  .logo-icon{{font-size:32px}}
  .logo-text{{font-size:22px;font-weight:800;letter-spacing:-.5px}}
  .logo-sub{{font-size:12px;opacity:.75;margin-top:1px}}
  .env-pill{{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);border-radius:20px;padding:6px 14px;font-size:13px;font-weight:600}}
  .pulse{{width:8px;height:8px;border-radius:50%;background:#4ade80;box-shadow:0 0 0 0 rgba(74,222,128,.4);animation:pulse 2s infinite}}
  @keyframes pulse{{0%{{box-shadow:0 0 0 0 rgba(74,222,128,.4)}}70%{{box-shadow:0 0 0 8px rgba(74,222,128,0)}}100%{{box-shadow:0 0 0 0 rgba(74,222,128,0)}}}}
  .stats{{display:flex;gap:24px;flex-wrap:wrap}}
  .stat{{background:rgba(255,255,255,.12);border-radius:10px;padding:14px 20px;min-width:140px}}
  .stat-val{{font-size:26px;font-weight:800;line-height:1}}
  .stat-lbl{{font-size:12px;opacity:.75;margin-top:4px}}
  .main{{max-width:1100px;margin:0 auto;padding:28px 24px}}
  .feature-banner{{display:flex;align-items:center;gap:14px;background:var(--gradient);color:white;border-radius:12px;padding:14px 18px;margin-bottom:24px;flex-wrap:wrap}}
  .card{{background:white;border-radius:14px;border:1px solid #e2e8f0;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:24px;overflow:hidden}}
  .card-title{{font-size:15px;font-weight:700;padding:16px 20px 0;margin-bottom:12px}}
  table{{width:100%;border-collapse:collapse}}
  th{{background:#f8fafc;font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.5px;padding:10px 16px;text-align:left;border-bottom:1px solid #e2e8f0}}
  td{{padding:12px 16px;border-bottom:1px solid #f1f5f9;font-size:13px;vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#f8fafc}}
  body.dark tr:hover td{{background:#293548}}
  .ver-code{{background:#f1f5f9;color:var(--primary);padding:2px 7px;border-radius:5px;font-family:monospace;font-size:12px;font-weight:700}}
  .badge{{font-size:11px;font-weight:700;padding:3px 9px;border-radius:20px;letter-spacing:.3px}}
  .badge-active{{background:#dcfce7;color:#15803d}}
  .badge-rolled{{background:#fee2e2;color:#b91c1c}}
  .badge-retired{{background:#f3f4f6;color:#6b7280}}
  .color-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;vertical-align:middle;margin-right:4px}}
  .color-blue{{background:#3b82f6}}
  .color-green{{background:#22c55e}}
  .ts{{color:#94a3b8;font-size:12px}}
  .notes-td{{color:#64748b;font-size:12px;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .add-form{{padding:16px 20px;border-top:1px solid #e2e8f0;display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}}
  .form-group{{display:flex;flex-direction:column;gap:5px}}
  .form-group label{{font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase}}
  .form-group input,.form-group select{{padding:7px 10px;border:1px solid #cbd5e1;border-radius:7px;font-size:13px;background:white;color:#1e293b;min-width:120px}}
  body.dark .form-group input,body.dark .form-group select{{background:#334155;border-color:#475569;color:#e2e8f0}}
  .btn-add{{padding:7px 16px;background:var(--primary);color:white;border:none;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap;transition:opacity .15s;align-self:flex-end}}
  .btn-add:hover{{opacity:.85}}
  .footer{{text-align:center;padding:20px;font-size:12px;color:#94a3b8}}
  @media(max-width:640px){{.stats{{gap:12px}}.stat{{min-width:110px;padding:11px 14px}}}}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div class="header-top">
      <div class="logo">
        <span class="logo-icon">🚀</span>
        <div>
          <div class="logo-text">DeployTrack</div>
          <div class="logo-sub">Release management dashboard</div>
        </div>
      </div>
      <div class="env-pill">
        <span class="pulse"></span>
        {th["label"]} / {APP_VERSION} &nbsp;·&nbsp; {APP_ENV.upper()}
      </div>
    </div>
    <div class="stats">
      <div class="stat">
        <div class="stat-val" style="color:{th["dot_color"]}">{APP_VERSION}</div>
        <div class="stat-lbl">Active Version</div>
      </div>
      <div class="stat">
        <div class="stat-val" style="color:{th["dot_color"]}">{APP_COLOR.title()}</div>
        <div class="stat-lbl">Active Environment</div>
      </div>
      <div class="stat">
        <div class="stat-val" id="req-counter">{_request_count}</div>
        <div class="stat-lbl">Requests Served</div>
      </div>
      <div class="stat">
        <div class="stat-val" id="uptime-val">{uptime}</div>
        <div class="stat-lbl">Uptime</div>
      </div>
    </div>
  </div>
</div>

<div class="main">

  {v2_feature_html}

  <div class="card">
    <div class="card-title">Release History</div>
    <table>
      <thead>
        <tr>
          <th>Version</th>
          <th>Color</th>
          <th>Environment</th>
          <th>Status</th>
          <th>Deployed At</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody id="releases-tbody">
        {rows_html}
      </tbody>
    </table>
    <div class="add-form">
      <div class="form-group">
        <label>Version</label>
        <input id="f-ver" type="text" placeholder="v2.1" style="width:90px">
      </div>
      <div class="form-group">
        <label>Color</label>
        <select id="f-color">
          <option value="blue">Blue</option>
          <option value="green">Green</option>
        </select>
      </div>
      <div class="form-group">
        <label>Environment</label>
        <select id="f-env">
          <option value="production">Production</option>
          <option value="staging">Staging</option>
        </select>
      </div>
      <div class="form-group" style="flex:1">
        <label>Notes</label>
        <input id="f-notes" type="text" placeholder="Optional notes..." style="width:100%">
      </div>
      <button class="btn-add" onclick="addRelease()">+ Add Release</button>
    </div>
  </div>

  <div class="card" style="padding:18px 20px">
    <div style="font-size:13px;font-weight:700;margin-bottom:10px;">API Endpoints</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;font-size:12px;font-family:monospace">
      <code style="background:#f1f5f9;padding:4px 10px;border-radius:6px;color:var(--primary)">GET /health</code>
      <code style="background:#f1f5f9;padding:4px 10px;border-radius:6px;color:var(--primary)">GET /version</code>
      <code style="background:#f1f5f9;padding:4px 10px;border-radius:6px;color:var(--primary)">GET /api/releases</code>
      <code style="background:#f1f5f9;padding:4px 10px;border-radius:6px;color:var(--primary)">POST /api/releases</code>
      <code style="background:#f1f5f9;padding:4px 10px;border-radius:6px;color:var(--primary)">PATCH /api/releases/{{id}}</code>
      <code style="background:#f1f5f9;padding:4px 10px;border-radius:6px;color:var(--primary)">GET /docs</code>
    </div>
  </div>

</div>

<div class="footer">DeployTrack &nbsp;·&nbsp; {APP_COLOR.title()} Environment &nbsp;·&nbsp; {APP_VERSION} &nbsp;·&nbsp; Built for Zero-Downtime DevOps Learning</div>

<script>
function addRelease() {{
  const ver   = document.getElementById('f-ver').value.trim();
  const color = document.getElementById('f-color').value;
  const env   = document.getElementById('f-env').value;
  const notes = document.getElementById('f-notes').value.trim();
  if (!ver) {{ alert('Enter a version'); return; }}
  fetch('/api/releases', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ version: ver, color, environment: env, notes }})
  }}).then(r => r.json()).then(() => location.reload());
}}

function toggleDark() {{
  document.body.classList.toggle('dark');
  const btn = document.getElementById('dmBtn');
  if (btn) btn.textContent = document.body.classList.contains('dark') ? 'Disable Dark Mode' : 'Enable Dark Mode';
}}

// Live counter update
setInterval(() => {{
  fetch('/stats').then(r => r.json()).then(d => {{
    const el = document.getElementById('req-counter');
    if (el) el.textContent = d.requests;
  }}).catch(() => {{}});
}}, 3000);
</script>
</body>
</html>"""

# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    bump()
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "color": APP_COLOR,
        "environment": APP_ENV,
        "uptime_seconds": int(time.time() - _start_time),
    }

@app.get("/version")
async def version():
    bump()
    return {
        "version": APP_VERSION,
        "color": APP_COLOR,
        "environment": APP_ENV,
        "build": f"{APP_COLOR}-{APP_VERSION}",
    }

@app.get("/stats")
async def stats():
    return {
        "requests": _request_count,
        "uptime_seconds": int(time.time() - _start_time),
        "version": APP_VERSION,
        "color": APP_COLOR,
    }

@app.get("/api/releases")
async def list_releases():
    bump()
    db = Session()
    try:
        rows = db.query(Release).order_by(Release.deployed_at.desc()).all()
        return [
            {
                "id": r.id,
                "version": r.version,
                "color": r.color,
                "environment": r.environment,
                "status": r.status,
                "deployed_at": r.deployed_at.isoformat() if r.deployed_at else None,
                "notes": r.notes,
            }
            for r in rows
        ]
    finally:
        db.close()

@app.post("/api/releases", status_code=201)
async def create_release(payload: ReleaseCreate):
    bump()
    db = Session()
    try:
        r = Release(
            version=payload.version,
            color=payload.color,
            environment=payload.environment,
            notes=payload.notes,
        )
        db.add(r)
        db.commit()
        db.refresh(r)
        return {"id": r.id, "version": r.version, "color": r.color, "status": r.status}
    finally:
        db.close()

@app.patch("/api/releases/{release_id}")
async def update_release(release_id: int, payload: ReleaseUpdate):
    bump()
    db = Session()
    try:
        r = db.query(Release).filter(Release.id == release_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="Release not found")
        r.status = payload.status
        if payload.notes:
            r.notes = payload.notes
        db.commit()
        return {"id": r.id, "status": r.status}
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
