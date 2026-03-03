#!/bin/bash
# rotate-secrets.sh
# Demonstrates secret rotation strategies:
#   1. KV secret rotation (update in place)
#   2. Transit key rotation (old ciphertexts still work)
#   3. Force database credential renewal
#   4. Certificate re-issuance
#
# Usage:
#   export VAULT_ADDR=http://localhost:8200
#   export VAULT_TOKEN=root
#   ./rotate-secrets.sh

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"
export VAULT_ADDR VAULT_TOKEN

echo "================================================="
echo "  Secret Rotation Demo"
echo "================================================="

# ── 1. Rotate a KV Secret ─────────────────────────────────────────────────────
echo ""
echo "--- [1] KV Secret Rotation ---"
echo "  Before rotation:"
vault kv get secret/app/database

# Simulate: generate new password
NEW_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
echo ""
echo "  Updating password to: ${NEW_PASS:0:8}... (truncated)"
vault kv put secret/app/database \
    host=postgres \
    port=5432 \
    dbname=appdb \
    username=appuser \
    password="${NEW_PASS}"

echo "  After rotation:"
vault kv get -field=password secret/app/database

echo ""
echo "  Secret version history:"
vault kv metadata get secret/app/database | grep "versions" -A 10

# ── 2. Rotate Transit Encryption Key ─────────────────────────────────────────
echo ""
echo "--- [2] Transit Key Rotation ---"

# Encrypt with current key
PLAINTEXT_B64=$(echo -n "sensitive-data-example" | base64)
CIPHERTEXT=$(vault write -field=ciphertext transit/encrypt/app-key plaintext="${PLAINTEXT_B64}")
echo "  Ciphertext with current key: ${CIPHERTEXT:0:40}..."

# Rotate the key
echo "  Rotating app-key..."
vault write -f transit/keys/app-key/rotate

# Old ciphertext still decryptable!
DECRYPTED_B64=$(vault write -field=plaintext transit/decrypt/app-key ciphertext="${CIPHERTEXT}")
DECRYPTED=$(echo "${DECRYPTED_B64}" | base64 -d)
echo "  Old ciphertext still decrypts to: ${DECRYPTED}"

# Rewrap to new key version
NEW_CIPHERTEXT=$(vault write -field=ciphertext transit/rewrap/app-key ciphertext="${CIPHERTEXT}")
echo "  Rewrapped ciphertext (v2): ${NEW_CIPHERTEXT:0:40}..."

# Show key info
echo "  Key versions:"
vault read transit/keys/app-key | grep -E "min_decryption|min_encryption|latest_version"

# ── 3. Force DB Credential Renewal ────────────────────────────────────────────
echo ""
echo "--- [3] Database Credential Rotation ---"
echo "  Requesting new credentials (simulates TTL expiry + renewal)..."
vault read database/creds/app-role

echo ""
echo "  In production: applications should request new credentials before TTL expires."
echo "  Use vault lease renew <lease-id> to extend a lease before it expires."

# ── 4. Certificate Re-issuance ────────────────────────────────────────────────
echo ""
echo "--- [4] Certificate Re-issuance ---"
echo "  Issuing short-lived certificate (best practice: rotate before expiry)..."
vault write pki_int/issue/app-role \
    common_name="dashboard.vault.local" \
    ttl="1h" \
    format=pem | grep -E "serial_number|expiration|issuing_ca"

echo ""
echo "================================================="
echo "  Rotation Demo Complete!"
echo "  Key takeaways:"
echo "  - KV secrets: new version on every write, old versions retained"
echo "  - Transit: key rotation doesn't break old ciphertexts"
echo "  - DB creds: request new ones before TTL expires"
echo "  - Certs: issue new ones before expiry (automate this!)"
echo "================================================="
