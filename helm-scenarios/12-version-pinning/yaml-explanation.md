# Helm Version Pinning - Complete Guide

This comprehensive guide explains Helm chart version pinning, why it's critical for production deployments, how to search for versions, and how to perform controlled version upgrades. Version pinning is one of the most important production best practices for Helm.

---

## 🎯 What is Version Pinning?

**Version pinning** means explicitly specifying the exact chart version to install or upgrade, rather than accepting "the latest" version.

### Without Version Pinning (DANGEROUS)
```bash
helm install my-app bitnami/nginx
# Installs whatever version is latest TODAY
# Tomorrow, the same command might install a DIFFERENT version
# ⚠️ UNPREDICTABLE AND DANGEROUS IN PRODUCTION
```

### With Version Pinning (SAFE)
```bash
helm install my-app bitnami/nginx --version 15.0.0
# ALWAYS installs exactly version 15.0.0
# Today, tomorrow, next year - same command, same result
# ✅ PREDICTABLE AND SAFE
```

### Why This Matters

**Without version pinning:**
- Your CI/CD pipeline might deploy different versions in dev vs staging vs production
- Rebuilding from scratch could give you a different application
- Breaking changes sneak in unexpectedly
- Debugging is nearly impossible ("which version was that?")
- Compliance and audit trails are broken

**With version pinning:**
- Reproducible deployments across all environments
- Explicit, reviewed version upgrades
- Complete audit trail
- Rollback to known-good versions
- Confidence in what you're deploying

---

## 📊 Chart Version vs App Version

Understanding the distinction between chart version and app version is critical.

### Chart Version

**What it is:** The version of the Helm chart packaging

**Example:** `nginx-15.0.0`

**What it includes:**
- Kubernetes manifests (Deployment, Service, ConfigMap, etc.)
- Helm templates with Go templating logic
- Default values.yaml
- Chart metadata (Chart.yaml)
- Helper templates and functions
- Hooks, tests, and other chart features

**When it changes:**
- Chart structure changes
- New template features added
- Bug fixes in templates
- New configuration options
- Kubernetes API version updates
- Chart maintainer makes improvements

### App Version

**What it is:** The version of the application inside the containers

**Example:** `1.25.3` (nginx application version)

**What it includes:**
- The actual nginx binary
- Application configuration
- Application dependencies

**When it changes:**
- Upstream application releases new version
- Security patches to application
- Bug fixes in application
- New application features

### Relationship Between Chart and App Versions

**Important:** Chart version and app version are **independent**!

| Chart Version | App Version | What Changed |
|--------------|-------------|--------------|
| `15.0.0` | `1.25.3` | Initial release |
| `15.0.1` | `1.25.3` | Chart bug fix (same nginx) |
| `15.0.2` | `1.25.3` | Added new template feature (same nginx) |
| `15.1.0` | `1.25.4` | Minor nginx upgrade |
| `16.0.0` | `1.26.0` | Breaking chart changes + new nginx |

**Why both versions matter:**

```bash
# You pin the CHART version
helm install my-app bitnami/nginx --version 15.0.0

# This chart version determines:
# 1. Which app version gets deployed (from chart's default)
# 2. What Kubernetes resources are created
# 3. What configuration options are available
```

**Checking both versions:**
```bash
# View chart version and app version
helm search repo bitnami/nginx --versions

# Output shows both:
# NAME            CHART VERSION  APP VERSION  DESCRIPTION
# bitnami/nginx   15.0.0         1.25.3       NGINX is a web server
# bitnami/nginx   14.2.1         1.25.2       NGINX is a web server
# bitnami/nginx   14.2.0         1.25.2       NGINX is a web server
```

**Real-world implication:**
```bash
# Scenario: Security vulnerability in nginx 1.25.2

# Bad approach: Upgrade to latest chart (might have breaking changes)
helm upgrade my-app bitnami/nginx

# Good approach: Find the minimum chart version with patched nginx
helm search repo bitnami/nginx --versions | grep "1.25.3"
# Result: Chart 15.0.0 has nginx 1.25.3

# Upgrade to specific safe version
helm upgrade my-app bitnami/nginx --version 15.0.0
```

---

## 🔍 Searching for Chart Versions

Helm provides powerful search capabilities to find available chart versions.

### Basic Version Search

**List all versions:**
```bash
helm search repo bitnami/nginx --versions
```

**Output format:**
```
NAME            CHART VERSION  APP VERSION  DESCRIPTION
bitnami/nginx   17.0.1         1.26.1       NGINX is a web server
bitnami/nginx   17.0.0         1.26.0       NGINX is a web server
bitnami/nginx   16.2.1         1.25.5       NGINX is a web server
bitnami/nginx   16.2.0         1.25.5       NGINX is a web server
```

### Filter by Chart Version

**Find specific chart version:**
```bash
helm search repo bitnami/nginx --version 15.0.0
```

**Find versions matching pattern:**
```bash
# All 15.x.x versions
helm search repo bitnami/nginx --versions | grep "^bitnami/nginx.*15\."

# All versions with nginx 1.25.x
helm search repo bitnami/nginx --versions | grep "1\.25\."
```

