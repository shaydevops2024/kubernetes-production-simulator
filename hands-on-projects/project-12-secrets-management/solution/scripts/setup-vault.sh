#!/bin/bash
# setup-vault.sh
# Configures Vault in Kubernetes with all secrets engines, policies,
# and Kubernetes auth. Run this after Vault is initialized and unsealed.
#
# Usage:
#   export VAULT_ADDR=http://localhost:8200   # port-forward first
#   export VAULT_TOKEN=<root-token>
#   ./setup-vault.sh

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"
NAMESPACE="${NAMESPACE:-secrets-management}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres.secrets-management.svc.cluster.local}"
POSTGRES_USER="${POSTGRES_USER:-vault_admin}"
POSTGRES_PASS="${POSTGRES_PASS:-vault_admin_password_change_in_prod}"
POSTGRES_DB="${POSTGRES_DB:-appdb}"

export VAULT_ADDR VAULT_TOKEN

echo "================================================="
echo "  Vault Setup Script"
echo "  VAULT_ADDR: $VAULT_ADDR"
echo "  Namespace:  $NAMESPACE"
echo "================================================="

# ── Verify Vault is reachable ─────────────────────────────────────────────────
echo ""
echo "[1/8] Checking Vault status..."
vault status || { echo "ERROR: Vault is unreachable or sealed. Unseal it first."; exit 1; }

# ── KV v2 ─────────────────────────────────────────────────────────────────────
echo ""
echo "[2/8] Enabling KV v2 secrets engine..."
vault secrets enable -path=secret kv-v2 2>/dev/null && echo "  KV v2 enabled at secret/" || echo "  KV v2 already enabled"

vault kv put secret/app/database \
    host="${POSTGRES_HOST}" \
    port=5432 \
    dbname="${POSTGRES_DB}" \
    username=appuser \
    password=placeholder_replaced_by_dynamic_secrets

vault kv put secret/app/config \
    app_name="VaultDash" \
    env=production \
    log_level=info

echo "  Demo secrets written"

# ── Database Engine ───────────────────────────────────────────────────────────
echo ""
echo "[3/8] Configuring Database secrets engine..."
vault secrets enable database 2>/dev/null && echo "  Database engine enabled" || echo "  Database engine already enabled"

vault write database/config/postgres \
    plugin_name=postgresql-database-plugin \
    allowed_roles="app-role,readonly-role" \
    connection_url="postgresql://{{username}}:{{password}}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=disable" \
    username="${POSTGRES_USER}" \
    password="${POSTGRES_PASS}"

vault write database/roles/app-role \
    db_name=postgres \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\"; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO \"{{name}}\";" \
    revocation_statements="DROP ROLE IF EXISTS \"{{name}}\";" \
    default_ttl="1h" \
    max_ttl="24h"

vault write database/roles/readonly-role \
    db_name=postgres \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    revocation_statements="DROP ROLE IF EXISTS \"{{name}}\";" \
    default_ttl="30m" \
    max_ttl="1h"

echo "  Roles configured: app-role (1h), readonly-role (30m)"

# ── PKI Engine ────────────────────────────────────────────────────────────────
echo ""
echo "[4/8] Setting up PKI (Root CA + Intermediate CA)..."
vault secrets enable pki 2>/dev/null || true
vault secrets tune -max-lease-ttl=87600h pki

vault write -field=certificate pki/root/generate/internal \
    common_name="Vault Root CA" \
    issuer_name="root-2024" \
    ttl=87600h > /dev/null

vault write pki/config/urls \
    issuing_certificates="${VAULT_ADDR}/v1/pki/ca" \
    crl_distribution_points="${VAULT_ADDR}/v1/pki/crl"

vault secrets enable -path=pki_int pki 2>/dev/null || true
vault secrets tune -max-lease-ttl=43800h pki_int

CSR=$(vault write -field=csr pki_int/intermediate/generate/internal \
    common_name="Vault Intermediate CA" ttl=43800h)

