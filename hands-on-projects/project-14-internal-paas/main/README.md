# Main — Building the Internal Developer Platform on Kubernetes

This is the production phase. You'll build the full Internal Developer Platform step by step on a local Kind cluster.

Each phase delivers something you verify is working before you move on to the next. By the end you have a complete self-service platform.

All reference manifests are in `solution/`. You can peek at them if you get stuck, but try to write them yourself first — that's where the learning happens.

---

## What You'll Build

```
Phase 1 → Kind cluster + MetalLB + ingress-nginx + local-path-provisioner
Phase 2 → Harbor (registry) + Gitea (Git) + Woodpecker CI
Phase 3 → Crossplane (namespace provisioning) + RBAC
Phase 4 → HashiCorp Vault (secrets management)
Phase 5 → CloudNativePG (database provisioning)
Phase 6 → Backstage (developer portal)
Phase 7 → kube-prometheus-stack + OpenCost (observability + costs)
Phase 8 → Kyverno (policy enforcement)
```

All phases use ArgoCD for GitOps (installed in Phase 1 alongside the cluster).

---

## Prerequisites

```bash
# Check you have these installed
kind version          # v0.20+
kubectl version       # v1.28+
helm version          # v3.12+
docker info           # Docker running

# Optional but useful
argocd version        # for ArgoCD CLI
```

---

## Phase 1 — Kind Cluster + Core Infrastructure

### Why this order?

You need a running cluster before everything else. MetalLB gives you real LoadBalancer IPs (simulating bare metal). ingress-nginx handles all HTTP routing. local-path-provisioner gives you PersistentVolumes.

### 1.1 — Create the Kind Cluster