### JSON Output for Scripting

**Get structured data:**
```bash
helm search repo bitnami/nginx --versions -o json
```

**Output example:**
```json
[
  {
    "name": "bitnami/nginx",
    "version": "17.0.1",
    "app_version": "1.26.1",
    "description": "NGINX is a web server"
  },
  {
    "name": "bitnami/nginx",
    "version": "17.0.0",
    "app_version": "1.26.0",
    "description": "NGINX is a web server"
  }
]
```

**Use in scripts:**
```bash
# Get the 3rd most recent version (for testing upgrades)
CHART_VERSION=$(helm search repo bitnami/nginx --versions -o json | \
  python3 -c "import sys,json; versions=json.load(sys.stdin); \
  print(versions[2]['version'] if len(versions)>2 else versions[0]['version'])")

echo "Selected version: $CHART_VERSION"
```

### Finding Latest Stable Version

**Latest version (default behavior):**
```bash
helm search repo bitnami/nginx
# Shows only the latest version
```

**Check if update available:**
```bash
# Get current deployed version
CURRENT=$(helm list -n helm-scenarios -o json | \
  python3 -c "import sys,json; releases=json.load(sys.stdin); \
  [print(r['chart'].split('-')[-1]) for r in releases if r['name']=='my-nginx']")

# Get latest version
LATEST=$(helm search repo bitnami/nginx -o json | \
  python3 -c "import sys,json; print(json.load(sys.stdin)[0]['version'])")

echo "Current: $CURRENT"
echo "Latest: $LATEST"

if [ "$CURRENT" != "$LATEST" ]; then
  echo "Update available!"
fi
```

---

## 🎓 Installing with Version Pinning

### Basic Installation

**Pin chart version:**
```bash
helm install my-nginx bitnami/nginx \
  --version 15.0.0 \
  --namespace helm-scenarios \
  --create-namespace
```

**What happens:**
1. Helm searches local cache for bitnami/nginx chart version 15.0.0
2. If not cached, downloads from repository
3. Verifies chart version matches exactly 15.0.0
4. Renders templates with default values + any custom values
5. Applies manifests to cluster
6. Stores release metadata with chart version 15.0.0

### Installation with Custom Values

**Pin version and override values:**
```bash
helm install my-nginx bitnami/nginx \
  --version 15.0.0 \
  --namespace helm-scenarios \
  --set replicaCount=3 \
  --set resources.requests.cpu=100m \
  --set resources.requests.memory=128Mi \
  --wait \
  --timeout 120s
```

**Why --wait and --timeout:**
- `--wait`: Helm waits for all resources to be ready before completing
- `--timeout`: Maximum time to wait (fails if not ready by then)
- **Best practice:** Always use in production to catch deployment failures

### Verify Installed Version

**Check release information:**
```bash
helm list -n helm-scenarios
```

**Output shows:**
```
NAME       NAMESPACE       REVISION  STATUS    CHART         APP VERSION
my-nginx   helm-scenarios  1         deployed  nginx-15.0.0  1.25.3
```

**Get detailed version info:**
```bash
helm list -n helm-scenarios -o json | python3 -c "
import sys, json
releases = json.load(sys.stdin)
for r in releases:
    if r['name'] == 'my-nginx':
        print(f\"Release: {r['name']}\")
        print(f\"Chart: {r['chart']}\")
        print(f\"App Version: {r['app_version']}\")
        print(f\"Status: {r['status']}\")
        print(f\"Revision: {r['revision']}\")
"
```

### Prevent Accidental Unpinned Installs

**Pre-commit hook to enforce version pinning:**
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for helm install/upgrade commands without --version
if git diff --cached | grep -E "helm (install|upgrade)" | grep -v -- "--version"; then
  echo "ERROR: helm install/upgrade must use --version flag"
  exit 1
fi
```

**CI/CD pipeline check:**
```bash
# In your CI/CD pipeline
if ! echo "$HELM_COMMAND" | grep -q -- "--version"; then
  echo "ERROR: Helm command must include --version flag"
  exit 1
fi
```

---

## 🔄 Upgrading with Version Pinning

Upgrades should also use explicit version pinning for controlled, predictable updates.

### Basic Upgrade

**Upgrade to specific newer version:**
```bash
# Check current version first
helm list -n helm-scenarios

# Upgrade to specific target version
helm upgrade my-nginx bitnami/nginx \
  --version 16.0.0 \
  --namespace helm-scenarios \
  --wait \
  --timeout 120s
```

**What happens:**
1. Helm retrieves current release configuration (revision N)
2. Downloads chart version 16.0.0
3. Merges current values with chart 16.0.0 defaults
4. Renders templates
5. Performs rolling update to cluster resources
6. Creates new revision (N+1) with chart version 16.0.0

### Upgrade Strategy: Incremental Version Bumps

**Good practice:** Upgrade incrementally, not in big jumps

```bash
# Current version: 15.0.0
# Target version: 17.0.0
# Bad approach: Jump directly to 17.0.0

