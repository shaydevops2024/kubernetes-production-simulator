# app/ — Vault Secrets Dashboard

The pre-built application for this project is a **Vault Dashboard** — a single FastAPI service that connects to HashiCorp Vault and exposes both a REST API and a web UI for interacting with all Vault features.

You **do not write this app**. Your job is to containerize it, run it locally with Docker Compose, and eventually deploy it to Kubernetes — all while learning how Vault works behind the scenes.

---

## Service Overview

| Service | Port | Language | Description |
|---------|------|----------|-------------|
| **vault-dashboard** | 5555 | Python / FastAPI | Vault management UI + REST API |
| **vault** | 8200 | HashiCorp Vault | Secrets engine (deployed alongside) |
| **postgres** | 5432 | PostgreSQL | Target DB for dynamic credentials |

---

## What the Dashboard Shows

| Panel | What it demonstrates |
|-------|---------------------|
| **Overview** | Vault health status, mounted engines, cluster info |
| **KV Secrets** | List, read, write, and delete secrets from the KV v2 store |
| **Dynamic Creds** | Request fresh DB credentials with TTL countdown, revoke leases |
| **PKI** | Issue TLS certificates, view root CA |
| **Transit** | Encrypt and decrypt data using Vault's encryption-as-a-service |
| **Audit** | View configured audit devices, break-glass procedures |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard HTML UI |
| GET | `/health` | App health check |
| GET | `/api/vault/status` | Vault seal/init/version status |
| GET | `/api/engines` | List mounted secrets engines |
| GET | `/api/secrets?path=` | List secrets at a KV path |
| GET | `/api/secrets/{path}` | Read a specific secret |
| POST | `/api/secrets/{path}` | Write a secret (JSON body) |
| DELETE | `/api/secrets/{path}` | Delete a secret |
| POST | `/api/database/credentials` | Request dynamic DB credentials |
| GET | `/api/database/roles` | List available database roles |
| POST | `/api/pki/certificate` | Issue a TLS certificate |
| GET | `/api/pki/ca` | Get root CA certificate |
| POST | `/api/transit/encrypt` | Encrypt data via Transit engine |
| POST | `/api/transit/decrypt` | Decrypt data via Transit engine |
| GET | `/api/transit/keys` | List Transit encryption keys |
| GET | `/api/audit/devices` | List audit devices |
| POST | `/api/leases/revoke` | Revoke a Vault lease |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VAULT_ADDR` | `http://localhost:8200` | Vault server address |
| `VAULT_TOKEN` | `root` | Vault authentication token |
| `PORT` | `5555` | Port the dashboard listens on |

---

## Running the App Standalone

```bash
cd app/
pip install -r requirements.txt

# Vault must be running and accessible
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root

uvicorn main:app --host 0.0.0.0 --port 5555
```

Access the dashboard at: http://localhost:5555

---

## Questions to Think About

1. **Why is `VAULT_TOKEN=root` bad for production?** What should be used instead?
2. **What happens if Vault is down?** How does the dashboard handle it?
3. **How does the app know which secrets engine to use?** Where is that configured?
4. **Could you add a second service to this project** that retrieves its DB credentials from Vault instead of having them hardcoded?

---

## Next Step

→ **[Run the full stack locally](../local/README.md)** — Vault + PostgreSQL + Dashboard with Docker Compose
