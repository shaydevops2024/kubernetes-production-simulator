"""
RegionWatch — Multi-Region Disaster Recovery Dashboard
=======================================================
A monitoring dashboard that visualises the health and status of a
multi-region deployment.  Two instances run simultaneously:

  • PRIMARY   — the active region that serves real traffic
  • SECONDARY — the standby region ready for failover

Environment variables
---------------------
REGION_NAME        : human label  (e.g. "eu-west-1", "us-east-1")  default: primary
REGION_ROLE        : primary | secondary                             default: primary
DATABASE_URL       : postgresql://user:pass@host:5432/db
REPLICA_DB_URL     : replica URL (populated on secondary)
MINIO_ENDPOINT     : http://minio:9000
MINIO_ACCESS_KEY   : minioadmin
MINIO_SECRET_KEY   : minioadmin
APP_VERSION        : v1
APP_ENV            : production | development
"""

import os
import json
import time
import random
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# ── Configuration ─────────────────────────────────────────────────────────────
REGION_NAME    = os.getenv("REGION_NAME",    "primary")
REGION_ROLE    = os.getenv("REGION_ROLE",    "primary")   # primary | secondary
APP_VERSION    = os.getenv("APP_VERSION",    "v1")
APP_ENV        = os.getenv("APP_ENV",        "production")
DATABASE_URL   = os.getenv("DATABASE_URL",   "")
REPLICA_DB_URL = os.getenv("REPLICA_DB_URL", "")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS   = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET   = os.getenv("MINIO_SECRET_KEY", "minioadmin")

IS_PRIMARY = REGION_ROLE.lower() == "primary"

# ── Prometheus metrics ─────────────────────────────────────────────────────────
request_count    = Counter("regionwatch_requests_total",    "Total HTTP requests",   ["method", "path", "status"])
failover_count   = Counter("regionwatch_failovers_total",   "Total failover events")
replication_lag  = Gauge(  "regionwatch_replication_lag_seconds", "DB replication lag in seconds")
db_health        = Gauge(  "regionwatch_db_healthy",        "Database health (1=up, 0=down)")
backup_age       = Gauge(  "regionwatch_last_backup_age_seconds", "Seconds since last backup")
rto_gauge        = Gauge(  "regionwatch_rto_target_seconds","RTO target in seconds")
rpo_gauge        = Gauge(  "regionwatch_rpo_target_seconds","RPO target in seconds")

rto_gauge.set(300)   # 5 minutes
rpo_gauge.set(3600)  # 1 hour

# ── In-memory state ────────────────────────────────────────────────────────────
START_TIME = datetime.now(timezone.utc)

_state = {
    "active_region":    REGION_ROLE,
    "db_healthy":       True,
    "replication_lag":  0.0,      # seconds
    "last_backup_time": datetime.now(timezone.utc) - timedelta(minutes=23),
    "next_backup_time": datetime.now(timezone.utc) + timedelta(minutes=37),
    "failover_history": [],
    "backup_count":     7,
    "lock": threading.Lock(),
}

# Seed some historical failover events
_state["failover_history"] = [
    {"timestamp": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
     "from_region": "secondary", "to_region": "primary",
     "reason": "Scheduled failback after maintenance", "rto_seconds": 42},
    {"timestamp": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
     "from_region": "primary", "to_region": "secondary",
     "reason": "Primary region network failure simulation", "rto_seconds": 87},
]

# ── Background simulation ──────────────────────────────────────────────────────
def _simulate_metrics():
    """Continuously update simulated metrics in the background."""
    while True:
        time.sleep(5)
        with _state["lock"]:
            # Simulate replication lag (0.05–2.5 s, spikes occasionally)
            base_lag = random.uniform(0.05, 0.5)
            if random.random() < 0.05:
                base_lag = random.uniform(1.5, 2.5)
            _state["replication_lag"] = round(base_lag, 3)
            replication_lag.set(base_lag)

            # Simulate DB health (99.5% uptime)
            _state["db_healthy"] = random.random() > 0.005
            db_health.set(1 if _state["db_healthy"] else 0)

            # Advance backup clock
            now = datetime.now(timezone.utc)
            age = (now - _state["last_backup_time"]).total_seconds()
            backup_age.set(age)
            if age > 3600:   # auto-"backup" every hour
                _state["last_backup_time"] = now
                _state["next_backup_time"] = now + timedelta(hours=1)
                _state["backup_count"] += 1