# Good approach: Incremental upgrades with validation
helm upgrade my-nginx bitnami/nginx --version 15.1.0 --wait
# Test application, verify everything works

helm upgrade my-nginx bitnami/nginx --version 16.0.0 --wait
# Test application again

helm upgrade my-nginx bitnami/nginx --version 17.0.0 --wait
# Final upgrade
```

**Why incremental:**
- Easier to identify which version introduced issues
- Smaller change sets = lower risk
- Can rollback to intermediate known-good state
- Follows semantic versioning expectations

### Upgrade with Values Reuse

**Helm preserves custom values across upgrades:**
```bash
# Initial install with custom values
helm install my-nginx bitnami/nginx \
  --version 15.0.0 \
  --set replicaCount=3 \
  --set service.type=NodePort

# Upgrade (custom values are preserved)
helm upgrade my-nginx bitnami/nginx \
  --version 16.0.0 \
  --reuse-values
```

**Caution with --reuse-values:**
- Preserves ALL previous values (including defaults from old chart)
- New chart defaults are NOT applied
- Can cause issues if new chart expects new required values

**Safer alternative: --reset-values:**
```bash
helm upgrade my-nginx bitnami/nginx \
  --version 16.0.0 \
  --reset-values \
  -f my-values.yaml
```

**This approach:**
- Starts fresh with new chart defaults
- Applies your custom values file
- Prevents stale values from old chart versions

### Dry Run Before Upgrade

**CRITICAL: Always dry-run production upgrades:**
```bash
helm upgrade my-nginx bitnami/nginx \
  --version 16.0.0 \
  --namespace helm-scenarios \
  --dry-run \
  --debug > /tmp/upgrade-preview.yaml
```

**Review the output:**
```bash
less /tmp/upgrade-preview.yaml
```

**Look for:**
- Changes to resource requests/limits
- New required configurations
- Deprecated API versions
- Breaking changes in manifests
- Unexpected resource deletions

### Upgrade with Diff Preview

**Install helm-diff plugin:**
```bash
helm plugin install https://github.com/databus23/helm-diff
```

**Preview exact changes:**
```bash
helm diff upgrade my-nginx bitnami/nginx \
  --version 16.0.0 \
  --namespace helm-scenarios
```

**Output shows:**
```diff
--- Deployment/my-nginx
+++ Deployment/my-nginx
   spec:
