"""
Enterprise Secrets Management Dashboard
FastAPI app that connects to HashiCorp Vault and exposes a UI + REST API
to demonstrate dynamic secrets, PKI, transit encryption, and audit logging.
"""

import os
import json
import datetime
from typing import Optional

import hvac
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse

# ── Configuration ────────────────────────────────────────────────────────────

VAULT_ADDR  = os.getenv("VAULT_ADDR",  "http://localhost:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "root")
APP_PORT    = int(os.getenv("PORT", "5555"))

app = FastAPI(title="Vault Secrets Dashboard", version="1.0.0")


def get_vault_client() -> hvac.Client:
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    return client


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "vault_addr": VAULT_ADDR}


# ── Vault Status ──────────────────────────────────────────────────────────────

@app.get("/api/vault/status")
def vault_status():
    try:
        client = get_vault_client()
        status = client.sys.read_health_status(method="GET")
        seal   = client.sys.read_seal_status()
        return {
            "initialized": seal.get("initialized", False),
            "sealed":      seal.get("sealed", True),
            "version":     status.get("version", "unknown"),
            "cluster_name":status.get("cluster_name", ""),
            "server_time": datetime.datetime.utcnow().isoformat() + "Z",
            "reachable":   True,
        }
    except Exception as e:
        return {"reachable": False, "error": str(e)}


# ── KV Secrets ────────────────────────────────────────────────────────────────

@app.get("/api/secrets")
def list_secrets(path: str = ""):
    """List secrets at the given path in the KV v2 store."""
    try:
        client = get_vault_client()
        list_path = path.strip("/") or ""
        result = client.secrets.kv.v2.list_secrets(
            path=list_path,
            mount_point="secret",
        )
        return {"keys": result["data"]["keys"], "path": list_path}
    except (hvac.exceptions.InvalidPath, hvac.exceptions.Forbidden):
        return {"keys": [], "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/secrets/{path:path}")
def read_secret(path: str):
    """Read a specific secret from KV v2."""
    try:
        client = get_vault_client()
        result = client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point="secret",
        )
        data    = result["data"]["data"]
        meta    = result["data"]["metadata"]
        return {
            "path":       path,
            "data":       data,
            "version":    meta.get("version"),
            "created_at": meta.get("created_time"),
        }
    except hvac.exceptions.InvalidPath:
        raise HTTPException(status_code=404, detail=f"Secret not found: {path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/secrets/{path:path}")