The cluster config uses `extraPortMappings` to expose ingress on port 80/443, and a custom `containerdConfigPatches` to trust the local Harbor registry (you'll set up Harbor in Phase 2, but you configure the trust now).

```bash
# Apply the cluster config
kind create cluster --name paas --config solution/phase-1-cluster/kind-config.yaml
```

Verify:
```bash
kubectl get nodes
# Should show: 1 control-plane + 3 worker nodes Ready
```

### 1.2 — Install MetalLB

MetalLB simulates cloud LoadBalancer IPs on bare metal / Kind.

```bash
helm repo add metallb https://metallb.github.io/metallb
helm repo update

helm install metallb metallb/metallb \
  --namespace metallb-system \
  --create-namespace \
  --wait

# Apply the IP address pool (uses the Docker bridge network range)
kubectl apply -f solution/phase-1-cluster/metallb-config.yaml
```

Verify:
```bash
kubectl get ipaddresspool -n metallb-system
kubectl get l2advertisement -n metallb-system
```

### 1.3 — Install ingress-nginx

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer \
  --wait
```

Verify:
```bash
kubectl get svc -n ingress-nginx
# EXTERNAL-IP should show a real IP (from MetalLB), not <pending>
```

### 1.4 — Install ArgoCD

All future installs will be deployed via ArgoCD (GitOps). Install ArgoCD first.

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available --timeout=120s deployment/argocd-server -n argocd

# Get the initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo

# Expose the UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Access: https://localhost:8080 (admin / <password above>)
```

### Verify Phase 1

- [ ] All 4 nodes in `Ready` state
- [ ] MetalLB pods running in `metallb-system`
- [ ] ingress-nginx has an EXTERNAL-IP (not `<pending>`)
- [ ] ArgoCD pods running and UI accessible

---

## Phase 2 — Container Registry + Git + CI/CD

### Why Gitea + Woodpecker instead of GitHub?

This project is fully on-prem. Gitea is a self-hosted Git server (like GitHub but runs in your cluster). Woodpecker CI connects to Gitea via OAuth and runs pipelines when you push code. Harbor is a self-hosted container registry (like Docker Hub).

### 2.1 — Install Harbor

Harbor is your private container registry. Kind is already patched to trust it.

```bash
helm repo add harbor https://helm.goharbor.io
helm install harbor harbor/harbor \
  --namespace harbor \
  --create-namespace \
  --values solution/phase-2-registry-gitea/harbor/harbor-values.yaml \
  --wait --timeout 5m
```

Verify:
```bash
kubectl get pods -n harbor
# All pods Running. Access via ingress: http://harbor.internal
```

Default credentials: `admin / Harbor12345` (change immediately in production!)

Push your first image:
```bash
docker tag python:3.11-slim harbor.internal/library/python:3.11-slim
docker push harbor.internal/library/python:3.11-slim
```

### 2.2 — Install Gitea

```bash
helm repo add gitea-charts https://dl.gitea.com/charts/
helm install gitea gitea-charts/gitea \
  --namespace gitea \
  --create-namespace \
  --values solution/phase-2-registry-gitea/gitea/gitea-values.yaml \
  --wait
```

Verify:
```bash
kubectl get pods -n gitea
# Access: http://git.internal (admin / gitea123)
```

Create a test repository and push a commit. Then move on to Woodpecker.

### 2.3 — Install Woodpecker CI

Woodpecker needs a Gitea OAuth application first:

```bash
# In Gitea UI: User Settings → Applications → OAuth2 Applications
# Create app: "Woodpecker CI"
# Redirect URI: http://woodpecker.internal/authorize
# Copy the Client ID and Secret

# Create the Woodpecker secret with these credentials
kubectl create secret generic woodpecker-secret \
  --namespace woodpecker \
  --from-literal=WOODPECKER_GITEA_CLIENT=<YOUR_CLIENT_ID> \
  --from-literal=WOODPECKER_GITEA_SECRET=<YOUR_CLIENT_SECRET> \
  --from-literal=WOODPECKER_AGENT_SECRET=$(openssl rand -hex 32)

helm repo add woodpecker https://woodpecker-ci.org/woodpecker
helm install woodpecker woodpecker/woodpecker \
  --namespace woodpecker \
  --create-namespace \
  --values solution/phase-2-registry-gitea/woodpecker/woodpecker-values.yaml \
  --wait
```

Test it: push a `.woodpecker.yml` pipeline to a Gitea repo and watch it run.

### Verify Phase 2

- [ ] Harbor UI accessible and accepting image pushes
- [ ] Gitea UI accessible and accepting git push
- [ ] Woodpecker shows pipelines triggered by Gitea commits
- [ ] Images built by Woodpecker are pushed to Harbor

---

## Phase 3 — Namespace Provisioning + RBAC

### Why Crossplane?

Without Crossplane, provisioning a namespace for a new team requires someone to manually run `kubectl` commands. With Crossplane, a developer submits a Kubernetes custom resource (like `NamespaceClaim`), and Crossplane automatically creates the namespace, ResourceQuota, NetworkPolicy, and RBAC — all as code, all in Git, all GitOps.

### 3.1 — Install Crossplane

```bash
helm repo add crossplane-stable https://charts.crossplane.io/stable
helm install crossplane crossplane-stable/crossplane \
  --namespace crossplane-system \
  --create-namespace \
  --wait
```

### 3.2 — Deploy the Namespace Composition

```bash
# The Composition defines the template — what gets created when a NamespaceClaim is submitted
kubectl apply -f solution/phase-3-namespace-rbac/crossplane/namespace-composition.yaml

# The CompositeResourceDefinition defines the custom resource type
kubectl apply -f solution/phase-3-namespace-rbac/crossplane/namespace-xrd.yaml
```

### 3.3 — Provision a Team Namespace

Instead of running `kubectl create namespace`, you now submit a claim:

```bash
kubectl apply -f solution/phase-3-namespace-rbac/crossplane/namespace-claim.yaml
```

Crossplane reads the claim and creates:
- The namespace
- A ResourceQuota (CPU, memory, pod limits)
- A NetworkPolicy (default deny + allow same-namespace)
- A developer ClusterRole + RoleBinding for the team

Verify:
```bash
kubectl get namespace team-delta
kubectl get resourcequota -n team-delta
kubectl get networkpolicy -n team-delta
kubectl get rolebinding -n team-delta
```

### Verify Phase 3

- [ ] Crossplane pods running
- [ ] NamespaceClaim creates all resources automatically
- [ ] ResourceQuota limits are enforced (try exceeding the CPU limit)
- [ ] NetworkPolicy blocks cross-namespace traffic (test it!)

---

## Phase 4 — Secrets Management with Vault

### Why Vault?

Kubernetes Secrets are base64-encoded, not encrypted. Anyone with cluster access can decode them. Vault provides real encryption, dynamic secrets (short-lived credentials generated on demand), audit logs, and fine-grained access policies.

### 4.1 — Install Vault

Start in dev mode (insecure, for learning). Phase 4B shows HA mode.

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault \
  --namespace vault \
  --create-namespace \
  --values solution/phase-4-vault/vault-values.yaml \
  --wait
```

### 4.2 — Initialize and Unseal

```bash
# In dev mode, Vault auto-unseals. Get the root token:
kubectl exec -n vault vault-0 -- vault status
kubectl logs -n vault vault-0 | grep "Root Token"
```

### 4.3 — Enable Kubernetes Auth

Pods authenticate to Vault using their ServiceAccount token:

```bash
# Run the auth setup script
bash solution/phase-4-vault/vault-k8s-auth.sh
```

### 4.4 — Inject Secrets into Pods

Vault Agent Injector patches your pod with a sidecar that writes secrets to a file. No application code changes needed.

```bash
# Deploy a test pod that reads a secret from Vault
kubectl apply -f solution/phase-4-vault/test-pod.yaml
kubectl exec -it vault-test -n team-alpha -- cat /vault/secrets/db-password
```

### Verify Phase 4

- [ ] Vault UI accessible and showing secrets engine
- [ ] Kubernetes auth method enabled
- [ ] Test pod successfully reads secret injected by Vault Agent
- [ ] Audit log shows the access

---

## Phase 5 — Database Provisioning with CloudNativePG

### Why CloudNativePG?

Like Crossplane for namespaces, CloudNativePG (CNPG) lets teams provision PostgreSQL clusters by submitting a Kubernetes resource. CNPG handles HA, replication, backups, and failover automatically.

### 5.1 — Install CloudNativePG

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace \
  --wait
```

### 5.2 — Provision a PostgreSQL Cluster

```bash
kubectl apply -f solution/phase-5-database/cloudnativepg/cnpg-cluster.yaml
```

Verify:
```bash
kubectl get cluster -n team-alpha
kubectl get pods -n team-alpha -l cnpg.io/cluster=team-alpha-db
# Should show 1 primary + 1 replica
```

Connect to the database:
```bash
kubectl exec -it team-alpha-db-1 -n team-alpha -- psql -U app
```

### Verify Phase 5

- [ ] CNPG operator running
- [ ] PostgreSQL cluster provisioned (primary + replica)
- [ ] Can connect and create tables
- [ ] Vault provides database credentials dynamically (stretch goal)

---

## Phase 6 — Backstage Developer Portal

### Why Backstage?

Backstage is Spotify's open-source developer portal. It's the real version of the mock portal you ran locally in Phase 2. It shows your services, team ownership, documentation, and integrates with your CI/CD, registry, and Git — all in one place.

### 6.1 — Install Backstage

```bash
kubectl apply -f solution/phase-6-backstage/backstage-namespace.yaml
helm repo add backstage https://backstage.github.io/charts
helm install backstage backstage/backstage \
  --namespace backstage \
  --values solution/phase-6-backstage/backstage-values.yaml \
  --wait
```

### 6.2 — Register Your Services

Backstage discovers services via `catalog-info.yaml` files in your Gitea repos:

```yaml
# catalog-info.yaml (add this to each service repo)
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: my-api
  annotations:
    gitea.com/project-slug: alpha/my-api
spec:
  type: service
  lifecycle: production
  owner: team-alpha
```

Push this to your Gitea repo and watch Backstage pick it up.

### Verify Phase 6

- [ ] Backstage UI accessible
- [ ] Services registered and visible in catalog
- [ ] Team ownership shown correctly
- [ ] Links to Gitea repos working

---

## Phase 7 — Observability + Cost Tracking

### 7.1 — Install kube-prometheus-stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values solution/phase-7-observability/kube-prometheus-stack-values.yaml \
  --wait --timeout 10m
```

Access Grafana:
```bash
kubectl port-forward svc/monitoring-grafana -n monitoring 3001:80
# http://localhost:3001 — admin / prom-operator
```

### 7.2 — Install metrics-server

Required by OpenCost and HPA:
```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm install metrics-server metrics-server/metrics-server \
  --namespace kube-system \
  --set args[0]=--kubelet-insecure-tls
```

### 7.3 — Install OpenCost

OpenCost breaks down cluster costs per namespace and team:
```bash
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm install opencost opencost/opencost \
  --namespace opencost \
  --create-namespace \
  --values solution/phase-7-observability/opencost-values.yaml
```

Access OpenCost UI:
```bash
kubectl port-forward svc/opencost -n opencost 9090:9090
# http://localhost:9090
```

### Verify Phase 7

- [ ] Prometheus scraping metrics from all namespaces
- [ ] Grafana dashboards showing cluster and namespace metrics
- [ ] OpenCost showing per-team cost breakdown
- [ ] AlertManager sending alerts (configure a test rule)

---

## Phase 8 — Policy Enforcement with Kyverno

### Why Kyverno?

Kyverno enforces policies as Kubernetes resources. Examples:
- Every pod must have resource limits (no runaway containers)
- Images must come from Harbor (no `docker.io` images in production)
- Every deployment must have the `team` label (for cost tracking)

### 8.1 — Install Kyverno

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --wait
```

### 8.2 — Apply Policies

```bash
kubectl apply -f solution/phase-8-policies/kyverno/require-labels.yaml
kubectl apply -f solution/phase-8-policies/kyverno/require-resources.yaml
kubectl apply -f solution/phase-8-policies/kyverno/restrict-images.yaml
```

Test them:
```bash
# This should be BLOCKED (missing team label)
kubectl run test --image=nginx -n team-alpha

# This should PASS
kubectl run test --image=harbor.internal/library/nginx:latest \
  -n team-alpha --labels="team=team-alpha,app=test"

# Check policy reports
kubectl get policyreport -A
```

### Verify Phase 8

- [ ] Policy violations shown in `policyreport`
- [ ] Pods without resource limits are blocked (or audited)
- [ ] Images from docker.io are blocked in team namespaces
- [ ] All existing workloads have the required labels

---

## GitOps — Managing Everything with ArgoCD

Once you have ArgoCD running (from Phase 1), you can manage all your Helm releases and manifests through it:

```bash
# Apply the app-of-apps pattern
kubectl apply -f solution/argocd/app-of-apps.yaml
```

ArgoCD will then watch your Git repository and automatically sync any changes you push to the cluster.

Test GitOps:
1. Push a change to a Helm values file in your Gitea repo
2. ArgoCD detects the change
3. ArgoCD syncs — Helm upgrade runs automatically
4. Verify the change is applied without touching `kubectl`

---

## Verification Checklist (Full Platform)

- [ ] Kind cluster with 4 nodes
- [ ] Harbor accepting image pushes
- [ ] Gitea serving Git repos
- [ ] Woodpecker running CI pipelines on git push
- [ ] Crossplane provisioning namespaces from YAML claims
- [ ] Vault injecting secrets into pods
- [ ] CloudNativePG managing PostgreSQL HA clusters
- [ ] Backstage showing service catalog
- [ ] Prometheus + Grafana showing team metrics
- [ ] OpenCost showing per-team cost
- [ ] Kyverno enforcing image and resource policies
- [ ] ArgoCD syncing all manifests from Git

---

## Solution Reference

Stuck? Each phase has a complete working solution in `solution/`:

```
solution/
├── phase-1-cluster/
├── phase-2-registry-gitea/
├── phase-3-namespace-rbac/
├── phase-4-vault/
├── phase-5-database/
├── phase-6-backstage/
├── phase-7-observability/
├── phase-8-policies/
└── argocd/
```