-    replicas: 1
+    replicas: 3
-    image: nginx:1.25.3
+    image: nginx:1.26.0
```

**Perfect for:**
- Code review in pull requests
- Understanding impact before applying
- Documentation of what changed
- Comparing chart versions

---

## 📜 Version History and Audit Trail

Helm tracks complete version history for every release.

### Viewing Release History

**Basic history:**
```bash
helm history my-nginx --namespace helm-scenarios
```

**Output:**
```
REVISION  UPDATED                   STATUS      CHART         DESCRIPTION
1         Mon Jan 15 10:00:00 2024  superseded  nginx-15.0.0  Install complete
2         Mon Jan 15 11:00:00 2024  superseded  nginx-15.1.0  Upgrade complete
3         Mon Jan 15 12:00:00 2024  deployed    nginx-16.0.0  Upgrade complete
```

**Detailed history with JSON:**
```bash
helm history my-nginx -n helm-scenarios -o json | python3 -c "
import sys, json
revisions = json.load(sys.stdin)
for rev in revisions:
    print(f\"Rev {rev['revision']}: {rev['chart']} - {rev['status']}\")
    print(f\"  Updated: {rev['updated']}\")
    print(f\"  Description: {rev['description']}\")
    print()
"
```

### Compare Version Changes

**Get values from specific revision:**
```bash
# Values from revision 1 (version 15.0.0)
helm get values my-nginx --revision 1 -n helm-scenarios

# Values from revision 3 (version 16.0.0)
helm get values my-nginx --revision 3 -n helm-scenarios
```

**Compare values between revisions:**
```bash
diff <(helm get values my-nginx --revision 1 -n helm-scenarios) \
     <(helm get values my-nginx --revision 3 -n helm-scenarios)
```

**Get manifest from specific revision:**
```bash
# See exactly what was deployed in revision 1
helm get manifest my-nginx --revision 1 -n helm-scenarios
```

### Version Progression Visualization

**Script to show version progression:**
```bash
#!/bin/bash
# show-version-history.sh

RELEASE=$1
NAMESPACE=$2

echo "Version History for $RELEASE"
echo "================================"

helm history $RELEASE -n $NAMESPACE -o json | python3 << 'EOF'
import sys, json
revisions = json.load(sys.stdin)

for i, rev in enumerate(revisions):
    chart_name, chart_version = rev['chart'].rsplit('-', 1)
    status_symbol = "✓" if rev['status'] == "deployed" else "○"

    print(f"{status_symbol} Rev {rev['revision']:2d}: v{chart_version:8s} ({rev['status']:10s}) - {rev['updated']}")

    if i < len(revisions) - 1:
        print("   ↓")
EOF
```

**Output example:**
```
Version History for my-nginx
================================
○ Rev  1: v15.0.0  (superseded) - Mon Jan 15 10:00:00 2024
   ↓
○ Rev  2: v15.1.0  (superseded) - Mon Jan 15 11:00:00 2024
   ↓
✓ Rev  3: v16.0.0  (deployed  ) - Mon Jan 15 12:00:00 2024
```

---

## 🔙 Rollback to Pinned Version

Rollback restores a previous chart version by creating a new revision.

### Basic Rollback

**Rollback to specific revision:**
```bash
# View history to choose revision
helm history my-nginx -n helm-scenarios

# Rollback to revision 1 (chart version 15.0.0)
helm rollback my-nginx 1 --namespace helm-scenarios --wait
```

**What happens:**
1. Helm retrieves configuration from revision 1
2. That revision has chart version 15.0.0
3. Renders templates using chart 15.0.0 and stored values
4. Applies to cluster (rolling update back to old version)
5. Creates NEW revision (e.g., revision 4) with chart 15.0.0

**Result:**
```
REVISION  STATUS      CHART         DESCRIPTION
1         superseded  nginx-15.0.0  Install complete
2         superseded  nginx-15.1.0  Upgrade complete
3         superseded  nginx-16.0.0  Upgrade complete
4         deployed    nginx-15.0.0  Rollback to 1
```

**Notice:** Revision 4 has same chart version as revision 1 (15.0.0)

### Rollback vs Fresh Install

**Rollback preserves history:**
```bash
helm rollback my-nginx 1 -n helm-scenarios
# Creates revision 4 with chart version from revision 1
# Full history preserved
```

**Fresh install loses history:**
```bash
helm uninstall my-nginx -n helm-scenarios
helm install my-nginx bitnami/nginx --version 15.0.0 -n helm-scenarios
# History starts from scratch
# All previous revisions lost
```

**When to use each:**
- **Rollback**: Temporary issue, want to revert quickly, need history
- **Fresh install**: Permanent change, want clean slate, history not needed

### Rollback with Version Verification

**Verify version after rollback:**
```bash
# Perform rollback
helm rollback my-nginx 1 -n helm-scenarios --wait

# Verify chart version
helm list -n helm-scenarios -o json | python3 -c "
import sys, json
releases = json.load(sys.stdin)
for r in releases:
    if r['name'] == 'my-nginx':
        chart_version = r['chart'].split('-')[-1]
        print(f\"Rolled back to chart version: {chart_version}\")
"

# Verify pods are running correct version
kubectl get pods -n helm-scenarios -l app.kubernetes.io/instance=my-nginx \
  -o jsonpath='{.items[0].spec.containers[0].image}'
```

### Emergency Rollback Procedure

**Production rollback checklist:**

```bash
#!/bin/bash
# emergency-rollback.sh

RELEASE="my-nginx"
NAMESPACE="helm-scenarios"

echo "🚨 EMERGENCY ROLLBACK INITIATED"
echo "================================"

# Step 1: View current state
echo "Current state:"
helm list -n $NAMESPACE -f $RELEASE

# Step 2: View history
echo -e "\nHistory:"
helm history $RELEASE -n $NAMESPACE

# Step 3: Confirm rollback target
read -p "Enter revision number to rollback to: " REVISION

# Step 4: Perform rollback
echo -e "\nRolling back to revision $REVISION..."
helm rollback $RELEASE $REVISION -n $NAMESPACE --wait --timeout 5m

# Step 5: Verify
echo -e "\nVerifying rollback..."
helm list -n $NAMESPACE -f $RELEASE

# Step 6: Check pod health
echo -e "\nPod status:"
kubectl get pods -n $NAMESPACE -l app.kubernetes.io/instance=$RELEASE

# Step 7: Test endpoint
echo -e "\nTesting endpoint..."
kubectl run curl-test --image=curlimages/curl --rm -i --restart=Never -- \
  curl -s http://$RELEASE.$NAMESPACE.svc.cluster.local

echo -e "\n✅ Rollback complete"
```

---

## 🏭 Production Best Practices

### 1. Always Pin Versions in Code

**Bad - Unpinned version:**
```yaml
# values.yaml or CI/CD script
helm install my-app bitnami/nginx
```

**Good - Pinned version:**
```yaml
# values.yaml
chartVersion: "15.0.0"

# CI/CD script
helm install my-app bitnami/nginx --version $CHART_VERSION
```

### 2. Version Lock Files

**Create a versions.yaml file:**
```yaml
# versions.yaml
releases:
  my-nginx:
    chart: bitnami/nginx
    version: "15.0.0"
    appVersion: "1.25.3"

  my-postgres:
    chart: bitnami/postgresql
    version: "12.5.0"
    appVersion: "15.3.0"

  my-redis:
    chart: bitnami/redis
    version: "17.11.3"
    appVersion: "7.0.11"
```

**Install from version lock file:**
```bash
#!/bin/bash
# install-from-lockfile.sh

CHART_NAME=$1
VERSION=$(yq eval ".releases.$CHART_NAME.version" versions.yaml)
CHART=$(yq eval ".releases.$CHART_NAME.chart" versions.yaml)

helm install $CHART_NAME $CHART --version $VERSION
```

### 3. Version Approval Process

**Workflow for version upgrades:**

```
1. Developer proposes upgrade
   ├─ Research release notes
   ├─ Check CHANGELOG
   └─ Test in dev environment

2. Create Pull Request
   ├─ Update versions.yaml
   ├─ Document changes
   └─ Run CI/CD tests

3. Review Process
   ├─ Security team reviews CVEs
   ├─ Ops team reviews changes
   └─ Tech lead approves

4. Staged Rollout
   ├─ Deploy to dev
   ├─ Deploy to staging (wait 24h)
   ├─ Deploy to production (canary)
   └─ Deploy to production (full)
```

### 4. Version Update Notifications

**Slack webhook for version updates:**
```bash
#!/bin/bash
# notify-version-update.sh

RELEASE=$1
OLD_VERSION=$2
NEW_VERSION=$3

curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d "{
    \"text\": \"🔄 Helm Release Updated\",
    \"attachments\": [{
      \"fields\": [
        {\"title\": \"Release\", \"value\": \"$RELEASE\", \"short\": true},
        {\"title\": \"Old Version\", \"value\": \"$OLD_VERSION\", \"short\": true},
        {\"title\": \"New Version\", \"value\": \"$NEW_VERSION\", \"short\": true},
        {\"title\": \"Environment\", \"value\": \"$ENVIRONMENT\", \"short\": true}
      ]
    }]
  }"
```

### 5. Automated Version Scanning

**Detect available updates:**
```bash
#!/bin/bash
# check-updates.sh

echo "Checking for chart updates..."
echo "=============================="

helm repo update

for release in $(helm list -A -o json | jq -r '.[].name'); do
  NAMESPACE=$(helm list -A -o json | jq -r ".[] | select(.name==\"$release\") | .namespace")
  CURRENT_CHART=$(helm list -n $NAMESPACE -o json | jq -r ".[] | select(.name==\"$release\") | .chart")
  CHART_NAME=$(echo $CURRENT_CHART | sed 's/-[0-9].*//')
  CURRENT_VERSION=$(echo $CURRENT_CHART | sed 's/.*-//')

  LATEST_VERSION=$(helm search repo $CHART_NAME -o json | jq -r '.[0].version')

  if [ "$CURRENT_VERSION" != "$LATEST_VERSION" ]; then
    echo "⚠️  $release: $CURRENT_VERSION -> $LATEST_VERSION (update available)"
  else
    echo "✓  $release: $CURRENT_VERSION (up to date)"
  fi
done
```

### 6. Version Documentation

**Maintain a CHART_VERSIONS.md file:**
```markdown
# Chart Version History

## my-nginx

| Date | Environment | Chart Version | App Version | Reason | Rollback Plan |
|------|-------------|---------------|-------------|--------|---------------|
| 2024-01-15 | prod | 15.0.0 | 1.25.3 | Initial release | N/A |
| 2024-01-20 | prod | 15.1.0 | 1.25.4 | Security patch CVE-2024-1234 | Rollback to 15.0.0 |
| 2024-02-01 | prod | 16.0.0 | 1.26.0 | New features, tested in staging | Rollback to 15.1.0 |
```

### 7. Semantic Versioning Awareness

**Understand chart version semantics:**

```
MAJOR.MINOR.PATCH
  │     │     │
  │     │     └─ Bug fixes, no breaking changes
  │     └─────── New features, backward compatible
  └───────────── Breaking changes, manual migration needed
```

**Version upgrade strategy:**

```bash
# PATCH upgrades (15.0.0 -> 15.0.1): Safe, low risk
helm upgrade my-app chart --version 15.0.1

# MINOR upgrades (15.0.0 -> 15.1.0): Test in staging first
helm upgrade my-app chart --version 15.1.0

# MAJOR upgrades (15.0.0 -> 16.0.0): Careful planning required
# 1. Read migration guide
# 2. Test in dev
# 3. Test in staging
# 4. Plan rollback strategy
# 5. Upgrade during maintenance window
helm upgrade my-app chart --version 16.0.0
```

### 8. Multi-Environment Version Strategy

**Different version strategies per environment:**

```yaml
# environments/dev.yaml
# Dev uses latest to catch issues early
chartVersion: "latest"  # Actually pinned to specific version in CI/CD

# environments/staging.yaml
# Staging uses N-1 version (one behind latest)
chartVersion: "16.0.0"

# environments/production.yaml
# Production uses N-2 version (proven stable)
chartVersion: "15.1.0"
```

**Promotion pipeline:**
```
Dev (16.1.0) → Test 1 week → Staging (16.1.0) → Test 1 week → Prod (16.1.0)
```

---

## 🐛 Troubleshooting Version Issues

### Version Not Found

**Symptom:**
```bash
helm install my-app bitnami/nginx --version 15.0.0
# Error: chart "nginx" matching 15.0.0 not found in bitnami index
```

**Causes:**
1. Repository index is outdated
2. Version doesn't exist
3. Typo in version number
4. Wrong repository

**Solutions:**

**Solution 1: Update repository cache**
```bash
helm repo update
helm search repo bitnami/nginx --versions | head -20
```

**Solution 2: Verify version exists**
```bash
# Check if version ever existed
helm search repo bitnami/nginx --versions | grep "15.0.0"
```

**Solution 3: Check repository URL**
```bash
helm repo list
# Ensure bitnami repository is added correctly
```

### Wrong Version Deployed

**Symptom:**
```bash
helm install my-app bitnami/nginx --version 15.0.0
helm list
# Shows different version than expected
```

**Diagnosis:**
```bash
# Check what was actually installed
helm list -o json | jq '.[] | {name: .name, chart: .chart}'

# Check values used
helm get values my-app --all

# Check chart that was pulled
helm pull bitnami/nginx --version 15.0.0 --untar
cat nginx/Chart.yaml
```

**Common causes:**
- Cached chart version mismatch
- Repository index corruption
- Race condition in CI/CD

**Solution:**
```bash
# Clear Helm cache
rm -rf ~/.cache/helm
rm -rf ~/.local/share/helm

# Update repos
helm repo update

# Retry installation
helm install my-app bitnami/nginx --version 15.0.0
```

### Version Mismatch Between Environments

**Symptom:**
Production runs v15.0.0, but staging runs v16.0.0, causing inconsistencies.

**Prevention:**
```bash
#!/bin/bash
# verify-version-consistency.sh

DEV_VERSION=$(helm list -n dev -o json | jq -r '.[] | select(.name=="my-app") | .chart')
STAGING_VERSION=$(helm list -n staging -o json | jq -r '.[] | select(.name=="my-app") | .chart')
PROD_VERSION=$(helm list -n prod -o json | jq -r '.[] | select(.name=="my-app") | .chart')

echo "Dev:     $DEV_VERSION"
echo "Staging: $STAGING_VERSION"
echo "Prod:    $PROD_VERSION"

if [ "$DEV_VERSION" != "$STAGING_VERSION" ] || [ "$STAGING_VERSION" != "$PROD_VERSION" ]; then
  echo "⚠️  WARNING: Version mismatch detected!"
  exit 1
fi

echo "✓ All environments in sync"
```

### Upgrade Blocked by Version Constraint

**Symptom:**
```bash
helm upgrade my-app bitnami/nginx --version 17.0.0
# Error: chart requires Kubernetes version >=1.23
```

**Check Kubernetes version:**
```bash
kubectl version --short
```

**Check chart requirements:**
```bash
helm show chart bitnami/nginx --version 17.0.0 | grep kubeVersion
```

**Solutions:**
1. Upgrade Kubernetes cluster
2. Use older chart version compatible with your Kubernetes
3. Override version constraint (risky)

```bash
# Find compatible version
helm search repo bitnami/nginx --versions | head -20
helm show chart bitnami/nginx --version 16.0.0 | grep kubeVersion
```

---

## 📊 Version Pinning Patterns

### Pattern 1: Lock File with Git

**Structure:**
```
repo/
├── charts/
│   └── versions-lock.yaml
├── environments/
│   ├── dev.yaml
│   ├── staging.yaml
│   └── production.yaml
└── scripts/
    ├── install.sh
    └── upgrade.sh
```

**versions-lock.yaml:**
```yaml
# Managed by Helm. Last updated: 2024-01-15
releases:
  nginx:
    repository: bitnami/nginx
    chart: nginx
    version: "15.0.0"
    appVersion: "1.25.3"
    digest: "sha256:abcdef123456..."  # Chart digest for extra verification

  postgresql:
    repository: bitnami/postgresql
    chart: postgresql
    version: "12.5.0"
    appVersion: "15.3.0"
    digest: "sha256:123456abcdef..."
```

**Install script:**
```bash
#!/bin/bash
# scripts/install.sh

RELEASE=$1
ENVIRONMENT=$2

CHART=$(yq eval ".releases.$RELEASE.chart" charts/versions-lock.yaml)
VERSION=$(yq eval ".releases.$RELEASE.version" charts/versions-lock.yaml)
REPO=$(yq eval ".releases.$RELEASE.repository" charts/versions-lock.yaml)

helm install $RELEASE $REPO \
  --version $VERSION \
  -f environments/$ENVIRONMENT.yaml \
  --wait
```

### Pattern 2: Infrastructure as Code (Terraform/Pulumi)

**Terraform example:**
```hcl
# terraform/helm-releases.tf

variable "chart_versions" {
  type = map(string)
  default = {
    nginx      = "15.0.0"
    postgresql = "12.5.0"
    redis      = "17.11.3"
  }
}

resource "helm_release" "nginx" {
  name       = "my-nginx"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "nginx"
  version    = var.chart_versions.nginx
  namespace  = "production"

  values = [
    file("values/nginx-production.yaml")
  ]
}
```

**Benefits:**
- Version changes tracked in git
- Terraform state tracks versions
- Plan shows version changes before apply

### Pattern 3: GitOps with ArgoCD/FluxCD

**ArgoCD Application manifest:**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-nginx
spec:
  source:
    repoURL: https://charts.bitnami.com/bitnami
    chart: nginx
    targetRevision: "15.0.0"  # ← Pinned version
    helm:
      values: |
        replicaCount: 3
        resources:
          requests:
            cpu: 100m
            memory: 128Mi

  destination:
    server: https://kubernetes.default.svc
    namespace: production

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**FluxCD HelmRelease manifest:**
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: my-nginx
  namespace: production
spec:
  chart:
    spec:
      chart: nginx
      version: "15.0.0"  # ← Pinned version
      sourceRef:
        kind: HelmRepository
        name: bitnami

  values:
    replicaCount: 3
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
```

**Benefits:**
- Git is source of truth for versions
- Pull requests for version updates
- Automated rollback on failures
- Complete audit trail via git history

### Pattern 4: Renovate Bot for Automated Updates

**renovate.json:**
```json
{
  "extends": ["config:base"],
  "helm-values": {
    "fileMatch": ["charts/.*\\.yaml$"]
  },
  "packageRules": [
    {
      "matchDatasources": ["helm"],
      "matchUpdateTypes": ["patch"],
      "automerge": true,
      "automergeType": "branch"
    },
    {
      "matchDatasources": ["helm"],
      "matchUpdateTypes": ["minor"],
      "automerge": false,
      "schedule": ["every weekend"]
    },
    {
      "matchDatasources": ["helm"],
      "matchUpdateTypes": ["major"],
      "automerge": false,
      "reviewers": ["@platform-team"]
    }
  ]
}
```

**Benefits:**
- Automatic pull requests for version updates
- Different strategies for patch/minor/major
- Can auto-merge patch updates
- Security updates applied quickly

---

## 🎯 Complete Workflow Example

### End-to-End Production Version Management

**Step 1: Initial deployment with version pinning**
```bash
# Research available versions
helm repo update
helm search repo bitnami/nginx --versions | head -10

# Choose stable version (not bleeding edge)
CHART_VERSION="15.0.0"

# Document decision
cat >> CHANGELOG.md << EOF
## 2024-01-15 - my-nginx v15.0.0
- Initial deployment
- Chart: bitnami/nginx 15.0.0
- App: nginx 1.25.3
- Config: 3 replicas, 100m CPU, 128Mi memory
EOF

# Install with pinned version
helm install my-nginx bitnami/nginx \
  --version $CHART_VERSION \
  --namespace production \
  --create-namespace \
  -f values-production.yaml \
  --wait \
  --timeout 5m

# Verify
helm list -n production
```

**Step 2: Regular version monitoring**
```bash
# Weekly check for updates (cron job)
#!/bin/bash
# /etc/cron.weekly/helm-version-check

helm repo update

CURRENT=$(helm list -n production -o json | jq -r '.[] | select(.name=="my-nginx") | .chart' | sed 's/.*-//')
LATEST=$(helm search repo bitnami/nginx -o json | jq -r '.[0].version')

if [ "$CURRENT" != "$LATEST" ]; then
  echo "Update available: $CURRENT -> $LATEST"

  # Get changelog
  echo "Changes:"
  helm show readme bitnami/nginx --version $LATEST | grep -A 50 "Upgrading"

  # Notify team
  slack_notify "Helm update available: my-nginx $CURRENT -> $LATEST"
fi
```

**Step 3: Version upgrade process**
```bash
# 1. Create upgrade proposal
cat > upgrades/nginx-15.1.0-proposal.md << EOF
# Upgrade Proposal: nginx 15.0.0 -> 15.1.0

## Motivation
Security patch for CVE-2024-1234

## Changes
- nginx: 1.25.3 -> 1.25.4
- Fixed memory leak in HTTP/2
- Improved error handling

## Risk Assessment
- Low risk (patch version)
- Tested in dev for 1 week
- No breaking changes

## Rollback Plan
helm rollback my-nginx 1 --namespace production --wait

## Testing Checklist
- [ ] Health check endpoint responds
- [ ] All pods running
- [ ] No error logs
- [ ] Response time < 100ms
EOF

# 2. Test in dev environment
helm upgrade my-nginx bitnami/nginx \
  --version 15.1.0 \
  --namespace dev \
  -f values-dev.yaml \
  --wait

# Run tests
./tests/smoke-tests.sh dev

# 3. Preview production changes
helm diff upgrade my-nginx bitnami/nginx \
  --version 15.1.0 \
  --namespace production \
  -f values-production.yaml

# 4. Upgrade staging
helm upgrade my-nginx bitnami/nginx \
  --version 15.1.0 \
  --namespace staging \
  -f values-staging.yaml \
  --wait

# Wait 24 hours, monitor metrics

# 5. Upgrade production (during maintenance window)
# Announce to team
slack_notify "Starting my-nginx upgrade: 15.0.0 -> 15.1.0"

# Backup current state
helm get values my-nginx -n production > backup-values-$(date +%Y%m%d).yaml
helm get manifest my-nginx -n production > backup-manifest-$(date +%Y%m%d).yaml

# Perform upgrade
helm upgrade my-nginx bitnami/nginx \
  --version 15.1.0 \
  --namespace production \
  -f values-production.yaml \
  --wait \
  --timeout 5m

# Verify
kubectl get pods -n production -l app.kubernetes.io/instance=my-nginx
curl https://nginx.production.example.com/health

# Update documentation
cat >> CHANGELOG.md << EOF
## 2024-01-22 - my-nginx v15.1.0
- Upgraded from 15.0.0
- Security patch CVE-2024-1234
- Chart: bitnami/nginx 15.1.0
- App: nginx 1.25.4
EOF

# Notify success
slack_notify "✅ my-nginx upgraded successfully: 15.1.0 deployed"
```

**Step 4: Monitor and validate**
```bash
# Post-upgrade validation
./scripts/validate-deployment.sh production my-nginx

# Monitor for 1 hour
watch kubectl get pods -n production -l app.kubernetes.io/instance=my-nginx

# Check metrics
curl https://metrics.example.com/api/v1/query?query=nginx_up

# If issues detected, rollback
if [ $ISSUES_DETECTED -eq 1 ]; then
  helm rollback my-nginx --namespace production --wait
  slack_notify "⚠️ Rolled back my-nginx due to issues"
fi
```

---

## 🔗 Integration with Other Tools

### Helm with CI/CD Pipelines

**GitHub Actions example:**
```yaml
# .github/workflows/helm-deploy.yml
name: Deploy with Helm

on:
  push:
    branches: [main]
    paths:
      - 'charts/versions.yaml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Helm
        uses: azure/setup-helm@v3
        with:
          version: '3.12.0'

      - name: Extract version from lock file
        id: version
        run: |
          VERSION=$(yq eval '.releases.nginx.version' charts/versions.yaml)
          echo "version=$VERSION" >> $GITHUB_OUTPUT

      - name: Helm diff
        run: |
          helm plugin install https://github.com/databus23/helm-diff
          helm diff upgrade my-nginx bitnami/nginx \
            --version ${{ steps.version.outputs.version }} \
            -f values-production.yaml

      - name: Helm upgrade
        run: |
          helm upgrade my-nginx bitnami/nginx \
            --version ${{ steps.version.outputs.version }} \
            --namespace production \
            -f values-production.yaml \
            --wait \
            --timeout 5m

      - name: Notify Slack
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Helm deploy: my-nginx ${{ steps.version.outputs.version }}'
```

### Helm with Monitoring

**Prometheus alert for version drift:**
```yaml
# prometheus-alerts.yml
groups:
  - name: helm-versions
    interval: 5m
    rules:
      - alert: HelmVersionDrift
        expr: |
          count by (release, namespace) (
            kube_pod_labels{label_helm_sh_chart=~"nginx-15.*"}
          ) > 0
          AND
          count by (release, namespace) (
            kube_pod_labels{label_helm_sh_chart=~"nginx-16.*"}
          ) > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Version drift detected in {{ $labels.release }}"
          description: "Multiple chart versions running simultaneously"
```

---

## 📚 Key Takeaways

### Critical Points

1. **Always pin versions** - Never use latest in production
2. **Chart version ≠ App version** - Understand both
3. **Test before upgrading** - Use staging environments
4. **Keep version history** - Full audit trail is essential
5. **Automate version tracking** - Use lock files and git
6. **Monitor for updates** - Regular version checks
7. **Document upgrades** - Why, what, when, rollback plan
8. **Practice rollbacks** - Know how to revert quickly

### Version Pinning Checklist

- [ ] All Helm installs use `--version` flag
- [ ] Version lock file exists and is in git
- [ ] CI/CD enforces version pinning
- [ ] Version approval process defined
- [ ] Staging environment for testing upgrades
- [ ] Rollback procedures documented
- [ ] Monitoring for version drift
- [ ] Regular version update reviews scheduled

---

## 🔗 Further Reading

### Official Documentation
- **Helm Versioning**: https://helm.sh/docs/topics/charts/#the-chartyaml-file
- **Helm Install**: https://helm.sh/docs/helm/helm_install/
- **Helm Upgrade**: https://helm.sh/docs/helm/helm_upgrade/
- **Helm Search**: https://helm.sh/docs/helm/helm_search/
- **Chart Repository Guide**: https://helm.sh/docs/topics/chart_repository/

### Best Practices
- **Semantic Versioning**: https://semver.org/
- **GitOps with Helm**: https://www.weave.works/technologies/gitops/
- **Helm Security Best Practices**: https://helm.sh/docs/topics/security/

### Tools
- **Helm Diff Plugin**: https://github.com/databus23/helm-diff
- **Renovate Bot**: https://docs.renovatebot.com/
- **ArgoCD**: https://argo-cd.readthedocs.io/
- **FluxCD**: https://fluxcd.io/

### Related Helm Scenarios
- **Scenario 02**: Upgrade and Rollback - Hands-on with upgrades
- **Scenario 09**: Helm Diff - Preview changes before applying
- **Scenario 08**: Production Pipeline - Complete CI/CD integration

---

*This guide covers everything you need to know about Helm version pinning, from basic concepts to production-ready workflows. Version pinning is a non-negotiable best practice for reliable, reproducible Kubernetes deployments!*
