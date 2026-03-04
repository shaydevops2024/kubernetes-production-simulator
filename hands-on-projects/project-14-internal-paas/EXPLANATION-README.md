# Project 14 — Internal Developer Platform (PaaS): Explained

---

## 1. The App

You are building a **complete Internal Developer Platform (IDP)** — the kind of platform that large engineering organizations use so that developers can self-serve infrastructure without filing tickets to the ops team. A developer opens the portal, clicks "Create Namespace for Team A", and within seconds they have an isolated namespace with RBAC, resource quotas, Vault secrets, a PostgreSQL database, and cost tracking — all provisioned automatically.

```
Developer
  └─▶ Developer Portal (Backstage-style)
        │  "Create namespace for Team A"
        │  "Provision PostgreSQL for my service"
        │  "Inject my secrets"
        ▼
  ┌─────────────────────────────────────────────────────┐
  │               Kubernetes (Kind Cluster)              │
  │                                                      │
  │  [Gitea]          [Woodpecker CI]    [Harbor]        │
  │  Git hosting      CI pipelines       Image registry  │
  │       │                │                  │          │
  │       └───────────────►ArgoCD◄────────────┘          │
  │                         │ GitOps sync                 │
  │                         ▼                            │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
  │  │  Team A  │  │  Team B  │  │  Crossplane       │   │
  │  │  ns+RBAC │  │  ns+RBAC │  │  Provisions:      │   │
  │  │  Quota   │  │  Quota   │  │  - Namespaces     │   │
  │  └──────────┘  └──────────┘  │  - RBAC           │   │
  │                              │  - Databases       │   │
  │  ┌──────────┐  ┌──────────┐  └──────────────────┘   │
  │  │  Vault   │  │CloudNaPG │  ┌──────────────────┐   │
  │  │  (HA)    │  │(Postgres)│  │  Kyverno          │   │
  │  │  Secrets │  │  DBaaS   │  │  Policy engine    │   │
  │  └──────────┘  └──────────┘  └──────────────────┘   │
  │                                                      │
  │  ┌──────────────────────┐  ┌────────────────────┐   │
  │  │  Prometheus+Grafana  │  │  OpenCost           │   │
  │  │  Observability       │  │  Per-team cost      │   │
  │  └──────────────────────┘  └────────────────────┘   │
  └─────────────────────────────────────────────────────┘
```

| Component | Role |
|-----------|------|
| **Developer Portal** | Self-service UI — teams onboard themselves without waiting on ops |
| **Gitea** | Self-hosted Git server — teams push code here |
| **Woodpecker CI** | CI pipeline engine — builds and tests code from Gitea |
| **Harbor** | Self-hosted container registry — stores team images; vulnerability scanning built in |
| **ArgoCD** | GitOps operator — syncs K8s state to match Git, the source of truth |
| **Crossplane** | Kubernetes-native infrastructure provisioner — provisions namespaces, RBAC, databases using CRDs |
| **Vault (HA mode)** | Secrets management — per-team secrets, dynamic DB credentials, PKI |
| **CloudNativePG** | PostgreSQL-as-a-Service operator — teams request databases, operator handles HA |
| **Kyverno** | Policy engine — enforces rules (every pod must have resource limits, no privileged containers) |
| **OpenCost** | Cost tracking — shows per-team, per-namespace infrastructure cost |
| **Prometheus + Grafana** | Platform observability — metrics for the entire platform |

---

## 2. How to Use the App

### Phase 1 — Run the Portal Locally (Docker Compose)

```bash
cd hands-on-projects/project-14-internal-paas/local/

docker compose up --build
```

| UI | URL |
|----|-----|
| Developer Portal | http://localhost:3000 |

**Basic workflow (local simulation):**
1. Open http://localhost:3000
2. Create a new team (e.g., "team-payments")
3. The portal shows the self-service options:
   - Provision namespace (simulated)
   - Request a database (simulated)
   - Inject secrets (simulated)
4. Explore the cost breakdown for each team
5. See the provisioned resources list

### Phase 2 — Deploy the Full Platform to Kubernetes

This is the most complex project — you deploy ~10 tools and wire them together. The guide is phase-by-phase:

