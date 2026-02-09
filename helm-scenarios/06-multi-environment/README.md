# Scenario 06: Multi-Environment Deployments

## Objective
Learn how to use multiple values files to deploy the same Helm chart to different environments (dev, staging, prod) with appropriate configurations for each. This is a core Helm pattern used in every production workflow.

## What You Will Learn
- Using `-f` / `--values` to override default values
- Layering multiple values files (defaults -> environment-specific)
- Environment-specific resource configurations
- How to manage replicas, logging, resources, and scheduling per environment
- Comparing deployments across environments

## Prerequisites
- Helm 3 installed
- Kind cluster running with 3 nodes
- `kubectl` configured to talk to your cluster

## Key Concepts

### Values File Layering
Helm merges values files in order. Later files override earlier ones:
```bash
helm install myapp ./chart \
  -f values.yaml \          # Base defaults (implicit)
  -f values-prod.yaml       # Production overrides
```

### Environment Differences
| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| Replicas | 1 | 2 | 3 |
| Log Level | debug | warn | info |
| Resources | None | Moderate | Strict |
| Anti-Affinity | No | No | Yes |
| Debug Mode | On | Off | Off |

## Chart Structure
```
06-multi-environment/
  Chart.yaml
  values.yaml           # Base defaults
  values-dev.yaml       # Dev overrides (minimal resources)
  values-staging.yaml   # Staging overrides (moderate)
  values-prod.yaml      # Prod overrides (strict resources, HA)
  templates/
    _helpers.tpl
    deployment.yaml
    service.yaml
    configmap.yaml
```

## Duration
20 minutes

## Difficulty
Medium
