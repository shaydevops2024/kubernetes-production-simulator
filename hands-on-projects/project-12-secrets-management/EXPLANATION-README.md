# Project 12 — Enterprise Secrets Management (Vault): Explained

---

## 1. The App

You are deploying a **production-grade secrets management platform** using **HashiCorp Vault**. The main principle: secrets never live in your code, config files, or environment variables — Vault is the single source of truth.

The **Secrets Dashboard** is a FastAPI application that visually demonstrates all of Vault's capabilities in real time:

```
Browser
  └─▶ Secrets Dashboard (:5555)
        │  Vault Status · KV Secrets · DB Credentials · PKI
        │  Transit Encryption · Audit Logs
        ▼
    HashiCorp Vault
        ├── KV v2 (secrets/)      ← Store static app secrets
        ├── Database Engine       ← Generate dynamic, expiring DB credentials
        ├── PKI Engine            ← Issue TLS certificates on demand
        ├── Transit Engine        ← Encrypt/decrypt data without storing it
        ├── Audit Logging         ← Immutable log: who accessed what, when
        └── Kubernetes Auth       ← Pods authenticate using their service account token
              │
              ▼
          PostgreSQL
          (Vault manages its own users — creates + deletes them automatically)
```

| Vault Engine | What it does |
|-------------|-------------|
| **KV v2** | Key-Value store for static secrets (DB URLs, API keys, feature flags). Versioned — you can roll back |
| **Database Engine** | Generates unique username/password per app per request. Credentials expire after TTL (e.g., 1 hour) |
| **PKI Engine** | Issues TLS certificates. Private key never leaves Vault |
| **Transit Engine** | Encrypts/decrypts data on demand — Vault never stores the plaintext |
| **Kubernetes Auth** | Pods authenticate by presenting their K8s service account token — no password needed |

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-12-secrets-management/local/

docker compose up --build
```

Vault initialization runs automatically via `vault/init.sh` which:
- Unseals Vault (development mode: auto-unseal)
- Enables KV v2, Database, PKI, Transit engines
- Configures the Database engine to manage PostgreSQL users
- Creates sample secrets

| UI | URL |
|----|-----|
| Secrets Dashboard | http://localhost:5555 |
| Vault UI | http://localhost:8200 (token: root) |

**Explore the dashboard:**
1. **Vault Status** — shows initialized/sealed state, version, uptime
2. **KV Secrets** — browse and read static secrets stored in `secrets/`
3. **Dynamic DB Credentials** — click "Generate Credentials" — watch Vault create a new user in PostgreSQL with a TTL
4. **PKI** — issue a TLS certificate for any domain name
5. **Transit** — encrypt a string, then decrypt it (Vault never stores it)
6. **Audit Logs** — every operation logged with timestamp, path, response code

**CLI interaction:**
```bash
# Set Vault address and token
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root

# Read a static secret
vault kv get secrets/app/database

# Generate dynamic DB credentials (creates a new Postgres user)
vault read database/creds/app-role

# Issue a TLS certificate
vault write pki/issue/internal-ca \
  common_name=myapp.internal \
  ttl=24h

# Encrypt data with Transit
vault write transit/encrypt/app-key \
  plaintext=$(echo "my secret data" | base64)

# Decrypt it back
vault write transit/decrypt/app-key ciphertext=<vault:v1:...>
```

### Phase 2 — Deploy to Kubernetes

```bash
cd hands-on-projects/project-12-secrets-management/main/

# Install Vault via Helm (dev mode for learning, HA for production)
helm install vault hashicorp/vault -n vault --create-namespace \
  -f solution/vault/helm-values.yaml

# Wait for Vault to be ready
kubectl wait pod/vault-0 --for=condition=Ready -n vault --timeout=120s

# Initialize and unseal (first time only)
kubectl exec -n vault vault-0 -- vault operator init -key-shares=1 -key-threshold=1

# Save the unseal key and root token from output!

# Unseal
kubectl exec -n vault vault-0 -- vault operator unseal <unseal-key>

# Configure Vault (enable engines, policies, K8s auth)
kubectl exec -n vault vault-0 -- vault login <root-token>
kubectl apply -f solution/vault-config/

# Deploy the Secrets Dashboard
kubectl apply -f solution/app/

# The app uses Vault Agent Sidecar injection — no hardcoded tokens in pods
```

---

## 3. How to Test It

### KV Secrets Test

```bash
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root

# Write a secret
vault kv put secrets/app/config \
  db_password=supersecret \
  api_key=abc123 \
  feature_x=enabled

# Read it back
vault kv get secrets/app/config

# Read specific field
vault kv get -field=db_password secrets/app/config

# List secret versions
vault kv metadata get secrets/app/config
```

### Dynamic Database Credentials Test

```bash
# Generate credentials (Vault creates a new Postgres user)
CREDS=$(vault read -format=json database/creds/app-role)
echo $CREDS | jq .

DB_USER=$(echo $CREDS | jq -r .data.username)
DB_PASS=$(echo $CREDS | jq -r .data.password)
LEASE_ID=$(echo $CREDS | jq -r .lease_id)

# Verify user was created in PostgreSQL
docker compose exec postgres \
  psql -U admin -d appdb -c "\du" | grep $DB_USER

# Connect using the dynamic credentials
psql postgresql://$DB_USER:$DB_PASS@localhost:5432/appdb -c "SELECT 1;"

# After TTL expires (default 1 hour), the user is automatically deleted
# Renew the lease if you need it longer
vault lease renew $LEASE_ID

