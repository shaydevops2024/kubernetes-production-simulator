# Scenario 06: Helm Chart Deployment

## Overview

This scenario demonstrates how ArgoCD deploys applications from Helm chart repositories. Instead of pointing to a Git repository containing raw manifests, the ArgoCD Application CR references a Helm chart directly from a chart repository (Bitnami) and provides value overrides inline.

## What You Will Learn

- How ArgoCD integrates with Helm chart repositories
- Declarative Helm management without the helm CLI
- How to override Helm values in the Application CR
- How ArgoCD renders and tracks Helm-generated resources

## How ArgoCD Renders Helm Charts

When ArgoCD encounters a Helm source, it:

1. **Fetches** the chart from the specified `repoURL` and `chart` name
2. **Renders** the chart templates using the provided `values` overrides
3. **Applies** the rendered manifests to the target namespace
4. **Tracks** all generated resources in the ArgoCD resource tree

This is equivalent to running `helm template` + `kubectl apply`, but fully declarative and continuously reconciled.

## Declarative Helm Management

Traditional Helm workflow:
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install my-release bitnami/nginx -f values.yaml
```

ArgoCD GitOps workflow:
```yaml
# Everything is declared in the Application CR
source:
  repoURL: https://charts.bitnami.com/bitnami
  chart: nginx
  targetRevision: "*"
  helm:
    values: |
      replicaCount: 2
```

### Advantages of Declarative Helm

- **No imperative commands** -- the Application CR is the single source of truth
- **Version controlled** -- Helm values are stored in Git alongside the Application CR
- **Auto-sync** -- ArgoCD continuously ensures the deployed state matches the declared values
- **Self-healing** -- manual changes to Helm-deployed resources are automatically reverted
- **Audit trail** -- all value changes are tracked through Git history

## Value Overrides

ArgoCD supports multiple ways to override Helm values:

1. **Inline values** (used in this scenario): Values embedded directly in the Application CR
2. **Values files**: Reference values files from a Git repository
3. **Parameters**: Individual key-value parameter overrides

## Chart Version Control

The `targetRevision` field controls which chart version to deploy:
- `"*"` -- always use the latest version
- `"15.x"` -- use the latest patch in the 15.x series
- `"15.3.1"` -- pin to an exact version

## Files

| File | Purpose |
|------|---------|
| `application.yaml` | ArgoCD Application CR with Helm chart source |
| `commands.json` | Step-by-step guided commands |
