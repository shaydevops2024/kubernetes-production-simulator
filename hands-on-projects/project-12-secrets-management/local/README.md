# local/ — Run the Full Stack Locally

This folder contains the Docker Compose setup to run the entire secrets management platform on your machine. Use this as your learning sandbox before deploying to Kubernetes.

---

## Prerequisites

- Docker Engine 20.10+ and Docker Compose v2
- 2 GB free RAM (Vault + PostgreSQL + Dashboard)
- Ports 5555, 8200, 5432 available

---

## Quick Start

```bash
cd hands-on-projects/project-12-secrets-management/local
docker compose up --build
```

Wait about 30 seconds for Vault to initialize. Then:

| Service | URL | Notes |
|---------|-----|-------|
| **Dashboard UI** | http://localhost:5555 | Your main interface |
| **Vault UI** | http://localhost:8200/ui | Token: `root` |
| **Vault API** | http://localhost:8200 | Token: `root` |
| **PostgreSQL** | localhost:5432 | User: `vault_admin`, DB: `appdb` |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Your Browser                                                    │
└─────────┬──────────────────────────────────────────────────────-─┘
          │
    :5555 │                                   :8200/ui
    ┌─────▼──────────────┐            ┌────────────────────┐
    │  Dashboard (Python) │◄──────────►│  HashiCorp Vault   │
    │  /api/* endpoints   │  hvac SDK  │                    │
    └────────────────────┘            │  ┌─────────────┐   │
                                      │  │  KV v2      │   │
                                      │  │  Database   │   │
                                      │  │  PKI        │   │
                                      │  │  Transit    │   │
                                      │  │  Audit      │   │
                                      │  └─────────────┘   │
                                      └─────────┬──────────┘
                                                │ dynamic creds
                                       ┌────────▼──────────┐
                                       │   PostgreSQL       │
                                       │   (appdb)          │
                                       └───────────────────-┘
```

---

## DevOps Tasks

Work through these tasks in order. Each one teaches a different aspect of Vault.

---

### Task 1 — Explore the KV Secrets Store

**What you're learning:** How secrets are stored and versioned in Vault.

```bash
# See the demo secrets written by the init script
docker compose exec vault vault kv list secret/

# List secrets in the app/ path
docker compose exec vault vault kv list secret/app

# Read a specific secret
docker compose exec vault vault kv get secret/app/database

# Read only the password field
docker compose exec vault vault kv get -field=password secret/app/database
```

**Questions:**
- What's the difference between `kv get` and `kv get -field=...`?
- Run `vault kv put secret/app/database password=newpassword123` then `vault kv get secret/app/database`. What changed?
- Run `vault kv metadata get secret/app/database`. How many versions exist?
- How would you retrieve version 1 of a secret after overwriting it?

---

### Task 2 — Dynamic Database Credentials

**What you're learning:** Why dynamic secrets are superior to static passwords.

```bash
# Request a fresh set of credentials for the app-role
docker compose exec vault vault read database/creds/app-role

# Request another set — observe the username is different
docker compose exec vault vault read database/creds/app-role

# Look at what PostgreSQL users exist right now
docker compose exec postgres psql -U vault_admin -d appdb -c "\du"

# Use the credentials to actually connect
# (replace with the username/password Vault gave you)
docker compose exec postgres psql -U v-root-app-role-XXXXX -d appdb -c "SELECT * FROM users;"
```

**Questions:**
- What happens to the PostgreSQL user after the lease expires (default: 1 hour)?
- How would you revoke a set of credentials immediately? Try: `vault lease revoke <lease-id>`
- What's the difference between `app-role` (1h TTL) and `readonly-role` (30m TTL)?
- In a real app, when would you request new credentials — at startup, per-request, or on a schedule?

```bash
# Revoke a lease immediately (simulate incident response)
# First get a lease ID:
LEASE=$(docker compose exec vault vault read -field=lease_id database/creds/readonly-role)
echo "Lease: $LEASE"

# Revoke it immediately
docker compose exec vault vault lease revoke $LEASE

# Verify the PostgreSQL user is gone
docker compose exec postgres psql -U vault_admin -d appdb -c "\du"
```

---

### Task 3 — PKI Certificate Management

**What you're learning:** Vault as a Certificate Authority (CA).

```bash
# Issue a certificate for a service
docker compose exec vault vault write pki_int/issue/app-role \
    common_name="api.vault.local" \
    ttl="24h"

# Issue a short-lived cert (simulates best practice: 1-hour certs)
docker compose exec vault vault write pki_int/issue/app-role \
    common_name="microservice-a.vault.local" \
    ttl="1h"

# List issued certificates
docker compose exec vault vault list pki_int/certs

# View root CA
docker compose exec vault vault read pki/cert/ca
```

**Questions:**
- Why use 1-hour certificates instead of 1-year certificates?
- If a private key is compromised, what must you do with a long-lived cert vs. a 1-hour cert?
- How does automatic certificate rotation via Vault eliminate the "certificate expired at 3 AM" incident?

---

### Task 4 — Transit Encryption (Encryption-as-a-Service)

**What you're learning:** How to encrypt data without your app managing encryption keys.

```bash
# Encrypt sensitive data
echo -n "user@example.com" | base64 | \
  docker compose exec -T vault vault write transit/encrypt/app-key plaintext=-

# Decrypt it back (replace with your ciphertext)
docker compose exec vault vault write transit/decrypt/app-key \
    ciphertext="vault:v1:your-ciphertext-here"

# Rotate the encryption key (old data can still be decrypted with old key version)
docker compose exec vault vault write -f transit/keys/app-key/rotate

# Re-encrypt existing ciphertext with the new key version
docker compose exec vault vault write transit/rewrap/app-key \
    ciphertext="vault:v1:your-ciphertext-here"

# List key versions
docker compose exec vault vault read transit/keys/app-key
```

**Questions:**
- After rotating the key, what does `vault:v2:...` vs `vault:v1:...` mean in the ciphertext?
- Why can Vault still decrypt `vault:v1:...` ciphertext after rotating to v2?
- What does `min_decryption_version` do? Try setting it to 2.

---

### Task 5 — Audit Logging

**What you're learning:** Every action in Vault is logged.

```bash
# Tail the audit log in real time
docker compose exec vault tail -f /vault/logs/audit.log

# In another terminal, make some Vault requests
docker compose exec vault vault kv get secret/app/database
docker compose exec vault vault read database/creds/app-role

# View the audit entries (formatted)
docker compose exec vault sh -c "cat /vault/logs/audit.log | head -5" | \
  python3 -c "import sys,json; [print(json.dumps(json.loads(l),indent=2)) for l in sys.stdin if l.strip()]"
```

**Questions:**
- What fields does each audit entry contain?
- How would you know WHO requested a secret if multiple services use the same token?
- What's the difference between a `request` and `response` audit entry?
- What would happen if the audit device fails to write? (Hint: Vault refuses requests)

---

### Task 6 — Vault Policies (RBAC)

**What you're learning:** Restricting what each identity can access.

```bash
# View existing policies
docker compose exec vault vault policy list
docker compose exec vault vault policy read dashboard-policy
docker compose exec vault vault policy read readonly-policy

# Create a token with only the readonly policy
READONLY_TOKEN=$(docker compose exec vault vault token create \
    -policy=readonly-policy \
    -ttl=30m \
    -field=token)
echo "Readonly token: $READONLY_TOKEN"

# Try to read a secret with the readonly token — should work
VAULT_TOKEN=$READONLY_TOKEN docker compose exec -e VAULT_TOKEN=$READONLY_TOKEN vault \
    vault kv get secret/app/config

# Try to write a secret — should be denied
VAULT_TOKEN=$READONLY_TOKEN docker compose exec -e VAULT_TOKEN=$READONLY_TOKEN vault \
    vault kv put secret/app/config env=production

# Try to request DB credentials — should be denied (only read, not db)
VAULT_TOKEN=$READONLY_TOKEN docker compose exec -e VAULT_TOKEN=$READONLY_TOKEN vault \
    vault read database/creds/app-role
```

---

### Task 7 — Break-Glass Procedure

**What you're learning:** Emergency access when Vault is unavailable.

```bash
# Simulate Vault going down
docker compose stop vault

# Observe dashboard behavior — what happens to the UI?
curl http://localhost:5555/api/vault/status

# Document: what would you do in a real incident?
# 1. Do apps still work? (short-term, if they cached credentials)
# 2. How long until dynamic credentials expire and break the app?
# 3. Where are your backup/break-glass credentials stored?

# Bring Vault back up
docker compose start vault

# In production, you'd need:
# - Unseal keys (stored in HSM or split across multiple teams)
# - An emergency policy token stored offline
# - Runbook for the on-call engineer
```

---

## Common Issues

### `vault-init` exits with error
```bash
docker compose logs vault-init
```
The init script depends on both `vault` and `postgres` being healthy. Check those services first.

### Dashboard shows "Vault Unreachable"
Vault may still be initializing. Check:
```bash
docker compose logs vault
docker compose logs vault-init
```

### Dynamic credentials failing
```bash
docker compose exec vault vault read database/config/postgres
```
Ensure the `postgres` hostname resolves and the connection is valid.

### Port 5555 already in use
```bash
lsof -i :5555
# or change the port in docker-compose.yml
```

---

## Cleanup

```bash
# Stop and remove all containers + volumes
docker compose down -v

# Just stop (keep volumes)
docker compose down
```

---

## Next Step

→ **[Deploy to Kubernetes](../main/README.md)** — run Vault in a real cluster
