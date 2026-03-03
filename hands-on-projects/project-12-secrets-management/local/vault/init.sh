#!/bin/sh
# Vault Initialization Script
# Runs once after Vault starts in dev mode.
# Configures all secrets engines used by the dashboard.

set -e

VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"

export VAULT_ADDR
export VAULT_TOKEN

echo "==> Waiting for Vault to be ready..."
until vault status > /dev/null 2>&1; do
  echo "    Vault not ready yet, retrying in 2s..."
  sleep 2
done
echo "==> Vault is ready."

# ── 1. KV v2 Secrets Engine ───────────────────────────────────────────────────
echo ""
echo "==> [1/6] Enabling KV v2 secrets engine at secret/..."
vault secrets enable -path=secret kv-v2 2>/dev/null || echo "    KV already enabled"

# Write demo secrets
echo "    Writing demo secrets..."
vault kv put secret/app/database  host=postgres port=5432 dbname=appdb username=appuser password=apppassword123
vault kv put secret/app/config    app_name="VaultDash" env=development debug=true log_level=info
vault kv put secret/app/api-keys  stripe_key=sk_test_demo1234 sendgrid_key=SG.demo.abcdef github_token=ghp_demo123
vault kv put secret/infra/dns     primary=8.8.8.8 secondary=8.8.4.4 domain=vault.local
vault kv put secret/infra/smtp    host=smtp.gmail.com port=587 username=noreply@vault.local password=smtp_secret
echo "    Demo secrets written: app/database, app/config, app/api-keys, infra/dns, infra/smtp"

# ── 2. Database Secrets Engine ────────────────────────────────────────────────
echo ""
echo "==> [2/6] Enabling Database secrets engine..."
vault secrets enable database 2>/dev/null || echo "    Database engine already enabled"

echo "    Configuring PostgreSQL connection..."
vault write database/config/postgres \
    plugin_name=postgresql-database-plugin \
    allowed_roles="app-role,readonly-role" \
    connection_url="postgresql://{{username}}:{{password}}@postgres:5432/appdb?sslmode=disable" \
    username="vault_admin" \
    password="vault_admin_password"

echo "    Creating app-role (read-write, 1h TTL)..."
vault write database/roles/app-role \
    db_name=postgres \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\"; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO \"{{name}}\";" \
    revocation_statements="REASSIGN OWNED BY \"{{name}}\" TO vault_admin; DROP OWNED BY \"{{name}}\"; DROP ROLE IF EXISTS \"{{name}}\";" \
    default_ttl="1h" \
    max_ttl="24h"

echo "    Creating readonly-role (read-only, 30m TTL)..."
vault write database/roles/readonly-role \
    db_name=postgres \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    revocation_statements="REASSIGN OWNED BY \"{{name}}\" TO vault_admin; DROP OWNED BY \"{{name}}\"; DROP ROLE IF EXISTS \"{{name}}\";" \
    default_ttl="30m" \
    max_ttl="1h"

echo "    Database engine configured with 2 roles"

# ── 3. PKI Secrets Engine ─────────────────────────────────────────────────────
echo ""
echo "==> [3/6] Setting up PKI infrastructure (Root CA + Intermediate CA)..."
vault secrets enable pki 2>/dev/null || echo "    PKI already enabled"

vault secrets tune -max-lease-ttl=87600h pki

# Generate root CA
vault write -field=certificate pki/root/generate/internal \
    common_name="Vault Root CA" \
    ttl=87600h > /dev/null
vault write pki/config/urls \
    issuing_certificates="${VAULT_ADDR}/v1/pki/ca" \
    crl_distribution_points="${VAULT_ADDR}/v1/pki/crl"
echo "    Root CA generated"

# Intermediate CA
vault secrets enable -path=pki_int pki 2>/dev/null || echo "    pki_int already enabled"
vault secrets tune -max-lease-ttl=43800h pki_int

# Sign intermediate with root
CSR=$(vault write -field=csr pki_int/intermediate/generate/internal \
    common_name="Vault Intermediate CA" ttl=43800h)
