# Scenario 05: Helm Hooks

## Objective
Learn how Helm hooks control the lifecycle of a release by running Jobs at specific points during install, upgrade, and delete operations. Hooks let you perform tasks like database migrations before your app starts, or smoke tests after deployment.

## What You Will Learn
- How Helm hook annotations work (`helm.sh/hook`)
- Hook types: `pre-install`, `post-install`, `pre-delete`
- Hook weights for ordering multiple hooks
- Hook deletion policies (`helm.sh/hook-delete-policy`)
- How hooks interact with the release lifecycle

## Prerequisites
- Helm 3 installed
- Kind cluster running with 3 nodes
- `kubectl` configured to talk to your cluster

## Key Concepts

### Hook Annotations
Helm hooks are regular Kubernetes resources (usually Jobs) with special annotations:

```yaml
annotations:
  "helm.sh/hook": pre-install        # When to run
  "helm.sh/hook-weight": "0"         # Order (lower runs first)
  "helm.sh/hook-delete-policy": hook-succeeded  # When to clean up
```

### Hook Types
| Hook | When It Runs |
|------|-------------|
| `pre-install` | After templates are rendered, before any resources are created |
| `post-install` | After all resources are loaded into Kubernetes |
| `pre-delete` | Before any resources are deleted from Kubernetes |
| `pre-upgrade` | After templates are rendered, before any resources are updated |
| `post-upgrade` | After all resources are updated |

### Hook Execution Flow
```
helm install
  -> render templates
  -> run pre-install hooks (wait for completion)
  -> create Kubernetes resources
  -> run post-install hooks (wait for completion)
  -> release is "deployed"
```

## Chart Structure
```
05-helm-hooks/
  Chart.yaml
  values.yaml
  templates/
    _helpers.tpl
    deployment.yaml
    service.yaml
    pre-install-job.yaml    # DB migration hook
    post-install-job.yaml   # Smoke test hook
```

## Duration
20 minutes

## Difficulty
Medium