threading.Thread(target=_simulate_metrics, daemon=True).start()

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="RegionWatch", version=APP_VERSION)

# ── Health endpoint ────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status":      "healthy",
        "region_name": REGION_NAME,
        "region_role": REGION_ROLE,
        "version":     APP_VERSION,
        "uptime":      int((datetime.now(timezone.utc) - START_TIME).total_seconds()),
    }

# ── Prometheus metrics endpoint ────────────────────────────────────────────────
@app.get("/metrics")
def metrics():
    request_count.labels(method="GET", path="/metrics", status=200).inc()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ── Status API ─────────────────────────────────────────────────────────────────
@app.get("/api/status")
def api_status():
    with _state["lock"]:
        now = datetime.now(timezone.utc)
        uptime = int((now - START_TIME).total_seconds())
        last_backup = _state["last_backup_time"]
        next_backup = _state["next_backup_time"]
        backup_age_s = int((now - last_backup).total_seconds())

        return {
            "region_name":      REGION_NAME,
            "region_role":      REGION_ROLE,
            "is_active":        _state["active_region"] == REGION_ROLE,
            "active_region":    _state["active_region"],
            "version":          APP_VERSION,
            "environment":      APP_ENV,
            "uptime_seconds":   uptime,
            "db_healthy":       _state["db_healthy"],
            "replication_lag":  _state["replication_lag"],
            "last_backup_time": last_backup.isoformat(),
            "next_backup_time": next_backup.isoformat(),
            "backup_age_seconds": backup_age_s,
            "backup_count":     _state["backup_count"],
            "rto_target":       300,   # 5 min
            "rpo_target":       3600,  # 1 hour
            "failover_history": list(reversed(_state["failover_history"][-5:])),
        }

# ── Failover simulation ────────────────────────────────────────────────────────
@app.post("/api/failover")
def trigger_failover(reason: Optional[str] = None):
    with _state["lock"]:
        from_region = _state["active_region"]
        to_region   = "secondary" if from_region == "primary" else "primary"
        rto = random.randint(28, 95)

        event = {
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "from_region": from_region,
            "to_region":   to_region,
            "reason":      reason or "Manual failover triggered",
            "rto_seconds": rto,
        }
        _state["active_region"] = to_region
        _state["failover_history"].append(event)
        failover_count.inc()

    return {
        "success":     True,
        "event":       event,
        "new_active":  to_region,
        "rto_seconds": rto,
    }

# ── Backup trigger simulation ──────────────────────────────────────────────────
@app.post("/api/backup")
def trigger_backup():
    with _state["lock"]:
        _state["last_backup_time"] = datetime.now(timezone.utc)
        _state["next_backup_time"] = _state["last_backup_time"] + timedelta(hours=1)
        _state["backup_count"] += 1
        count = _state["backup_count"]
    return {"success": True, "backup_count": count,
            "timestamp": _state["last_backup_time"].isoformat()}