def write_secret(path: str, body: dict = Body(...)):
    """Create or update a secret in KV v2."""
    try:
        client = get_vault_client()
        client.secrets.kv.v2.create_or_update_secret(
            path=path,
            secret=body,
            mount_point="secret",
        )
        return {"message": f"Secret written to secret/{path}", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/secrets/{path:path}")
def delete_secret(path: str):
    """Delete (destroy latest version of) a secret."""
    try:
        client = get_vault_client()
        client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=path,
            mount_point="secret",
        )
        return {"message": f"Secret {path} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dynamic Database Credentials ─────────────────────────────────────────────

@app.post("/api/database/credentials")
def get_database_credentials(role: str = "app-role"):
    """
    Request a fresh set of dynamic PostgreSQL credentials from Vault.
    Vault will create a new user in PostgreSQL, return the credentials,
    and automatically revoke the user when the TTL expires.
    """
    try:
        client = get_vault_client()
        result = client.secrets.database.generate_credentials(name=role)
        lease  = result.get("lease_id", "")
        ttl    = result.get("lease_duration", 0)
        data   = result.get("data", {})
        return {
            "username":       data.get("username"),
            "password":       data.get("password"),
            "lease_id":       lease,
            "lease_duration": ttl,
            "expires_in":     f"{ttl // 60} minutes",
            "role":           role,
            "note": "These credentials are temporary. Vault will revoke them when the lease expires.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/database/roles")
def list_database_roles():
    """List available database roles."""
    try:
        client = get_vault_client()
        result = client.secrets.database.list_roles()
        return {"roles": result["data"].get("keys", [])}
    except Exception as e:
        return {"roles": [], "error": str(e)}


# ── PKI Certificate Management ────────────────────────────────────────────────

@app.post("/api/pki/certificate")
def issue_certificate(
    common_name: str = Body("dashboard.vault.local", embed=True),
    ttl: str         = Body("24h", embed=True),
):
    """Issue a TLS certificate from Vault's built-in PKI engine."""
    try:
        client = get_vault_client()
        result = client.secrets.pki.generate_certificate(
            name="app-role",
            common_name=common_name,
            extra_params={"ttl": ttl},
            mount_point="pki_int",
        )
        data = result["data"]
        return {
            "serial_number": data.get("serial_number"),
            "common_name":   common_name,
            "expiration":    data.get("expiration"),
            "certificate":   data.get("certificate", ""),
            "ca_chain":      data.get("ca_chain", []),
            "ttl":           ttl,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pki/ca")
def get_ca_certificate():
    """Get the root CA certificate."""
    try:
        client = get_vault_client()
        result = client.secrets.pki.read_ca_certificate(mount_point="pki")
        return {"ca_certificate": result}
    except Exception as e:
        return {"ca_certificate": None, "error": str(e)}


# ── Transit Encryption ────────────────────────────────────────────────────────

@app.post("/api/transit/encrypt")
def encrypt_data(plaintext: str = Body(..., embed=True), key_name: str = Body("app-key", embed=True)):
    """Encrypt data using Vault's Transit secrets engine (Vault as a service)."""
    try:
        import base64
        client    = get_vault_client()
        b64_input = base64.b64encode(plaintext.encode()).decode()
        result    = client.secrets.transit.encrypt_data(
            name=key_name,
            plaintext=b64_input,
        )
        ciphertext = result["data"]["ciphertext"]
        return {
            "original":   plaintext,
            "ciphertext": ciphertext,
            "key_name":   key_name,
            "note": "Only Vault can decrypt this. Your app never sees the key.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transit/decrypt")
def decrypt_data(ciphertext: str = Body(..., embed=True), key_name: str = Body("app-key", embed=True)):
    """Decrypt data using Vault's Transit secrets engine."""
    try:
        import base64
        client = get_vault_client()
        result = client.secrets.transit.decrypt_data(
            name=key_name,
            ciphertext=ciphertext,
        )
        plaintext_b64 = result["data"]["plaintext"]
        plaintext     = base64.b64decode(plaintext_b64).decode()
        return {"plaintext": plaintext, "key_name": key_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transit/keys")
def list_transit_keys():
    """List available encryption keys in Transit engine."""
    try:
        client = get_vault_client()
        result = client.secrets.transit.list_keys()
        return {"keys": result["data"].get("keys", [])}
    except Exception as e:
        return {"keys": [], "error": str(e)}


# ── Audit Logs ────────────────────────────────────────────────────────────────

@app.get("/api/audit/devices")
def list_audit_devices():
    """List configured audit devices."""
    try:
        client  = get_vault_client()
        devices = client.sys.list_enabled_audit_devices()
        return {"devices": list(devices.keys())}
    except Exception as e:
        return {"devices": [], "error": str(e)}


# ── Mounted Engines ───────────────────────────────────────────────────────────

@app.get("/api/engines")
def list_secret_engines():
    """List all mounted secrets engines."""
    try:
        client  = get_vault_client()
        mounts  = client.sys.list_mounted_secrets_engines()
        engines = []
        for path, info in mounts.items():
            engines.append({
                "path":        path,
                "type":        info.get("type"),
                "description": info.get("description", ""),
            })
        return {"engines": engines}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Lease Management ──────────────────────────────────────────────────────────

@app.post("/api/leases/revoke")
def revoke_lease(lease_id: str = Body(..., embed=True)):
    """Revoke a lease (immediately invalidate dynamic credentials)."""
    try:
        client = get_vault_client()
        client.sys.revoke_lease(lease_id=lease_id)
        return {"message": f"Lease {lease_id} revoked. Credentials are now invalid."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dashboard HTML ────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vault Secrets Dashboard</title>
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#0f0e17;--surface:#1a1a2e;--surface2:#16213e;--border:#2a2a4a;
    --primary:#7c3aed;--primary-light:#a78bfa;--green:#10b981;--red:#ef4444;
    --yellow:#f59e0b;--text:#e2e8f0;--muted:#94a3b8;--code:#1e293b;
  }
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
  .topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
  .topbar-left{display:flex;align-items:center;gap:12px}
  .logo{font-size:22px;font-weight:800;color:var(--primary-light)}
  .vault-badge{font-size:11px;padding:3px 10px;border-radius:99px;font-weight:700;letter-spacing:.5px}
  .badge-green{background:#064e3b;color:#34d399}
  .badge-red{background:#450a0a;color:#fca5a5}
  .badge-yellow{background:#451a03;color:#fbbf24}
  .nav{display:flex;gap:4px}
  .nav-btn{background:none;border:none;color:var(--muted);padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500;transition:all .15s}
  .nav-btn:hover,.nav-btn.active{background:rgba(124,58,237,.15);color:var(--primary-light)}
  .main{max-width:1200px;margin:0 auto;padding:28px 24px}
  .panel{display:none}
  .panel.active{display:block}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  .grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
  @media(max-width:900px){.grid-2,.grid-3{grid-template-columns:1fr}}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}
  .card-title{font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-bottom:16px;display:flex;align-items:center;gap:8px}
  .status-row{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--surface2);border-radius:8px;margin-bottom:8px}
  .status-label{font-size:13px;color:var(--muted)}
  .status-val{font-size:13px;font-weight:600}
  .status-val.ok{color:var(--green)}
  .status-val.warn{color:var(--yellow)}
  .status-val.err{color:var(--red)}
  .big-status{text-align:center;padding:32px 20px}
  .big-icon{font-size:56px;margin-bottom:12px}
  .big-label{font-size:20px;font-weight:700;margin-bottom:6px}
  .big-sub{font-size:13px;color:var(--muted)}
  .section-title{font-size:18px;font-weight:700;margin-bottom:20px;color:var(--text)}
  .btn{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:8px;font-size:13px;font-weight:600;border:none;cursor:pointer;transition:all .15s}
  .btn-primary{background:var(--primary);color:white}
  .btn-primary:hover{background:#6d28d9}
  .btn-secondary{background:var(--surface2);color:var(--text);border:1px solid var(--border)}
  .btn-secondary:hover{background:var(--border)}
  .btn-danger{background:#7f1d1d;color:#fca5a5;border:1px solid #991b1b}
  .btn-danger:hover{background:#991b1b}
  .btn-green{background:#064e3b;color:#34d399;border:1px solid #065f46}
  .btn-green:hover{background:#065f46}
  .input{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text);font-size:13px;outline:none;transition:border .15s;font-family:inherit}
  .input:focus{border-color:var(--primary)}
  .label{font-size:12px;font-weight:600;color:var(--muted);margin-bottom:6px;display:block}
  .form-group{margin-bottom:14px}
  .result-box{background:var(--code);border:1px solid var(--border);border-radius:8px;padding:14px;font-family:'Courier New',Courier,monospace;font-size:12px;color:#a5b4fc;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow-y:auto;margin-top:12px}
  .cred-card{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:16px;margin-top:12px}
  .cred-title{font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.6px;margin-bottom:10px}
  .cred-row{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg);border-radius:6px;margin-bottom:6px}
  .cred-key{font-size:12px;color:var(--muted)}
  .cred-val{font-size:12px;font-weight:600;color:var(--green);font-family:monospace}
  .cred-val.secret{filter:blur(4px);transition:filter .2s;cursor:pointer}
  .cred-val.secret:hover{filter:none}
  .ttl-bar{height:4px;background:var(--border);border-radius:2px;margin-top:12px;overflow:hidden}
  .ttl-fill{height:100%;background:var(--green);border-radius:2px;transition:width 1s linear}
  .tag{display:inline-flex;font-size:11px;padding:3px 10px;border-radius:6px;font-weight:600;margin:2px}
  .tag-purple{background:rgba(124,58,237,.15);color:var(--primary-light)}
  .tag-green{background:rgba(16,185,129,.1);color:#34d399}
  .tag-yellow{background:rgba(245,158,11,.1);color:#fbbf24}
  .tag-red{background:rgba(239,68,68,.1);color:#fca5a5}
  .engine-row{display:flex;align-items:center;gap:12px;padding:12px 14px;background:var(--surface2);border-radius:8px;margin-bottom:8px;border:1px solid var(--border)}
  .engine-path{font-size:13px;font-weight:700;color:var(--text);font-family:monospace}
  .engine-type{font-size:11px;color:var(--muted)}
  .secret-row{display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--surface2);border-radius:8px;margin-bottom:6px;cursor:pointer;border:1px solid var(--border);transition:border .15s}
  .secret-row:hover{border-color:var(--primary)}
  .secret-name{font-size:13px;font-weight:600;font-family:monospace}
  .audit-entry{padding:10px 14px;background:var(--surface2);border-radius:8px;margin-bottom:6px;border-left:3px solid var(--border);font-family:monospace;font-size:11px;color:var(--muted)}
  .audit-entry.type-request{border-color:#7c3aed}
  .audit-entry.type-response{border-color:#059669}
  .audit-op{font-size:12px;font-weight:700;color:var(--text);margin-bottom:4px}
  .loading{color:var(--muted);font-size:13px;padding:20px 0;text-align:center}
  .alert{padding:12px 16px;border-radius:8px;font-size:13px;margin-bottom:16px}
  .alert-success{background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.3);color:#34d399}
  .alert-error{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);color:#fca5a5}
  .alert-info{background:rgba(124,58,237,.1);border:1px solid rgba(124,58,237,.3);color:var(--primary-light)}
  .divider{border:none;border-top:1px solid var(--border);margin:20px 0}
  .flex{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .tabs{display:flex;gap:4px;margin-bottom:20px;border-bottom:1px solid var(--border);padding-bottom:0}
  .tab{padding:8px 16px;font-size:13px;font-weight:600;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .15s}
  .tab.active{color:var(--primary-light);border-bottom-color:var(--primary-light)}
  .tab:hover{color:var(--text)}
  textarea.input{min-height:80px;resize:vertical}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <div class="logo">🔐 VaultDash</div>
    <span class="vault-badge badge-yellow" id="vault-status-badge">Connecting...</span>
  </div>
  <nav class="nav">
    <button class="nav-btn active" onclick="showPanel('overview')">Overview</button>
    <button class="nav-btn" onclick="showPanel('kv')">KV Secrets</button>
    <button class="nav-btn" onclick="showPanel('dynamic')">Dynamic Creds</button>
    <button class="nav-btn" onclick="showPanel('pki')">PKI</button>
    <button class="nav-btn" onclick="showPanel('transit')">Transit</button>
    <button class="nav-btn" onclick="showPanel('audit')">Audit</button>
  </nav>
</div>

<div class="main">

  <!-- ── Overview ──────────────────────────────────────────────────── -->
  <div class="panel active" id="panel-overview">
    <div class="section-title">Vault Status</div>
    <div class="grid-3">
      <div class="card" id="card-vault-status">
        <div class="big-status">
          <div class="big-icon" id="vault-icon">⏳</div>
          <div class="big-label" id="vault-state-label">Loading...</div>
          <div class="big-sub" id="vault-version-label"></div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">🗄 Mounted Engines</div>
        <div id="engines-list"><div class="loading">Loading...</div></div>
      </div>
      <div class="card">
        <div class="card-title">ℹ Server Info</div>
        <div id="server-info-list"><div class="loading">Loading...</div></div>
      </div>
    </div>

    <hr class="divider">
    <div class="section-title">Quick Reference</div>
    <div class="grid-2">
      <div class="card">
        <div class="card-title">🔑 Key Concepts</div>
        <div style="display:flex;flex-direction:column;gap:8px;font-size:13px;">
          <div class="status-row"><span class="status-label">KV v2</span><span class="status-val ok">Versioned key-value store</span></div>
          <div class="status-row"><span class="status-label">Dynamic Secrets</span><span class="status-val ok">Generated per-request, auto-expire</span></div>
          <div class="status-row"><span class="status-label">PKI Engine</span><span class="status-val ok">Vault as Certificate Authority</span></div>
          <div class="status-row"><span class="status-label">Transit Engine</span><span class="status-val ok">Encrypt without managing keys</span></div>
          <div class="status-row"><span class="status-label">Leases</span><span class="status-val ok">Every secret has a TTL</span></div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">⚡ Quick Actions</div>
        <div style="display:flex;flex-direction:column;gap:10px;">
          <button class="btn btn-primary" onclick="showPanel('dynamic')">🔄 Request DB Credentials</button>
          <button class="btn btn-secondary" onclick="showPanel('pki')">📜 Issue Certificate</button>
          <button class="btn btn-secondary" onclick="showPanel('transit')">🔒 Encrypt Data</button>
          <button class="btn btn-secondary" onclick="showPanel('kv')">📁 Browse Secrets</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ── KV Secrets ─────────────────────────────────────────────────── -->
  <div class="panel" id="panel-kv">
    <div class="section-title">KV v2 Secrets Store</div>
    <div class="alert alert-info">📁 Secrets are stored at <code>secret/</code> — this is the KV v2 mount point. Each secret can have multiple versions.</div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title">📋 Browse Secrets</div>
        <div class="flex" style="margin-bottom:14px">
          <input class="input" id="kv-path-input" placeholder="e.g. app/database" style="flex:1">
          <button class="btn btn-primary" onclick="listSecrets()">List</button>
          <button class="btn btn-secondary" onclick="readSecret()">Read</button>
        </div>
        <div id="kv-list-result"><div class="loading">Enter a path and click List</div></div>
      </div>

      <div class="card">
        <div class="card-title">✏️ Write Secret</div>
        <div class="form-group">
          <label class="label">Path</label>
          <input class="input" id="kv-write-path" placeholder="e.g. myapp/config">
        </div>
        <div class="form-group">
          <label class="label">Secret data (JSON)</label>
          <textarea class="input" id="kv-write-data" placeholder='{"username": "admin", "password": "s3cr3t"}'></textarea>
        </div>
        <button class="btn btn-primary" onclick="writeSecret()">Write Secret</button>
        <div id="kv-write-result"></div>
      </div>
    </div>

  </div>

  <!-- ── Dynamic Credentials ────────────────────────────────────────── -->
  <div class="panel" id="panel-dynamic">
    <div class="section-title">Dynamic Database Credentials</div>
    <div class="alert alert-info">
      💡 <strong>Why dynamic secrets?</strong> Instead of sharing a single static password that never changes, Vault creates a unique username/password pair <em>for each request</em>. The credentials automatically expire after the TTL. This means a leaked credential is useless after a few minutes.
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title">🔄 Request Credentials</div>
        <div class="form-group">
          <label class="label">Database Role</label>
          <select class="input" id="db-role-select">
            <option value="app-role">app-role (read-write, 1 hour TTL)</option>
            <option value="readonly-role">readonly-role (read-only, 30 min TTL)</option>
          </select>
        </div>
        <button class="btn btn-primary" onclick="requestDbCredentials()">🔑 Generate Credentials</button>
        <div id="db-cred-result"></div>
      </div>

      <div class="card">
        <div class="card-title">📚 How It Works</div>
        <div style="font-size:13px;line-height:1.8;color:var(--muted)">
          <div style="margin-bottom:8px;">1. App requests credentials from Vault</div>
          <div style="margin-bottom:8px;">2. Vault connects to PostgreSQL using its own admin credentials</div>
          <div style="margin-bottom:8px;">3. Vault executes a CREATE ROLE statement with a generated username/password</div>
          <div style="margin-bottom:8px;">4. Vault returns credentials + a lease ID</div>
          <div style="margin-bottom:8px;">5. App uses credentials until lease expires</div>
          <div style="margin-bottom:8px;">6. Vault automatically runs DROP ROLE when lease expires</div>
          <div style="padding:10px;background:var(--bg);border-radius:6px;margin-top:8px">
            <div style="color:var(--green);font-size:11px;font-weight:700">RESULT:</div>
            <div style="font-size:12px;margin-top:4px">PostgreSQL never has long-lived credentials. Each connection uses a unique, time-limited identity.</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:20px">
      <div class="card-title">🚫 Revoke a Lease</div>
      <div class="alert alert-info" style="font-size:12px">Enter a lease ID to immediately revoke credentials (simulate incident response)</div>
      <div class="flex">
        <input class="input" id="revoke-lease-id" placeholder="database/creds/app-role/xxxxx" style="flex:1">
        <button class="btn btn-danger" onclick="revokeLease()">Revoke Now</button>
      </div>
      <div id="revoke-result"></div>
    </div>
  </div>

  <!-- ── PKI ───────────────────────────────────────────────────────── -->
  <div class="panel" id="panel-pki">
    <div class="section-title">PKI Certificate Management</div>
    <div class="alert alert-info">
      📜 <strong>Vault as your CA.</strong> Instead of buying certificates or managing OpenSSL, Vault issues TLS certificates on demand. Services get short-lived certs that auto-rotate — no more certificate expiry incidents.
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title">🏭 Issue Certificate</div>
        <div class="form-group">
          <label class="label">Common Name (domain)</label>
          <input class="input" id="pki-cn" value="myservice.vault.local">
        </div>
        <div class="form-group">
          <label class="label">TTL</label>
          <select class="input" id="pki-ttl">
            <option value="1h">1 hour (short-lived, best practice)</option>
            <option value="24h" selected>24 hours</option>
            <option value="72h">72 hours</option>
            <option value="720h">30 days</option>
          </select>
        </div>
        <button class="btn btn-primary" onclick="issueCertificate()">📜 Issue Certificate</button>
        <div id="pki-result"></div>
      </div>

      <div class="card">
        <div class="card-title">🔐 Root CA</div>
        <button class="btn btn-secondary" onclick="loadCA()" style="margin-bottom:14px">Load CA Certificate</button>
        <div id="pki-ca-result"><div class="loading">Click to load</div></div>
      </div>
    </div>
  </div>

  <!-- ── Transit ───────────────────────────────────────────────────── -->
  <div class="panel" id="panel-transit">
    <div class="section-title">Transit Encryption Engine</div>
    <div class="alert alert-info">
      🔒 <strong>Encryption as a service.</strong> Your app doesn't manage keys — Vault does. You send plaintext, get back ciphertext. Keys never leave Vault. This protects you even if your database is breached.
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title">🔒 Encrypt Data</div>
        <div class="form-group">
          <label class="label">Plaintext to encrypt</label>
          <textarea class="input" id="transit-plaintext" placeholder="e.g. user@example.com or a credit card number">sensitive data here</textarea>
        </div>
        <div class="form-group">
          <label class="label">Encryption Key</label>
          <input class="input" id="encrypt-key" value="app-key">
        </div>
        <button class="btn btn-primary" onclick="encryptData()">🔒 Encrypt</button>
        <div id="encrypt-result"></div>
      </div>

      <div class="card">
        <div class="card-title">🔓 Decrypt Data</div>
        <div class="form-group">
          <label class="label">Ciphertext (vault:v1:...)</label>
          <textarea class="input" id="transit-ciphertext" placeholder="vault:v1:..."></textarea>
        </div>
        <div class="form-group">
          <label class="label">Encryption Key</label>
          <input class="input" id="decrypt-key" value="app-key">
        </div>
        <button class="btn btn-primary" onclick="decryptData()">🔓 Decrypt</button>
        <div id="decrypt-result"></div>
      </div>
    </div>

    <div class="card" style="margin-top:20px">
      <div class="card-title">🗝 Available Keys</div>
      <div id="transit-keys-list"><div class="loading">Loading...</div></div>
    </div>
  </div>

  <!-- ── Audit ─────────────────────────────────────────────────────── -->
  <div class="panel" id="panel-audit">
    <div class="section-title">Audit & Compliance</div>
    <div class="alert alert-info">
      📊 <strong>Every action is logged.</strong> Vault writes an immutable audit log of every request — who asked for what, when, and from which IP. Required for SOC2, PCI-DSS, HIPAA compliance.
    </div>

    <div class="card">
      <div class="card-title">📡 Audit Devices</div>
      <div id="audit-devices-list"><div class="loading">Loading...</div></div>
    </div>

    <div class="card" style="margin-top:20px">
      <div class="card-title">📄 Recent Activity (audit log tail)</div>
      <div class="alert alert-info" style="font-size:12px;margin-bottom:14px">
        The audit log is written to <code>/vault/logs/audit.log</code> inside the Vault container.<br>
        Run: <code>docker compose exec vault tail -20 /vault/logs/audit.log | python3 -m json.tool</code>
      </div>
      <button class="btn btn-secondary" onclick="fetchAuditDevices()">🔄 Refresh Devices</button>
    </div>

    <div class="card" style="margin-top:20px">
      <div class="card-title">🚨 Break-Glass Procedure</div>
      <div style="font-size:13px;line-height:1.9;color:var(--muted)">
        <strong style="color:var(--red)">Emergency: Vault is sealed or unreachable</strong>
        <div style="margin-top:10px;background:var(--code);border-radius:8px;padding:14px;font-family:monospace;font-size:12px;color:#a5b4fc;">
# 1. Check Vault status<br>
vault status<br><br>
# 2. If sealed — unseal with unseal keys<br>
vault operator unseal &lt;unseal-key-1&gt;<br>
vault operator unseal &lt;unseal-key-2&gt;<br>
vault operator unseal &lt;unseal-key-3&gt;<br><br>
# 3. If using static fallback secrets<br>
kubectl get secret vault-fallback -n secrets-management<br><br>
# 4. Enable break-glass token (stored in HSM or offline)<br>
vault token create -policy=break-glass -ttl=1h<br><br>
# 5. Document the incident<br>
echo "Break-glass used: $(date) by $(whoami)" >> /var/log/break-glass.log
        </div>
      </div>
    </div>
  </div>

</div>

<script>
const API = '';

function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  event.currentTarget.classList.add('active');
  if (name === 'overview') loadOverview();
  if (name === 'transit') loadTransitKeys();
  if (name === 'audit') fetchAuditDevices();
}

function json(obj) {
  return JSON.stringify(obj, null, 2);
}

// ── Load Overview ────────────────────────────────────────────────────────────
async function loadOverview() {
  try {
    const [statusRes, enginesRes] = await Promise.all([
      fetch(API + '/api/vault/status'),
      fetch(API + '/api/engines'),
    ]);
    const status  = await statusRes.json();
    const engines = await enginesRes.json();

    const badge = document.getElementById('vault-status-badge');
    const icon  = document.getElementById('vault-icon');
    const label = document.getElementById('vault-state-label');
    const ver   = document.getElementById('vault-version-label');

    if (!status.reachable) {
      badge.className = 'vault-badge badge-red';
      badge.textContent = 'Unreachable';
      icon.textContent  = '❌';
      label.textContent = 'Vault Unreachable';
      ver.textContent   = status.error || '';
    } else if (status.sealed) {
      badge.className = 'vault-badge badge-yellow';
      badge.textContent = 'Sealed';
      icon.textContent  = '🔒';
      label.textContent = 'Vault is Sealed';
      ver.textContent   = 'Needs unseal keys to operate';
    } else {
      badge.className = 'vault-badge badge-green';
      badge.textContent = 'Active';
      icon.textContent  = '✅';
      label.textContent = 'Vault is Active';
      ver.textContent   = 'Version ' + (status.version || 'unknown');
    }

    // Engines list
    const el = document.getElementById('engines-list');
    if (engines.engines && engines.engines.length) {
      el.innerHTML = engines.engines.map(e =>
        `<div class="engine-row">
          <div>
            <div class="engine-path">${e.path}</div>
            <div class="engine-type">${e.type} ${e.description ? '— ' + e.description : ''}</div>
          </div>
          <span class="tag tag-purple">${e.type}</span>
        </div>`
      ).join('');
    } else {
      el.innerHTML = '<div class="loading">No engines loaded</div>';
    }

    // Server info
    const si = document.getElementById('server-info-list');
    si.innerHTML = [
      ['Initialized', status.initialized ? '✅ Yes' : '❌ No', status.initialized ? 'ok' : 'err'],
      ['Sealed',      status.sealed      ? '⚠ Sealed' : '✅ Unsealed', status.sealed ? 'warn' : 'ok'],
      ['Version',     status.version || 'unknown', ''],
      ['Server Time', status.server_time ? status.server_time.split('T')[1].split('.')[0] + ' UTC' : '–', ''],
      ['Cluster',     status.cluster_name || 'dev-cluster', ''],
      ['Vault Addr',  '${VAULT_ADDR}', ''],
    ].map(([k, v, cls]) =>
      `<div class="status-row"><span class="status-label">${k}</span><span class="status-val ${cls}">${v}</span></div>`
    ).join('');

  } catch(e) {
    document.getElementById('vault-status-badge').textContent = 'Error';
    console.error(e);
  }
}

// ── KV Secrets ───────────────────────────────────────────────────────────────
async function listSecrets() {
  const path   = document.getElementById('kv-path-input').value.trim();
  const result = document.getElementById('kv-list-result');
  result.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const res  = await fetch(API + '/api/secrets?path=' + encodeURIComponent(path));
    const data = await res.json();
    if (data.keys && data.keys.length) {
      result.innerHTML = data.keys.map(k =>
        `<div class="secret-row" onclick="selectSecret('${(path ? path + '/' : '') + k}')">
          <span style="font-size:16px">${k.endsWith('/') ? '📁' : '🔑'}</span>
          <span class="secret-name">${k}</span>
        </div>`
      ).join('');
    } else {
      result.innerHTML = '<div class="loading">No secrets found at this path</div>';
    }
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function selectSecret(path) {
  document.getElementById('kv-path-input').value = path;
  if (!path.endsWith('/')) readSecret();
  else listSecrets();
}

async function readSecret() {
  const path = document.getElementById('kv-path-input').value.trim();
  if (!path) return;
  const result = document.getElementById('kv-list-result');
  result.innerHTML = '<div class="loading">Reading...</div>';
  try {
    const res  = await fetch(API + '/api/secrets/' + path);
    const data = await res.json();
    if (res.status === 404) {
      result.innerHTML = `<div class="alert alert-error">Secret not found: ${path}</div>`;
      return;
    }
    result.innerHTML = `
      <div class="cred-card">
        <div class="cred-title">📁 secret/${path} — version ${data.version}</div>
        ${Object.entries(data.data || {}).map(([k, v]) =>
          `<div class="cred-row">
            <span class="cred-key">${k}</span>
            <span class="cred-val secret" title="click to reveal">${v}</span>
          </div>`
        ).join('')}
        <div style="font-size:11px;color:var(--muted);margin-top:8px">Created: ${data.created_at || 'unknown'}</div>
      </div>`;
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

async function writeSecret() {
  const path   = document.getElementById('kv-write-path').value.trim();
  const rawData = document.getElementById('kv-write-data').value.trim();
  const result = document.getElementById('kv-write-result');
  if (!path || !rawData) {
    result.innerHTML = '<div class="alert alert-error">Path and data are required</div>';
    return;
  }
  let data;
  try { data = JSON.parse(rawData); } catch(e) {
    result.innerHTML = '<div class="alert alert-error">Invalid JSON</div>';
    return;
  }
  try {
    const res  = await fetch(API + '/api/secrets/' + path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const resp = await res.json();
    result.innerHTML = `<div class="alert alert-success">✅ ${resp.message}</div>`;
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// ── Dynamic DB Credentials ────────────────────────────────────────────────────
async function requestDbCredentials() {
  const role   = document.getElementById('db-role-select').value;
  const result = document.getElementById('db-cred-result');
  result.innerHTML = '<div class="loading">Requesting credentials from Vault...</div>';
  try {
    const res  = await fetch(API + '/api/database/credentials', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({role}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    const ttl = data.lease_duration || 3600;
    result.innerHTML = `
      <div class="cred-card" style="margin-top:12px">
        <div class="cred-title">🔑 Dynamic Credentials — Role: ${role}</div>
        <div class="cred-row"><span class="cred-key">Username</span><span class="cred-val">${data.username}</span></div>
        <div class="cred-row"><span class="cred-key">Password</span><span class="cred-val secret" title="click to reveal">${data.password}</span></div>
        <div class="cred-row"><span class="cred-key">Expires in</span><span class="cred-val" style="color:var(--yellow)">${data.expires_in}</span></div>
        <div class="cred-row"><span class="cred-key">Lease ID</span><span class="cred-val" style="font-size:10px;color:var(--muted)">${data.lease_id}</span></div>
        <div class="ttl-bar"><div class="ttl-fill" id="ttl-fill-bar" style="width:100%"></div></div>
        <div style="font-size:11px;color:var(--muted);margin-top:6px">⚠ These credentials will be automatically revoked when the lease expires</div>
        <button class="btn btn-danger" style="margin-top:10px;font-size:11px" onclick="document.getElementById('revoke-lease-id').value='${data.lease_id}';showPanel('dynamic')">🚫 Pre-fill Revoke</button>
      </div>`;
    // animate TTL bar
    let remaining = ttl;
    const interval = setInterval(() => {
      remaining--;
      const pct = (remaining / ttl) * 100;
      const bar = document.getElementById('ttl-fill-bar');
      if (bar) { bar.style.width = pct + '%'; bar.style.background = pct > 50 ? 'var(--green)' : pct > 20 ? 'var(--yellow)' : 'var(--red)'; }
      else clearInterval(interval);
    }, 1000);
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
  }
}

async function revokeLease() {
  const leaseId = document.getElementById('revoke-lease-id').value.trim();
  const result  = document.getElementById('revoke-result');
  if (!leaseId) { result.innerHTML = '<div class="alert alert-error">Enter a lease ID</div>'; return; }
  try {
    const res  = await fetch(API + '/api/leases/revoke', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({lease_id: leaseId}),
    });
    const data = await res.json();
    if (!res.ok) {
      result.innerHTML = `<div class="alert alert-error">❌ ${data.detail || 'Revocation failed'}</div>`;
    } else {
      result.innerHTML = `<div class="alert alert-success">✅ ${data.message}</div>`;
    }
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
  }
}

// ── PKI ────────────────────────────────────────────────────────────────────
async function issueCertificate() {
  const cn     = document.getElementById('pki-cn').value.trim();
  const ttl    = document.getElementById('pki-ttl').value;
  const result = document.getElementById('pki-result');
  result.innerHTML = '<div class="loading">Issuing certificate...</div>';
  try {
    const res  = await fetch(API + '/api/pki/certificate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({common_name: cn, ttl}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    result.innerHTML = `
      <div class="cred-card" style="margin-top:12px">
        <div class="cred-title">📜 Certificate Issued</div>
        <div class="cred-row"><span class="cred-key">Common Name</span><span class="cred-val">${data.common_name}</span></div>
        <div class="cred-row"><span class="cred-key">Serial</span><span class="cred-val" style="font-size:11px">${data.serial_number}</span></div>
        <div class="cred-row"><span class="cred-key">TTL</span><span class="cred-val" style="color:var(--yellow)">${data.ttl}</span></div>
        <div class="cred-row"><span class="cred-key">Expires</span><span class="cred-val" style="color:var(--yellow)">${new Date(data.expiration * 1000).toISOString()}</span></div>
        <div style="font-size:11px;color:var(--muted);margin-top:10px;margin-bottom:4px">Certificate</div>
        <pre style="font-size:10px;font-family:monospace;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px;overflow-x:auto;white-space:pre;word-break:break-all;color:var(--green)">${data.certificate}</pre>
      </div>`;
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
  }
}

async function loadCA() {
  const result = document.getElementById('pki-ca-result');
  result.innerHTML = '<div class="loading">Loading CA...</div>';
  try {
    const res  = await fetch(API + '/api/pki/ca');
    const data = await res.json();
    if (data.ca_certificate) {
      result.innerHTML = `<pre style="font-size:10px;font-family:monospace;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px;overflow-x:auto;white-space:pre;word-break:break-all;color:var(--green)">${data.ca_certificate}</pre>`;
    } else {
      result.innerHTML = `<div class="alert alert-error">CA not configured: ${data.error}</div>`;
    }
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// ── Transit ──────────────────────────────────────────────────────────────────
async function encryptData() {
  const plaintext = document.getElementById('transit-plaintext').value.trim();
  const keyName   = document.getElementById('encrypt-key').value.trim() || 'app-key';
  const result    = document.getElementById('encrypt-result');
  if (!plaintext) return;
  result.innerHTML = '<div class="loading">Encrypting...</div>';
  try {
    const res  = await fetch(API + '/api/transit/encrypt', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({plaintext, key_name: keyName}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    document.getElementById('transit-ciphertext').value = data.ciphertext;
    document.getElementById('decrypt-key').value = keyName;
    result.innerHTML = `
      <div class="cred-card" style="margin-top:12px">
        <div class="cred-title">🔒 Encrypted</div>
        <div class="result-box">${data.ciphertext}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:6px">⬆ Ciphertext auto-filled in Decrypt panel</div>
      </div>`;
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
  }
}

async function decryptData() {
  const ciphertext = document.getElementById('transit-ciphertext').value.trim();
  const keyName    = document.getElementById('decrypt-key').value.trim() || 'app-key';
  const result     = document.getElementById('decrypt-result');
  if (!ciphertext) return;
  result.innerHTML = '<div class="loading">Decrypting...</div>';
  try {
    const res  = await fetch(API + '/api/transit/decrypt', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ciphertext, key_name: keyName}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    result.innerHTML = `
      <div class="cred-card" style="margin-top:12px">
        <div class="cred-title">🔓 Decrypted</div>
        <div class="cred-row"><span class="cred-key">Plaintext</span><span class="cred-val">${data.plaintext}</span></div>
        <div class="cred-row"><span class="cred-key">Key used</span><span class="cred-val">${data.key_name}</span></div>
      </div>`;
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
  }
}

async function loadTransitKeys() {
  const result = document.getElementById('transit-keys-list');
  result.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const res  = await fetch(API + '/api/transit/keys');
    const data = await res.json();
    if (data.keys && data.keys.length) {
      result.innerHTML = data.keys.map(k =>
        `<span class="tag tag-purple" style="font-family:monospace">🔑 ${k}</span>`
      ).join('');
    } else {
      result.innerHTML = '<div class="loading">No keys found — run vault init script first</div>';
    }
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// ── Audit ────────────────────────────────────────────────────────────────────
async function fetchAuditDevices() {
  const result = document.getElementById('audit-devices-list');
  result.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const res  = await fetch(API + '/api/audit/devices');
    const data = await res.json();
    if (data.devices && data.devices.length) {
      result.innerHTML = data.devices.map(d =>
        `<div class="engine-row">
          <span style="font-size:20px">📄</span>
          <div>
            <div class="engine-path">${d}</div>
            <div class="engine-type">Audit device — all requests logged</div>
          </div>
          <span class="tag tag-green">Active</span>
        </div>`
      ).join('');
    } else {
      result.innerHTML = '<div class="alert alert-error">No audit devices configured. Run: vault audit enable file file_path=/vault/logs/audit.log</div>';
    }
  } catch(e) {
    result.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// ── Init ────────────────────────────────────────────────────────────────────
loadOverview();
// Poll vault status every 10s
setInterval(() => {
  const activePanel = document.querySelector('.panel.active');
  if (activePanel && activePanel.id === 'panel-overview') loadOverview();
  else {
    fetch(API + '/api/vault/status').then(r => r.json()).then(s => {
      const badge = document.getElementById('vault-status-badge');
      if (!s.reachable) { badge.className = 'vault-badge badge-red'; badge.textContent = 'Unreachable'; }
      else if (s.sealed) { badge.className = 'vault-badge badge-yellow'; badge.textContent = 'Sealed'; }
      else { badge.className = 'vault-badge badge-green'; badge.textContent = 'Active'; }
    }).catch(() => {});
  }
}, 10000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML.replace("${VAULT_ADDR}", VAULT_ADDR)