```bash
cd hands-on-projects/project-14-internal-paas/main/

# Phase 1: Foundation
kubectl apply -f solution/platform/namespace.yaml
kubectl apply -f solution/platform/rbac/

# Phase 2: Install Gitea (self-hosted Git)
helm install gitea gitea-charts/gitea -n platform --create-namespace \
  -f solution/gitea/values.yaml

# Phase 3: Install Harbor (image registry)
helm install harbor harbor/harbor -n harbor --create-namespace \
  -f solution/harbor/values.yaml

# Phase 4: Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Phase 5: Install Vault (HA mode with 3 replicas)
helm install vault hashicorp/vault -n vault --create-namespace \
  -f solution/vault/ha-values.yaml

# Phase 6: Install CloudNativePG
helm install cnpg cloudnative-pg/cloudnative-pg -n cnpg-system --create-namespace

# Phase 7: Install Crossplane
helm install crossplane crossplane-stable/crossplane -n crossplane-system --create-namespace

# Phase 8: Apply Crossplane compositions (namespace + RBAC + DB templates)
kubectl apply -f solution/crossplane/compositions/

# Phase 9: Install Kyverno
helm install kyverno kyverno/kyverno -n kyverno --create-namespace
kubectl apply -f solution/kyverno/policies/

# Phase 10: Install OpenCost
helm install opencost opencost/opencost -n opencost --create-namespace

# Phase 11: Install Woodpecker CI
helm install woodpecker woodpecker/woodpecker -n platform \
  -f solution/woodpecker/values.yaml

# Phase 12: Deploy the Developer Portal
kubectl apply -f solution/portal/

# Phase 13: Configure ArgoCD to manage itself and team workloads
kubectl apply -f solution/argocd-apps/
```

**Onboard a new team via the portal:**
```bash
# Via the self-service portal UI, or via CLI:
kubectl apply -f - <<EOF
apiVersion: platform.example.com/v1alpha1
kind: Team
metadata:
  name: team-payments
spec:
  displayName: "Payments Team"
  plan: "standard"  # defines CPU/memory quotas
  members:
    - username: alice
    - username: bob
EOF

# Crossplane sees this CRD and automatically creates:
# - Namespace: team-payments
# - ResourceQuota for the team
# - RBAC roles and bindings
# - Vault secret path for the team
# - Initial PostgreSQL database (if requested)
```

---

## 3. How to Test It

### Team Provisioning Test

```bash
# Apply a Team CRD
kubectl apply -f - <<EOF
apiVersion: platform.example.com/v1alpha1
kind: Team
metadata:
  name: test-team
spec:
  plan: "starter"
EOF

# Verify Crossplane provisioned the namespace
kubectl get namespace test-team

# Verify RBAC was created
kubectl get rolebinding -n test-team

# Verify ResourceQuota was applied
kubectl describe resourcequota -n test-team
```

### Kyverno Policy Test

```bash
# Try to deploy a pod WITHOUT resource limits (should be blocked)
kubectl apply -f - -n test-team <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: no-limits-pod
spec:
  containers:
    - name: test
      image: nginx
EOF
# Expected: admission webhook denied (Kyverno policy: require-resource-limits)

# Deploy with resource limits (should succeed)
kubectl apply -f - -n test-team <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: with-limits-pod
spec:
  containers:
    - name: test
      image: nginx
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
        limits:
          cpu: "500m"
          memory: "256Mi"
EOF
```

### Database Provisioning Test (CloudNativePG)

```bash
# Request a database via Crossplane
kubectl apply -f - <<EOF
apiVersion: platform.example.com/v1alpha1
kind: Database
metadata:
  name: payments-db
  namespace: test-team
spec:
  team: test-team
  size: "small"  # 1 CPU, 1Gi RAM
  storage: "5Gi"
EOF

# Verify CloudNativePG cluster was created
kubectl get cluster -n test-team

# Check database is ready
kubectl get pods -n test-team -l cnpg.io/cluster=payments-db
```

### CI/CD Pipeline Test (Gitea + Woodpecker)

```bash
# Push code to Gitea
git remote add gitea http://localhost:3000/team-payments/myapp.git
git push gitea main

# Watch Woodpecker CI pick up the pipeline
# Open Woodpecker UI: http://localhost:8000
# Should see: Clone → Test → Build → Push to Harbor → Notify ArgoCD

# Verify image was pushed to Harbor
# Open Harbor: http://localhost:80
# Look for: team-payments/myapp:<git-sha>
```

### Cost Tracking Test

```bash
# Check per-team cost in OpenCost
curl http://localhost:9003/model/allocation?window=1d\&aggregate=namespace \
  | jq '.data[0] | {namespace: .name, totalCost: .totalCost}'

# Or in Grafana: OpenCost dashboard shows per-namespace breakdown
# Open http://localhost:3001 → Dashboards → OpenCost
```

### ArgoCD GitOps Test