# ── Dashboard HTML ─────────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RegionWatch — DR Dashboard</title>
<style>
  :root {
    --primary:  #6366f1;
    --active:   #10b981;
    --standby:  #64748b;
    --danger:   #ef4444;
    --warn:     #f59e0b;
    --bg:       #0f172a;
    --surface:  #1e293b;
    --border:   #334155;
    --text:     #e2e8f0;
    --muted:    #94a3b8;
    --radius:   12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* ── Top bar ── */
  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 28px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  .topbar-left { display: flex; align-items: center; gap: 12px; }
  .topbar-logo { font-size: 22px; font-weight: 800; color: white; letter-spacing: -0.5px; }
  .topbar-logo span { color: var(--primary); }
  .region-badge {
    padding: 5px 14px;
    border-radius: 50px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .badge-primary  { background: #1d4ed8; color: #bfdbfe; border: 1px solid #3b82f6; }
  .badge-secondary{ background: #374151; color: #d1d5db; border: 1px solid #6b7280; }
  .badge-active   { background: #065f46; color: #6ee7b7; border: 1px solid #10b981; }
  .version-tag    { font-size: 12px; color: var(--muted); background: #0f172a; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--border); }
  .topbar-right   { display: flex; align-items: center; gap: 10px; }
  .clock          { font-size: 13px; color: var(--muted); font-family: monospace; }

  /* ── Main layout ── */
  .main { padding: 24px 28px; display: flex; flex-direction: column; gap: 20px; }

  /* ── Active region banner ── */
  .active-banner {
    border-radius: var(--radius);
    padding: 18px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }
  .active-banner.is-active   { background: linear-gradient(135deg, #064e3b, #065f46); border: 1px solid #10b981; }
  .active-banner.is-standby  { background: linear-gradient(135deg, #1e293b, #334155); border: 1px solid #475569; }
  .banner-label { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }
  .banner-region { font-size: 28px; font-weight: 800; color: white; margin-top: 4px; }
  .banner-status { font-size: 14px; margin-top: 4px; }
  .banner-actions { display: flex; gap: 10px; flex-shrink: 0; }

  /* ── Status grid ── */
  .status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
  }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
  }
  .stat-label { font-size: 12px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-value { font-size: 26px; font-weight: 800; margin-top: 6px; font-family: monospace; }
  .stat-sub   { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .ok     { color: #10b981; }
  .warn   { color: #f59e0b; }
  .danger { color: #ef4444; }
  .info   { color: #6366f1; }

  /* ── Two-column panel ── */
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 800px) { .two-col { grid-template-columns: 1fr; } }

  /* ── Panel ── */
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }
  .panel-header {
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    gap: 8px;
    justify-content: space-between;
  }
  .panel-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }

  /* ── Row items ── */
  .row-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 14px;
    background: #0f172a;
    border-radius: 8px;
    border: 1px solid var(--border);
  }
  .row-key  { font-size: 13px; color: var(--muted); }
  .row-val  { font-size: 13px; font-weight: 600; font-family: monospace; }

  /* ── Progress bar (replication lag) ── */
  .lag-bar-wrap { height: 6px; background: #0f172a; border-radius: 4px; overflow: hidden; margin-top: 6px; }
  .lag-bar      { height: 100%; border-radius: 4px; transition: width .5s, background .5s; }

  /* ── Failover history ── */
  .fo-event {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 14px;
    background: #0f172a;
    border-radius: 8px;
    border-left: 3px solid var(--primary);
    font-size: 12px;
  }
  .fo-event-top { display: flex; justify-content: space-between; align-items: center; }
  .fo-route { font-weight: 700; color: white; font-size: 13px; }
  .fo-ts    { color: var(--muted); font-family: monospace; }
  .fo-rto   { background: #1e293b; padding: 2px 8px; border-radius: 4px; font-weight: 700; color: #6ee7b7; }
  .fo-reason { color: var(--muted); margin-top: 2px; }

  /* ── Buttons ── */
  .btn {
    padding: 9px 18px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 13px;
    cursor: pointer;
    border: none;
    transition: all .15s;
    white-space: nowrap;
  }
  .btn-failover { background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; }
  .btn-failover:hover { background: #991b1b; }
  .btn-backup   { background: #1e3a5f; color: #93c5fd; border: 1px solid #3b82f6; }
  .btn-backup:hover { background: #1d4ed8; color: white; }
  .btn-sm { padding: 6px 12px; font-size: 12px; }

  /* ── RTO/RPO gauges ── */
  .gauge-row { display: flex; gap: 16px; }
  .gauge-box {
    flex: 1;
    background: #0f172a;
    border-radius: 8px;
    padding: 14px 16px;
    border: 1px solid var(--border);
    text-align: center;
  }
  .gauge-label { font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .gauge-value { font-size: 22px; font-weight: 800; font-family: monospace; margin-top: 6px; }
  .gauge-target { font-size: 11px; color: var(--muted); margin-top: 4px; }

  /* ── Backup schedule ── */
  .backup-icon { font-size: 24px; }

  /* ── Footer ── */
  .footer { text-align: center; color: var(--muted); font-size: 12px; padding: 16px; border-top: 1px solid var(--border); margin-top: 8px; }

  /* ── Pulse dot ── */
  .pulse-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .pulse-green { background: #10b981; box-shadow: 0 0 0 3px rgba(16,185,129,.25); animation: pulse 2s infinite; }
  .pulse-red   { background: #ef4444; box-shadow: 0 0 0 3px rgba(239,68,68,.25); animation: pulse 2s infinite; }
  .pulse-gray  { background: #64748b; }
  @keyframes pulse { 0%,100%{ box-shadow: 0 0 0 3px rgba(16,185,129,.25); } 50%{ box-shadow: 0 0 0 6px rgba(16,185,129,.1); } }
</style>
</head>
<body>

<!-- ── Top bar ── -->
<div class="topbar">
  <div class="topbar-left">
    <div class="topbar-logo">Region<span>Watch</span></div>
    <span id="role-badge" class="region-badge badge-primary">loading…</span>
    <span id="active-badge" class="region-badge badge-active" style="display:none;">● ACTIVE</span>
    <span class="version-tag" id="version-tag">v1</span>
  </div>
  <div class="topbar-right">
    <span class="clock" id="clock">--:--:-- UTC</span>
  </div>
</div>

<!-- ── Main ── -->
<div class="main">

  <!-- ── Active region banner ── -->
  <div class="active-banner is-standby" id="active-banner">
    <div>
      <div class="banner-label" id="banner-label">Region Status</div>
      <div class="banner-region" id="banner-region">Loading…</div>
      <div class="banner-status" id="banner-status" style="color:var(--muted)">Fetching status…</div>
    </div>
    <div class="banner-actions">
      <button class="btn btn-backup" onclick="triggerBackup()">📦 Trigger Backup</button>
      <button class="btn btn-failover" onclick="triggerFailover()">⚡ Simulate Failover</button>
    </div>
  </div>

  <!-- ── KPI cards ── -->
  <div class="status-grid">

    <div class="stat-card">
      <div class="stat-label">DB Health</div>
      <div class="stat-value" id="db-health">–</div>
      <div class="stat-sub" id="db-health-sub">Checking…</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Replication Lag</div>
      <div class="stat-value" id="rep-lag">–</div>
      <div class="lag-bar-wrap"><div class="lag-bar" id="lag-bar" style="width:0%;background:#10b981;"></div></div>
      <div class="stat-sub" id="rep-lag-sub">vs 2.5 s max threshold</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Last Backup</div>
      <div class="stat-value info" id="last-backup">–</div>
      <div class="stat-sub" id="backup-sub">Next: –</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Uptime</div>
      <div class="stat-value ok" id="uptime">–</div>
      <div class="stat-sub" id="uptime-sub">This instance</div>
    </div>

  </div>

  <!-- ── Two-column section ── -->
  <div class="two-col">

    <!-- Region details -->
    <div class="panel">
      <div class="panel-header">
        <span>⚙️ Region Details</span>
        <span id="pulse-indicator"><span class="pulse-dot pulse-gray"></span></span>
      </div>
      <div class="panel-body">
        <div class="row-item"><span class="row-key">Region Name</span>     <span class="row-val" id="det-region">–</span></div>
        <div class="row-item"><span class="row-key">Role</span>            <span class="row-val" id="det-role">–</span></div>
        <div class="row-item"><span class="row-key">Active Region</span>   <span class="row-val" id="det-active">–</span></div>
        <div class="row-item"><span class="row-key">Version</span>         <span class="row-val" id="det-version">–</span></div>
        <div class="row-item"><span class="row-key">Environment</span>     <span class="row-val" id="det-env">–</span></div>
        <div class="row-item"><span class="row-key">Backup Count</span>    <span class="row-val ok" id="det-backups">–</span></div>
      </div>
    </div>

    <!-- RTO / RPO -->
    <div class="panel">
      <div class="panel-header"><span>🎯 RTO / RPO Targets</span></div>
      <div class="panel-body">
        <div class="gauge-row">
          <div class="gauge-box">
            <div class="gauge-label">RTO</div>
            <div class="gauge-value ok" id="rto-val">5m</div>
            <div class="gauge-target">Target: ≤ 5 min</div>
            <div class="gauge-target" style="margin-top:4px;color:#10b981;">Recovery Time Objective</div>
          </div>
          <div class="gauge-box">
            <div class="gauge-label">RPO</div>
            <div class="gauge-value ok" id="rpo-val">1h</div>
            <div class="gauge-target">Target: ≤ 1 hour</div>
            <div class="gauge-target" style="margin-top:4px;color:#10b981;">Recovery Point Objective</div>
          </div>
        </div>
        <div class="row-item" style="margin-top:4px;">
          <span class="row-key">Current backup age</span>
          <span class="row-val" id="rpo-current">–</span>
        </div>
        <div class="row-item">
          <span class="row-key">Last failover RTO</span>
          <span class="row-val ok" id="last-rto">–</span>
        </div>
        <p style="font-size:12px;color:var(--muted);line-height:1.6;margin-top:4px;">
          <strong style="color:var(--text);">RTO</strong> = how fast we recover after a failure.<br>
          <strong style="color:var(--text);">RPO</strong> = maximum data loss we can tolerate.
        </p>
      </div>
    </div>

  </div>

  <!-- ── Failover history ── -->
  <div class="panel">
    <div class="panel-header">
      <span>🕐 Failover History</span>
      <span style="font-size:11px;font-weight:400;color:var(--muted);">Last 5 events</span>
    </div>
    <div class="panel-body" id="fo-history">
      <div style="color:var(--muted);font-size:13px;">Loading…</div>
    </div>
  </div>

</div>

<div class="footer">RegionWatch {{ version }} · {{ region_name }} ({{ region_role }}) · Multi-Region DR Simulator</div>

<script>
const REGION_ROLE = "{{ region_role }}";
const REGION_NAME = "{{ region_name }}";

function fmtDuration(seconds) {
  if (seconds < 60)  return seconds + 's';
  if (seconds < 3600) return Math.floor(seconds/60) + 'm ' + (seconds%60) + 's';
  const h = Math.floor(seconds/3600);
  const m = Math.floor((seconds%3600)/60);
  return h + 'h ' + m + 'm';
}

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toUTCString().replace('GMT','UTC');
}

function fmtAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60)   return diff + 's ago';
  if (diff < 3600) return Math.floor(diff/60) + 'm ago';
  return Math.floor(diff/3600) + 'h ago';
}

async function fetchStatus() {
  try {
    const r = await fetch('/api/status');
    if (!r.ok) return;
    const d = await r.json();

    const isActive = d.is_active;

    // Banner
    const banner = document.getElementById('active-banner');
    banner.className = 'active-banner ' + (isActive ? 'is-active' : 'is-standby');
    document.getElementById('banner-label').textContent = isActive ? '● ACTIVE REGION — SERVING TRAFFIC' : '● STANDBY REGION — READY FOR FAILOVER';
    document.getElementById('banner-region').textContent = d.region_name.toUpperCase();
    document.getElementById('banner-status').textContent = isActive
      ? 'This region is currently handling all production traffic'
      : 'This region is on standby. Active region: ' + d.active_region.toUpperCase();

    // Badges
    const roleBadge = document.getElementById('role-badge');
    roleBadge.textContent  = d.region_role.toUpperCase();
    roleBadge.className    = 'region-badge ' + (d.region_role === 'primary' ? 'badge-primary' : 'badge-secondary');
    document.getElementById('active-badge').style.display = isActive ? 'inline-block' : 'none';
    document.getElementById('version-tag').textContent = d.version;

    // DB Health
    const dbEl = document.getElementById('db-health');
    dbEl.textContent = d.db_healthy ? '● UP' : '● DOWN';
    dbEl.className   = 'stat-value ' + (d.db_healthy ? 'ok' : 'danger');
    document.getElementById('db-health-sub').textContent = d.db_healthy ? 'PostgreSQL responding normally' : 'Database not reachable!';

    // Replication lag
    const lag = d.replication_lag;
    const lagEl = document.getElementById('rep-lag');
    lagEl.textContent = lag.toFixed(3) + 's';
    const pct = Math.min((lag / 2.5) * 100, 100);
    const lagColor = lag < 0.5 ? '#10b981' : lag < 1.5 ? '#f59e0b' : '#ef4444';
    lagEl.className = 'stat-value ' + (lag < 0.5 ? 'ok' : lag < 1.5 ? 'warn' : 'danger');
    const lagBar = document.getElementById('lag-bar');
    lagBar.style.width     = pct + '%';
    lagBar.style.background = lagColor;

    // Backup
    const backupAge = d.backup_age_seconds;
    document.getElementById('last-backup').textContent  = fmtDuration(backupAge);
    document.getElementById('backup-sub').textContent   = 'Next: ' + fmtAgo(d.next_backup_time);
    document.getElementById('rpo-current').textContent  = fmtDuration(backupAge);

    // Uptime
    document.getElementById('uptime').textContent     = fmtDuration(d.uptime_seconds);
    document.getElementById('uptime-sub').textContent = 'Since container start';

    // Pulse indicator
    const pulse = document.getElementById('pulse-indicator');
    pulse.innerHTML = '<span class="pulse-dot ' + (isActive ? 'pulse-green' : 'pulse-gray') + '"></span>';

    // Details
    document.getElementById('det-region').textContent  = d.region_name;
    document.getElementById('det-role').textContent    = d.region_role;
    document.getElementById('det-active').textContent  = d.active_region;
    document.getElementById('det-version').textContent = d.version;
    document.getElementById('det-env').textContent     = d.environment;
    document.getElementById('det-backups').textContent = d.backup_count;

    // RTO / RPO
    document.getElementById('rto-val').textContent = fmtDuration(d.rto_target);
    document.getElementById('rpo-val').textContent = fmtDuration(d.rpo_target);

    // Failover history
    const hist = document.getElementById('fo-history');
    if (!d.failover_history || d.failover_history.length === 0) {
      hist.innerHTML = '<div style="color:var(--muted);font-size:13px;">No failover events recorded</div>';
    } else {
      hist.innerHTML = d.failover_history.map(e => `
        <div class="fo-event">
          <div class="fo-event-top">
            <span class="fo-route">${e.from_region.toUpperCase()} → ${e.to_region.toUpperCase()}</span>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="fo-rto">RTO: ${e.rto_seconds}s</span>
              <span class="fo-ts">${fmtAgo(e.timestamp)}</span>
            </div>
          </div>
          <div class="fo-reason">${e.reason}</div>
        </div>
      `).join('');

      // Update last failover RTO
      document.getElementById('last-rto').textContent = d.failover_history[0].rto_seconds + 's';
    }

  } catch (e) {
    console.error('Status fetch error:', e);
  }
}

async function triggerFailover() {
  const reason = prompt('Failover reason (leave blank for "Manual failover triggered"):') || '';
  const r = await fetch('/api/failover?reason=' + encodeURIComponent(reason), { method: 'POST' });
  const d = await r.json();
  alert('Failover complete!\\nNew active region: ' + d.new_active.toUpperCase() + '\\nRTO: ' + d.rto_seconds + 's');
  fetchStatus();
}

async function triggerBackup() {
  const r = await fetch('/api/backup', { method: 'POST' });
  const d = await r.json();
  alert('Backup triggered!\\nTotal backups: ' + d.backup_count);
  fetchStatus();
}

// Clock
function updateClock() {
  document.getElementById('clock').textContent = new Date().toUTCString().replace('GMT','UTC').split(' ').slice(4).join(' ');
}
setInterval(updateClock, 1000);
updateClock();

// Auto-refresh
fetchStatus();
setInterval(fetchStatus, 5000);
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def dashboard():
    html = DASHBOARD_HTML \
        .replace("{{ version }}",     APP_VERSION) \
        .replace("{{ region_name }}", REGION_NAME) \
        .replace("{{ region_role }}", REGION_ROLE)
    request_count.labels(method="GET", path="/", status=200).inc()
    return HTMLResponse(content=html)
