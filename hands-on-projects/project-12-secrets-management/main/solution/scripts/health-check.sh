#!/bin/bash
# health-check.sh
# Verifies the full secrets management stack is healthy.
# Checks: Vault status, secrets engines, dynamic creds, PKI, transit, dashboard
#
# Usage:
#   export VAULT_ADDR=http://localhost:8200
#   export VAULT_TOKEN=root
#   ./health-check.sh

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:5555}"
export VAULT_ADDR VAULT_TOKEN

PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    printf "  %-50s " "${desc}..."
    if eval "${cmd}" > /dev/null 2>&1; then
        echo "✅ PASS"
        PASS=$((PASS + 1))
    else
        echo "❌ FAIL"
        FAIL=$((FAIL + 1))
    fi
}

echo "================================================="
echo "  Vault Health Check — $(date)"
echo "  VAULT_ADDR: ${VAULT_ADDR}"
echo "================================================="

echo ""
echo "--- Core Vault ---"
check "Vault is reachable"         "vault status"
check "Vault is initialized"       "vault status | grep -q 'Initialized.*true'"
check "Vault is unsealed"          "vault status | grep -q 'Sealed.*false'"

echo ""
echo "--- Secrets Engines ---"
check "KV v2 mounted at secret/"   "vault secrets list | grep -q '^secret/'"
check "Database engine mounted"    "vault secrets list | grep -q '^database/'"
check "PKI engine mounted"         "vault secrets list | grep -q '^pki/'"
check "PKI int engine mounted"     "vault secrets list | grep -q '^pki_int/'"
check "Transit engine mounted"     "vault secrets list | grep -q '^transit/'"

echo ""
echo "--- KV Secrets ---"
check "app/database secret exists" "vault kv get secret/app/database"
check "app/config secret exists"   "vault kv get secret/app/config"

echo ""
echo "--- Dynamic DB Credentials ---"
check "app-role exists"            "vault read database/roles/app-role"
check "readonly-role exists"       "vault read database/roles/readonly-role"
check "Can generate app-role creds" "vault read database/creds/app-role"

echo ""
echo "--- PKI ---"
check "Root CA exists"             "vault read pki/cert/ca"
check "Int CA role exists"         "vault read pki_int/roles/app-role"
check "Can issue certificate"      "vault write pki_int/issue/app-role common_name=test.vault.local ttl=1h"

echo ""
echo "--- Transit Encryption ---"
check "app-key exists"             "vault read transit/keys/app-key"
TESTCIPHER=$(echo -n "healthcheck" | base64 | vault write -field=ciphertext transit/encrypt/app-key plaintext=- 2>/dev/null)
check "Can encrypt data"           "echo '${TESTCIPHER}' | grep -q 'vault:v'"
check "Can decrypt data"           "vault write transit/decrypt/app-key ciphertext='${TESTCIPHER}'"

echo ""
echo "--- Audit ---"
check "Audit device active"        "vault audit list | grep -q 'file/'"

echo ""
echo "--- Dashboard ---"
check "Dashboard /health responds" "curl -sf ${DASHBOARD_URL}/health"
check "Dashboard /api/vault/status" "curl -sf ${DASHBOARD_URL}/api/vault/status | grep -q 'reachable'"

echo ""
echo "================================================="
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "================================================="

if [ "${FAIL}" -gt 0 ]; then
    echo "  ⚠ Some checks failed. Review the output above."
    exit 1
else
    echo "  ✅ All checks passed! Vault is healthy."
    exit 0
fi
