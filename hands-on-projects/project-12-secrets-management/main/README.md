# main/ — Deploy to Kubernetes

This is Phase 5 of the project. You've run Vault locally with Docker Compose — now you'll deploy a production-grade Vault cluster to your Kind Kubernetes cluster.

The `solution/` folder contains the complete reference implementation. **Try to build it yourself first**, then use the solution to check your work or get unstuck.

---

## What You'll Build

```
secrets-management namespace
├── vault/                    ← Vault StatefulSet (HA with Raft storage)
├── postgres/                 ← PostgreSQL StatefulSet (target for dynamic creds)
├── dashboard/                ← Dashboard Deployment
├── rbac/                     ← ServiceAccount, ClusterRole, ClusterRoleBinding
└── ingress/                  ← nginx Ingress for external access

vault-agent (sidecar pattern):
└── pod annotations → Vault injects secrets as files into /vault/secrets/
```

---

## Prerequisites

```bash
# Verify Kind cluster is running
kubectl cluster-info

# Verify nginx ingress controller is installed
kubectl get pods -n ingress-nginx

# Install Vault CLI
# macOS: brew tap hashicorp/tap && brew install hashicorp/tap/vault
# Linux: wget https://releases.hashicorp.com/vault/1.15.6/vault_1.15.6_linux_amd64.zip
```

---

## Phase 5A — Namespace & RBAC

Create the namespace and service accounts:

```bash
# Create namespace
kubectl create namespace secrets-management

# Your task: create a ServiceAccount for the dashboard app
# It needs permission to communicate with the Vault Kubernetes auth endpoint

kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: vault-dashboard
  namespace: secrets-management
EOF
```

**DevOps Task:** Why does the dashboard app need a ServiceAccount? What is Kubernetes auth in Vault and how does it use ServiceAccount tokens?

---

## Phase 5B — Deploy Vault via Helm

The recommended way to deploy Vault to Kubernetes is via the official Helm chart.

```bash
# Add the HashiCorp Helm repository
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update

# Install Vault (development mode — single node, not HA)
helm install vault hashicorp/vault \
    --namespace secrets-management \
    --set "server.dev.enabled=true" \
    --set "server.dev.devRootToken=root" \
    --set "ui.enabled=true" \
    --set "ui.serviceType=ClusterIP"

# Check pod status
kubectl get pods -n secrets-management
```

**For production HA mode** (see `solution/helm/vault-values.yaml`):

```bash
helm install vault hashicorp/vault \
    --namespace secrets-management \
    -f solution/helm/vault-values.yaml
```

After installing in HA mode, you must **initialize and unseal** Vault:

```bash
# Initialize Vault (generates unseal keys + root token)
kubectl exec -n secrets-management vault-0 -- vault operator init \
    -key-shares=5 \
    -key-threshold=3 \
    -format=json > vault-init-keys.json

# CRITICAL: Store vault-init-keys.json securely — if you lose unseal keys,
# you lose ALL secrets. In production, distribute keys to 5 different people.
cat vault-init-keys.json

# Unseal vault-0 (requires 3 of 5 keys)
kubectl exec -n secrets-management vault-0 -- vault operator unseal $(cat vault-init-keys.json | jq -r '.unseal_keys_b64[0]')
kubectl exec -n secrets-management vault-0 -- vault operator unseal $(cat vault-init-keys.json | jq -r '.unseal_keys_b64[1]')
kubectl exec -n secrets-management vault-0 -- vault operator unseal $(cat vault-init-keys.json | jq -r '.unseal_keys_b64[2]')

# Check status
kubectl exec -n secrets-management vault-0 -- vault status
```

---

## Phase 5C — Configure Vault for Kubernetes

After Vault is running and unsealed, configure it to use Kubernetes authentication:

```bash
# Port-forward to Vault for setup
kubectl port-forward -n secrets-management svc/vault 8200:8200 &

export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root  # or the root token from vault-init-keys.json

# Enable Kubernetes auth method
vault auth enable kubernetes

# Configure Kubernetes auth
vault write auth/kubernetes/config \
    kubernetes_host="https://$KUBERNETES_PORT_443_TCP_ADDR:443" \
    token_reviewer_jwt="$(kubectl get secret \
        $(kubectl get serviceaccount vault-dashboard -n secrets-management -o jsonpath='{.secrets[0].name}') \
        -n secrets-management -o jsonpath='{.data.token}' | base64 -d)" \
    kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt

# Create a Vault role that maps the K8s ServiceAccount to a policy
vault write auth/kubernetes/role/dashboard-role \
    bound_service_account_names=vault-dashboard \
    bound_service_account_namespaces=secrets-management \
    policies=dashboard-policy \
    ttl=1h

echo "Kubernetes auth configured!"
```