# Revoke immediately when done
vault lease revoke $LEASE_ID
```

### PKI Certificate Test

```bash
# Issue a certificate
CERT=$(vault write -format=json pki/issue/internal-ca \
  common_name=api.internal.example.com \
  ttl=1h)

echo $CERT | jq -r .data.certificate | openssl x509 -text -noout | grep -E "Subject:|Not After"
```

### Transit Encryption Test

```bash
# Encrypt
PLAINTEXT=$(echo "my sensitive data" | base64)
CIPHERTEXT=$(vault write -format=json transit/encrypt/app-key \
  plaintext=$PLAINTEXT | jq -r .data.ciphertext)

echo "Ciphertext: $CIPHERTEXT"

# Decrypt
vault write transit/decrypt/app-key ciphertext=$CIPHERTEXT \
  | jq -r .data.plaintext | base64 -d
# Should output: my sensitive data
```

### Audit Log Test

```bash
# Enable file audit log
vault audit enable file file_path=/vault/logs/audit.log

# Make any Vault operation
vault kv get secrets/app/config

# Check audit log
docker compose exec vault cat /vault/logs/audit.log | jq .
```

### Kubernetes Auth Test (K8s phase)

```bash
# Verify a pod can authenticate using its service account
kubectl exec -n secrets-app deploy/secrets-dashboard -- \
  curl -s --request POST \
    --data '{"jwt": "'$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)'", "role": "app-role"}' \
    http://vault.vault.svc:8200/v1/auth/kubernetes/login | jq .auth.client_token
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **HashiCorp Vault** | Secrets management platform | Central secret store; runs engines for KV, Database, PKI, Transit |
| **Vault CLI** | Operations interface | `vault kv`, `vault read`, `vault write` — all management operations |
| **Vault Agent** | Secret injection (K8s) | Sidecar that authenticates to Vault and writes secrets to shared volume |
| **PostgreSQL** | Backend for Database engine | Vault's Database engine connects and creates/revokes users dynamically |
| **hvac (Python)** | Vault client library | Dashboard app uses hvac to query Vault API from Python |
| **Helm** | K8s installation | `helm install vault hashicorp/vault` |
| **Kubernetes Auth** | Pod identity | Pods authenticate to Vault using their ServiceAccount JWT — no passwords |
| **Docker Compose** | Local development | Runs Vault (dev mode), PostgreSQL, and Dashboard |

### Key Secrets Management Concepts Practiced

- **Dynamic secrets**: Credentials are generated per-request and expire — no long-lived passwords
- **Least privilege**: Each app gets a Vault policy scoped to only its own secrets
- **Secret rotation**: Database engine auto-rotates the root credential Vault uses to manage Postgres
- **Encryption as a service**: Transit engine — your app never handles encryption keys
- **Audit trail**: Immutable log of every secret access — critical for compliance

---

## 5. Troubleshooting

### Vault is sealed on startup

```bash
# Vault starts sealed after a restart — check seal status
vault status

# Unseal with key (you saved this during init)
vault operator unseal <unseal-key>

# In Docker Compose dev mode, Vault auto-unseals — check if it's in dev mode
docker compose exec vault vault status | grep "Dev Mode"
```

### Dynamic DB credentials not working

```bash
# Check Database engine configuration
vault read database/config/postgresql

# Verify Vault can connect to PostgreSQL
vault write -f database/rotate-root/postgresql

# Check if Vault has CREATE ROLE permission on Postgres
docker compose exec postgres \
  psql -U admin -d appdb -c "\du admin"
# admin must have CREATEROLE privilege

# Check Vault Database engine logs
vault read sys/health
docker compose logs vault | grep database
```

### Dashboard shows "Vault unreachable"

```bash
# Check VAULT_ADDR environment variable
docker compose exec secrets-dashboard env | grep VAULT

# Test connectivity from dashboard container
docker compose exec secrets-dashboard \
  curl http://vault:8200/v1/sys/health

# Check if Vault token is valid
docker compose exec secrets-dashboard \
  curl http://vault:8200/v1/auth/token/lookup-self \
    -H "X-Vault-Token: $VAULT_TOKEN"
```

### Kubernetes: Pod can't authenticate to Vault

```bash
# Verify Kubernetes auth method is enabled
vault auth list | grep kubernetes

# Check the service account token is mounted
kubectl exec -n secrets-app deploy/secrets-dashboard -- \
  ls /var/run/secrets/kubernetes.io/serviceaccount/

# Verify the role binding
vault read auth/kubernetes/role/app-role
# Check: bound_service_account_names and bound_service_account_namespaces

# Check Vault Agent sidecar logs
kubectl logs -n secrets-app deploy/secrets-dashboard -c vault-agent
```

### Vault Helm Pod stuck in Init state (K8s)

```bash
# Check if Vault is unsealed
kubectl exec -n vault vault-0 -- vault status

# If sealed, unseal it
kubectl exec -n vault vault-0 -- \
  vault operator unseal <unseal-key>

# Check Vault pod logs
kubectl logs -n vault vault-0
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-12-secrets-management/local/

# Stop everything
docker compose down

# Full reset (removes Vault storage and PostgreSQL data)
docker compose down -v
```

### Kubernetes

```bash
# Delete app namespace
kubectl delete namespace secrets-app

# Uninstall Vault
helm uninstall vault -n vault
kubectl delete namespace vault

# Remove Vault CRDs if any
kubectl delete crd vaultauditbackends.vault.banzaicloud.com 2>/dev/null || true

# Note: Save your unseal keys somewhere secure before deleting!
# There is no recovery if you lose both the storage and the unseal keys
```
