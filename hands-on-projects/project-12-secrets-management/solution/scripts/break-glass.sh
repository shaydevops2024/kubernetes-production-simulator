#!/bin/bash
# break-glass.sh
# Emergency access procedure for when Vault is sealed, unreachable,
# or misconfigured. This is the runbook for the on-call engineer.
#
# This script is EDUCATIONAL — it demonstrates the concepts, not a
# production break-glass implementation (which would use HSMs, PGP keys, etc.)
#
# Usage:
#   ./break-glass.sh [check|unseal|emergency-token|status]

set -euo pipefail

NAMESPACE="${NAMESPACE:-secrets-management}"
VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
export VAULT_ADDR

echo "================================================="
echo "  VAULT BREAK-GLASS PROCEDURE"
echo "  $(date)"
echo "================================================="

ACTION="${1:-check}"

# ── Check current status ──────────────────────────────────────────────────────
check_status() {
    echo ""
    echo "=== Vault Status Check ==="
    echo ""
    echo "1. Pod status:"
    kubectl get pods -n "${NAMESPACE}" -l app=vault

    echo ""
    echo "2. Vault seal status:"
    kubectl exec -n "${NAMESPACE}" vault-0 -- vault status 2>/dev/null || echo "   ERROR: Cannot reach vault-0"

    echo ""
    echo "3. Last 20 lines of Vault logs:"
    kubectl logs -n "${NAMESPACE}" vault-0 --tail=20 2>/dev/null || echo "   ERROR: Cannot get logs"

    echo ""
    echo "4. Service endpoints:"
    kubectl get svc -n "${NAMESPACE}" | grep vault
}

# ── Unseal Vault ──────────────────────────────────────────────────────────────
unseal_vault() {
    echo ""
    echo "=== Unseal Vault ==="
    echo ""
    echo "You need 3 of 5 unseal keys (generated during 'vault operator init')."
    echo "These should be stored in your company password manager or HSM."
    echo ""

    # In a real scenario, these would come from an HSM or secure key ceremony
    # Never store actual unseal keys in scripts!
    echo "Usage (run manually with your actual unseal keys):"
    echo ""
    echo "  kubectl exec -n ${NAMESPACE} vault-0 -- vault operator unseal <key1>"
    echo "  kubectl exec -n ${NAMESPACE} vault-0 -- vault operator unseal <key2>"
    echo "  kubectl exec -n ${NAMESPACE} vault-0 -- vault operator unseal <key3>"
    echo ""
    echo "For auto-unseal in production, use:"
    echo "  - AWS KMS seal"
    echo "  - Azure Key Vault seal"
    echo "  - GCP CKMS seal"
    echo "  Configuration in vault.hcl:"
    echo '  seal "awskms" {'
    echo '    region     = "us-east-1"'
    echo '    kms_key_id = "arn:aws:kms:..."'
    echo '  }'
}

# ── Create emergency token ────────────────────────────────────────────────────
emergency_token() {
    echo ""
    echo "=== Emergency Token Creation ==="
    echo ""
    echo "WARNING: This creates a root-equivalent token. Use only in emergencies."
    echo "         Document the incident and revoke this token when done."
    echo ""

    VAULT_TOKEN="${VAULT_TOKEN:-root}"
    export VAULT_TOKEN

    # Create a short-lived break-glass token
    TOKEN=$(vault token create \
        -policy=break-glass \
        -ttl=1h \
        -display-name="break-glass-$(date +%Y%m%d-%H%M%S)" \
        -metadata="created_by=$(whoami)" \
        -metadata="reason=break-glass-incident" \
        -field=token)

    echo "  Emergency token created (1h TTL):"
    echo "  Token: ${TOKEN}"
    echo ""
    echo "  IMPORTANT:"
    echo "  1. Record this incident in your incident log"
    echo "  2. Revoke this token when the incident is resolved:"
    echo "     vault token revoke ${TOKEN}"
    echo "  3. Review audit logs after: vault audit list"

    # Log to a local incident file
    INCIDENT_FILE="/tmp/vault-break-glass-$(date +%Y%m%d-%H%M%S).log"
    echo "Break-glass invoked: $(date) by $(whoami)" > "${INCIDENT_FILE}"
    echo "Vault addr: ${VAULT_ADDR}" >> "${INCIDENT_FILE}"
    echo "Token (first 20 chars): ${TOKEN:0:20}..." >> "${INCIDENT_FILE}"
    echo ""
    echo "  Incident log written to: ${INCIDENT_FILE}"
}

# ── Recovery from complete failure ────────────────────────────────────────────
show_recovery_steps() {
    echo ""
    echo "=== Full Recovery Procedure ==="
    echo ""
    echo "Scenario: Vault pod is down, data is lost"
    echo ""
    echo "Step 1: Check if data volume is intact"
    echo "  kubectl get pvc -n ${NAMESPACE}"
    echo "  kubectl describe pvc vault-data-vault-0 -n ${NAMESPACE}"
    echo ""
    echo "Step 2: If volume is intact, just restart the pod"
    echo "  kubectl delete pod -n ${NAMESPACE} vault-0"
    echo "  # Wait for restart, then unseal"
    echo ""
    echo "Step 3: If data is lost (worst case), restore from backup"
    echo "  # If using Raft snapshots:"
    echo "  vault operator raft snapshot restore vault-backup.snap"
    echo ""
    echo "Step 4: Verify application secrets are accessible"
    echo "  vault kv get secret/app/database"
    echo "  vault read database/creds/app-role"
    echo ""
    echo "Step 5: Check and restart affected applications"
    echo "  # Apps that cached expired dynamic credentials need restart"
    echo "  kubectl rollout restart deployment -n ${NAMESPACE} vault-dashboard"
    echo ""
    echo "Step 6: Review and clear the incident"
    echo "  vault audit list"
    echo "  # Review /vault/audit/audit.log for what happened before failure"
}

# ── Main ──────────────────────────────────────────────────────────────────────
case "${ACTION}" in
    check)
        check_status
        ;;
    unseal)
        unseal_vault
        ;;
    emergency-token)
        emergency_token
        ;;
    recovery)
        show_recovery_steps
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 [check|unseal|emergency-token|recovery]"
        echo ""
        echo "  check           — Show current Vault status"
        echo "  unseal          — Instructions for unsealing Vault"
        echo "  emergency-token — Create a break-glass token (needs root access)"
        echo "  recovery        — Full recovery procedure steps"
        exit 1
        ;;
esac

echo ""
echo "================================================="
echo "  Break-glass script complete: $(date)"
echo "================================================="