---

## Phase 5D — Configure Secrets Engines

Run the same setup as your local init script, but targeting the K8s Vault:

```bash
# Apply the same configuration as local/vault/init.sh
# but replace postgres hostname with the K8s service name

vault secrets enable -path=secret kv-v2
vault secrets enable database
vault secrets enable pki
vault secrets enable -path=pki_int pki
vault secrets enable transit

# Configure database engine pointing to K8s PostgreSQL service
vault write database/config/postgres \
    plugin_name=postgresql-database-plugin \
    allowed_roles="app-role,readonly-role" \
    connection_url="postgresql://{{username}}:{{password}}@postgres.secrets-management.svc.cluster.local:5432/appdb?sslmode=disable" \
    username="vault_admin" \
    password="vault_admin_password"
```

---

## Phase 5E — Deploy the Dashboard + PostgreSQL

Your task: write Kubernetes manifests for:

### PostgreSQL

```yaml
# Required resources:
# - StatefulSet (postgres:15-alpine)
# - Service (ClusterIP on port 5432)
# - Secret (POSTGRES_PASSWORD)
```

### Dashboard Deployment

```yaml
# Required resources:
# - Deployment (your dashboard image)
# - Service (ClusterIP on port 5555)
# - Ingress (host: vault-dashboard.local)
#
# Key question: How does the pod authenticate to Vault?
# Option A: Mount VAULT_TOKEN from a K8s Secret (simple, less secure)
# Option B: Use Vault Agent Injector (recommended for production)
```

---

## Phase 5F — Vault Agent Injector (Advanced)

This is the production-grade way to inject secrets into pods — no Vault SDK needed in your app.

Add these annotations to your Dashboard Deployment:

```yaml
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "dashboard-role"
        vault.hashicorp.com/agent-inject-secret-config: "secret/data/app/config"
        vault.hashicorp.com/agent-inject-template-config: |
          {{- with secret "secret/data/app/config" -}}
          APP_NAME={{ .Data.data.app_name }}
          ENV={{ .Data.data.env }}
          {{- end }}
```

After adding these annotations, Vault Agent runs as a sidecar and:
1. Authenticates to Vault using the pod's ServiceAccount token
2. Fetches the secret
3. Writes it to `/vault/secrets/config` inside the pod
4. Refreshes the file when the secret changes

**DevOps Task:** Why is this better than reading secrets from environment variables?

---

## Phase 5G — Verification

```bash
# Check all pods are running
kubectl get pods -n secrets-management

# Test Vault connectivity from the dashboard pod
kubectl exec -n secrets-management deploy/vault-dashboard -- \
    curl -s http://vault:8200/v1/sys/health | python3 -m json.tool

# Request dynamic credentials from inside the cluster
kubectl exec -n secrets-management deploy/vault-dashboard -- \
    curl -s -H "X-Vault-Token: root" \
    http://vault:8200/v1/database/creds/app-role

# Access the dashboard
kubectl port-forward -n secrets-management svc/vault-dashboard 5555:5555
# Open http://localhost:5555

# Check audit logs
kubectl exec -n secrets-management vault-0 -- \
    cat /vault/logs/audit.log | head -20
```

---

## Verification Checklist

- [ ] Vault pods are Running and unsealed (`vault status`)
- [ ] PostgreSQL pod is Running and healthy
- [ ] Dashboard pod is Running and reachable on port 5555
- [ ] Kubernetes auth is configured (`vault auth list`)
- [ ] Secrets engines mounted: KV, Database, PKI, Transit
- [ ] Dynamic credentials work (`vault read database/creds/app-role`)
- [ ] Dashboard can list secrets via the Vault API
- [ ] Audit logging is active (`vault audit list`)

---

## Reference Solution

Stuck? The complete solution is in `../solution/`:

```
solution/
├── k8s/
│   ├── namespace/        ← Namespace definition
│   ├── vault/            ← Vault StatefulSet + Service (without Helm)
│   ├── postgres/         ← PostgreSQL StatefulSet + Service + Secret
│   ├── app/              ← Dashboard Deployment + Service
│   ├── rbac/             ← ServiceAccount + ClusterRole + Binding
│   └── ingress/          ← nginx Ingress
├── helm/
│   └── vault-values.yaml ← Vault Helm chart values (HA + TLS)
└── scripts/
    ├── setup-vault.sh    ← Full Vault configuration script
    ├── rotate-secrets.sh ← Demonstrates manual rotation
    ├── break-glass.sh    ← Emergency access procedure
    └── health-check.sh   ← Verify full stack health
```
