# Scenario 05: Kustomize Environments

## Overview

This scenario demonstrates how ArgoCD integrates with Kustomize to manage multiple environments (dev and prod) from a single set of base manifests. Kustomize is a Kubernetes-native configuration management tool that uses a base/overlay pattern to customize resources without modifying the originals.

## What You Will Learn

- How Kustomize base/overlay pattern works
- How ArgoCD natively detects and builds Kustomize configurations
- How to manage multiple environments (dev, prod) using overlays
- Environment promotion via GitOps

## Architecture

```
base/
  deployment.yaml    # Common deployment (1 replica, nginx:1.21-alpine)
  service.yaml       # Common ClusterIP service
  kustomization.yaml # References base resources

overlays/
  dev/
    kustomization.yaml  # Dev: 1 replica, minimal resources, dev- prefix
  prod/
    kustomization.yaml  # Prod: 3 replicas, higher resources, prod- prefix
```

## How It Works

1. **Base manifests** define the common deployment and service shared across all environments.
2. **Overlays** customize the base for each environment using JSON patches:
   - `namePrefix` adds environment-specific prefixes to resource names
   - `commonLabels` adds environment labels to all resources
   - `patches` modify replica counts, resource limits, etc.
3. **ArgoCD Applications** point to different overlay paths, each deploying to its own namespace.

## Kustomize vs Helm

For simple environment differentiation, Kustomize has several advantages over Helm:

- **No templating language** -- uses plain YAML with patches
- **Native to kubectl** -- `kubectl apply -k` works out of the box
- **ArgoCD auto-detection** -- ArgoCD automatically detects `kustomization.yaml` files
- **Lower complexity** -- no chart packaging, no values files, no template syntax
- **Easier to review** -- patches show exactly what changes between environments

Helm is better suited for complex parameterization, reusable charts, and dependency management.

## Key Concepts

- **DRY Principle**: Base manifests are written once; overlays only specify differences.
- **Environment Promotion**: Promoting from dev to prod means creating a new overlay, not duplicating manifests.
- **GitOps**: Each environment has its own ArgoCD Application pointing to its overlay path. Changes to any overlay trigger automatic sync.

## Files

| File | Purpose |
|------|---------|
| `application-dev.yaml` | ArgoCD Application CR for dev environment |
| `application-prod.yaml` | ArgoCD Application CR for prod environment |
| `base/deployment.yaml` | Base nginx deployment |
| `base/service.yaml` | Base ClusterIP service |
| `base/kustomization.yaml` | Base Kustomize configuration |
| `overlays/dev/kustomization.yaml` | Dev overlay (1 replica, minimal resources) |
| `overlays/prod/kustomization.yaml` | Prod overlay (3 replicas, higher resources) |
| `commands.json` | Step-by-step guided commands |