SIGNED=$(echo "$CSR" | vault write -field=certificate pki/root/sign-intermediate \
    csr=- format=pem_bundle ttl=43800h 2>/dev/null || echo "")
if [ -n "$SIGNED" ]; then
    echo "$SIGNED" | vault write pki_int/intermediate/set-signed certificate=-
fi

vault write pki_int/config/urls \
    issuing_certificates="${VAULT_ADDR}/v1/pki_int/ca" \
    crl_distribution_points="${VAULT_ADDR}/v1/pki_int/crl"

vault write pki_int/roles/app-role \
    allowed_domains="vault.local,svc.cluster.local,localhost" \
    allow_subdomains=true \
    allow_localhost=true \
    max_ttl=720h \
    generate_lease=true
echo "    PKI infrastructure ready (Root + Intermediate CA)"

# ── 4. Transit Secrets Engine ─────────────────────────────────────────────────
echo ""
echo "==> [4/6] Enabling Transit secrets engine (encryption-as-a-service)..."
vault secrets enable transit 2>/dev/null || echo "    Transit already enabled"

vault write -f transit/keys/app-key           2>/dev/null || true
vault write -f transit/keys/user-data-key     2>/dev/null || true
vault write -f transit/keys/payment-key       type=rsa-2048 2>/dev/null || true
echo "    Created encryption keys: app-key, user-data-key, payment-key (RSA-2048)"

# ── 5. Audit Logging ──────────────────────────────────────────────────────────
echo ""
echo "==> [5/6] Enabling audit logging to file..."
mkdir -p /vault/logs
vault audit enable file file_path=/vault/logs/audit.log 2>/dev/null || echo "    Audit device already enabled"
echo "    Audit log: /vault/logs/audit.log"

# ── 6. Policies ───────────────────────────────────────────────────────────────
echo ""
echo "==> [6/6] Creating Vault policies..."

# Dashboard policy (used by the app)
vault policy write dashboard-policy - <<EOF
# KV secrets
path "secret/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
# Database credentials
path "database/creds/*" {
  capabilities = ["read"]
}
path "database/roles/*" {
  capabilities = ["list"]
}
# PKI
path "pki_int/issue/*" {
  capabilities = ["create", "update"]
}
path "pki/cert/ca" {
  capabilities = ["read"]
}
# Transit
path "transit/encrypt/*" {
  capabilities = ["create", "update"]
}
path "transit/decrypt/*" {
  capabilities = ["create", "update"]
}
path "transit/keys" {
  capabilities = ["list"]
}
# Sys (for status checks)
path "sys/health" {
  capabilities = ["read", "sudo"]
}
path "sys/mounts" {
  capabilities = ["read"]
}
path "sys/audit" {
  capabilities = ["read", "list"]
}
# Lease revocation
path "sys/leases/revoke" {
  capabilities = ["update"]
}
EOF

# Read-only policy (for demo)
vault policy write readonly-policy - <<EOF
path "secret/data/app/*" {
  capabilities = ["read"]
}
path "database/creds/readonly-role" {
  capabilities = ["read"]
}
EOF

# Break-glass policy (emergency access)
vault policy write break-glass - <<EOF
path "*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
EOF

echo "    Policies created: dashboard-policy, readonly-policy, break-glass"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Vault Initialization Complete!"
echo "=========================================="
echo ""
echo "  Vault UI:        ${VAULT_ADDR}/ui"
echo "  Dashboard:       http://localhost:5555"
echo "  Vault Token:     root  (dev mode only)"
echo ""
echo "  Secrets Engines:"
echo "    secret/     → KV v2   (5 demo secrets)"
echo "    database/   → Dynamic PostgreSQL credentials"
echo "    pki/        → Root Certificate Authority"
echo "    pki_int/    → Intermediate CA (issues certs)"
echo "    transit/    → Encryption keys (3 keys)"
echo ""
echo "  Audit Logging:   /vault/logs/audit.log"
echo "  DB Roles:        app-role (1h), readonly-role (30m)"
echo "  Encryption Keys: app-key, user-data-key, payment-key"
echo "=========================================="