```bash
# Verify ArgoCD is managing the platform
argocd app list

# Check all apps are synced
argocd app get platform --refresh
# Should show: Sync Status: Synced, Health Status: Healthy

# Make a change to Gitea, watch ArgoCD auto-sync
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Developer Portal (FastAPI + HTML)** | Self-service UI | Teams onboard via the portal; it calls K8s API to apply Crossplane CRDs |
| **Gitea** | Self-hosted Git | Teams push code here; Woodpecker watches for changes |
| **Woodpecker CI** | CI engine | Listens to Gitea webhooks; runs `.woodpecker.yaml` pipeline definitions |
| **Harbor** | Image registry | Woodpecker pushes images here; Kyverno ensures only Harbor images are used |
| **ArgoCD** | GitOps operator | Watches Gitea repos, syncs K8s cluster to match Git state |
| **Crossplane** | Infrastructure provisioner | Manages team namespaces, RBAC, quotas as K8s-native CRDs |
| **Vault (HA)** | Secrets management | 3-replica Raft HA cluster; per-team secret paths; dynamic DB creds |
| **CloudNativePG** | Postgres operator | Teams request databases; operator handles HA, backups, failover |
| **Kyverno** | Policy enforcement | Blocks non-compliant workloads at admission time; no privileged containers, required labels, resource limits |
| **OpenCost** | Cost tracking | Reads Prometheus metrics, calculates per-namespace cloud cost |
| **Prometheus + Grafana** | Platform observability | Metrics for all platform components; team-facing dashboards |
| **Helm** | Package manager | Installs every platform component from its Helm chart |

### Key Internal PaaS Concepts Practiced

- **Developer self-service**: Teams provision infrastructure without ops tickets
- **Platform as code**: All platform components defined in Git; ArgoCD keeps them in sync
- **Crossplane compositions**: Abstract complex K8s resources into simple developer-facing CRDs
- **Policy as code**: Kyverno policies are YAML — versioned, reviewed, enforced at admission time
- **FinOps**: Per-team cost visibility encourages responsible resource usage
- **GitOps at platform level**: The platform itself is managed by ArgoCD — infrastructure drift is auto-corrected

---

## 5. Troubleshooting

### Crossplane not creating resources

```bash
# Check Crossplane controller logs
kubectl logs -n crossplane-system deploy/crossplane -f

# Check the composition status
kubectl get composite -A
kubectl describe composite team-test-team

# Common cause: Composition or CompositeResourceDefinition not applied
kubectl get xrd  # CustomResourceDefinitions for platform
kubectl get composition
```

### Kyverno blocking legitimate pods

```bash
# Check which policy is blocking
kubectl get policyreport -n test-team

# Describe the specific violation
kubectl describe policyreport -n test-team

# Temporarily audit mode (log but don't block) during debugging
kubectl edit clusterpolicy require-resource-limits
# Change: validationFailureAction: enforce → audit
```

### Woodpecker CI not triggering on Gitea push

```bash
# Check webhook is configured in Gitea
# Gitea → Repository → Settings → Webhooks

# Check Woodpecker received the event
kubectl logs -n platform deploy/woodpecker-server | grep webhook

# Verify Gitea and Woodpecker can communicate
kubectl exec -n platform deploy/woodpecker-server -- \
  curl http://gitea.platform.svc:3000/api/v1/repos/search?limit=1
```

### Vault HA cluster not forming (3 pods failing)

```bash
# Check Vault pod logs
kubectl logs -n vault vault-0
kubectl logs -n vault vault-1

# Check Raft join status
kubectl exec -n vault vault-0 -- vault operator raft list-peers

# Common cause: storage PVC not available
kubectl get pvc -n vault

# Unseal all nodes if sealed (need to unseal each separately)
for i in 0 1 2; do
  kubectl exec -n vault vault-$i -- vault operator unseal <unseal-key>
done
```

### CloudNativePG database stuck in "Creating"

```bash
# Check cluster status
kubectl describe cluster -n test-team payments-db

# Check CloudNativePG operator logs
kubectl logs -n cnpg-system deploy/cnpg-controller-manager -f

# Check if PVC was provisioned
kubectl get pvc -n test-team

# Common fix: StorageClass doesn't exist or has no available provisioner
kubectl get storageclass
```

### OpenCost showing no data

```bash
# OpenCost needs Prometheus to be scraping kubelet metrics
kubectl port-forward -n opencost deploy/opencost 9003:9003

curl http://localhost:9003/healthz

# Check if Prometheus is reachable
curl 'http://localhost:9003/model/allocation?window=1d' | jq .

# Verify Prometheus scrapes node metrics
curl 'http://localhost:9090/api/v1/query?query=node_cpu_seconds_total' | jq '.data.result | length'
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-14-internal-paas/local/

docker compose down -v
```

### Kubernetes (Full Platform Teardown)

```bash
# Delete all team namespaces
kubectl delete namespaces -l managed-by=crossplane-platform

# Uninstall all Helm releases
helm uninstall opencost -n opencost
helm uninstall kyverno -n kyverno
helm uninstall cnpg -n cnpg-system
helm uninstall vault -n vault
helm uninstall crossplane -n crossplane-system
helm uninstall harbor -n harbor
helm uninstall gitea -n platform
helm uninstall woodpecker -n platform
helm uninstall kube-prometheus-stack -n monitoring

# Delete ArgoCD
kubectl delete namespace argocd

# Delete namespaces
kubectl delete namespace opencost kyverno cnpg-system vault crossplane-system harbor platform monitoring

# Delete the Kind cluster entirely (fastest cleanup)
kind delete cluster --name <your-cluster-name>
```
