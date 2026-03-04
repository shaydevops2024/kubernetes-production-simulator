#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Configure Vault Kubernetes Auth
# This enables pods to authenticate to Vault using their ServiceAccount token.
# Run AFTER Vault is installed and running in dev mode.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

VAULT_NS="vault"
VAULT_TOKEN="root"    # matches devRootToken in vault-values.yaml
VAULT_ADDR="http://vault.internal"

echo "==> Setting up Vault port-forward..."
kubectl port-forward svc/vault -n "${VAULT_NS}" 8200:8200 &
PF_PID=$!
sleep 3
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN="${VAULT_TOKEN}"

echo "==> Enabling Kubernetes auth method..."
vault auth enable kubernetes 2>/dev/null || echo "  (already enabled)"

echo "==> Configuring Kubernetes auth..."
KUBE_HOST=$(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.server}')
KUBE_CA=$(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)
SA_TOKEN=$(kubectl create token vault -n vault 2>/dev/null || \
           kubectl get secret -n vault -o jsonpath='{.items[?(@.type=="kubernetes.io/service-account-token")].data.token}' | base64 -d)

vault write auth/kubernetes/config \
    token_reviewer_jwt="${SA_TOKEN}" \
    kubernetes_host="${KUBE_HOST}" \
    kubernetes_ca_cert="${KUBE_CA}" \
    issuer="https://kubernetes.default.svc.cluster.local"

echo "==> Enabling KV secrets engine..."
vault secrets enable -path=secret kv-v2 2>/dev/null || echo "  (already enabled)"

echo "==> Writing sample secrets..."
vault kv put secret/team-alpha/db \
    username=app \
    password=supersecretpassword123 \
    host=team-alpha-db-rw.team-alpha.svc.cluster.local \
    port=5432 \
    dbname=appdb

vault kv put secret/team-beta/db \
    username=betaapp \
    password=betasecret456 \
    host=team-beta-db-rw.team-beta.svc.cluster.local \
    port=5432 \
    dbname=betadb

echo "==> Creating read policies..."
vault policy write team-alpha-read - <<EOF
path "secret/data/team-alpha/*" {
  capabilities = ["read", "list"]
}
EOF

vault policy write team-beta-read - <<EOF
path "secret/data/team-beta/*" {
  capabilities = ["read", "list"]
}
EOF

echo "==> Creating Kubernetes auth roles..."
vault write auth/kubernetes/role/team-alpha \
    bound_service_account_names=default \
    bound_service_account_namespaces=alpha,team-alpha \
    policies=team-alpha-read \
    ttl=1h

vault write auth/kubernetes/role/team-beta \
    bound_service_account_names=default \
    bound_service_account_namespaces=beta,team-beta \
    policies=team-beta-read \
    ttl=1h

echo "==> Cleaning up port-forward..."
kill "${PF_PID}" 2>/dev/null || true

echo ""
echo "════════════════════════════════════════════════════════════"
echo "Phase 4 — Vault auth configured!"
echo ""
echo "  Test with: kubectl apply -f vault-test-pod.yaml"
echo "  Verify:    kubectl exec -it vault-test -- cat /vault/secrets/db"
echo "════════════════════════════════════════════════════════════"