echo "$CSR" | vault write -field=certificate pki/root/sign-intermediate \
    csr=- format=pem_bundle ttl=43800h | \
    vault write pki_int/intermediate/set-signed certificate=-

vault write pki_int/config/urls \
    issuing_certificates="${VAULT_ADDR}/v1/pki_int/ca" \
    crl_distribution_points="${VAULT_ADDR}/v1/pki_int/crl"

vault write pki_int/roles/app-role \
    allowed_domains="vault.local,svc.cluster.local,localhost" \
    allow_subdomains=true \
    allow_localhost=true \
    max_ttl=720h \
    generate_lease=true

echo "  PKI infrastructure ready"

# ── Transit Engine ────────────────────────────────────────────────────────────
echo ""
echo "[5/8] Enabling Transit encryption engine..."
vault secrets enable transit 2>/dev/null || true
vault write -f transit/keys/app-key 2>/dev/null || true
vault write -f transit/keys/user-data-key 2>/dev/null || true
echo "  Transit keys created: app-key, user-data-key"

# ── Audit Logging ─────────────────────────────────────────────────────────────
echo ""
echo "[6/8] Enabling audit logging..."
vault audit enable file file_path=/vault/audit/audit.log 2>/dev/null || echo "  Audit already enabled"

# ── Policies ──────────────────────────────────────────────────────────────────
echo ""
echo "[7/8] Creating policies..."
vault policy write dashboard-policy - <<'EOF'
path "secret/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "database/creds/*" {
  capabilities = ["read"]
}
path "database/roles" {
  capabilities = ["list"]
}
path "pki_int/issue/*" {
  capabilities = ["create", "update"]
}
path "pki/cert/ca" {
  capabilities = ["read"]
}
path "transit/encrypt/*" {
  capabilities = ["create", "update"]
}
path "transit/decrypt/*" {
  capabilities = ["create", "update"]
}
path "transit/keys" {
  capabilities = ["list"]
}
path "sys/health" {
  capabilities = ["read", "sudo"]
}
path "sys/mounts" {
  capabilities = ["read"]
}
path "sys/audit" {
  capabilities = ["read", "list"]
}
path "sys/leases/revoke" {
  capabilities = ["update"]
}
EOF

vault policy write break-glass - <<'EOF'
path "*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
EOF

echo "  Policies created: dashboard-policy, break-glass"

# ── Kubernetes Auth ───────────────────────────────────────────────────────────
echo ""
echo "[8/8] Configuring Kubernetes auth method..."
vault auth enable kubernetes 2>/dev/null || true

# Get K8s host from environment
K8S_HOST="https://${KUBERNETES_SERVICE_HOST:-kubernetes.default.svc}:${KUBERNETES_SERVICE_PORT_HTTPS:-443}"

vault write auth/kubernetes/config \
    kubernetes_host="${K8S_HOST}"

vault write auth/kubernetes/role/dashboard-role \
    bound_service_account_names=vault-dashboard \
    bound_service_account_namespaces="${NAMESPACE}" \
    policies=dashboard-policy \
    ttl=1h

echo "  Kubernetes auth configured for namespace: ${NAMESPACE}"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "================================================="
echo "  Vault Setup Complete!"
echo "================================================="
echo ""
echo "  Engines:  secret/ (KV v2), database/, pki/, pki_int/, transit/"
echo "  DB Roles: app-role (1h), readonly-role (30m)"
echo "  PKI:      Root CA + Intermediate CA"
echo "  Transit:  app-key, user-data-key"
echo "  Policies: dashboard-policy, break-glass"
echo "  K8s Auth: dashboard-role → dashboard-policy"
echo ""
echo "  Test dynamic credentials:"
echo "    vault read database/creds/app-role"
echo ""
echo "  Test certificate issuance:"
echo "    vault write pki_int/issue/app-role common_name=test.vault.local ttl=1h"
echo "================================================="
