# Scenario 07: Secrets Management in Helm

## Objective
Learn the challenges and approaches for managing secrets with Helm. You will explore passing secrets via `--set`, values files, the `lookup` function to preserve existing secrets, and understand why external tools like sealed-secrets are the recommended approach for production.

## What You Will Learn
- How `--set` passes secrets (and why it is dangerous)
- Why secrets in values files are also risky
- The Helm `lookup` function to avoid overwriting existing secrets
- Sealed-secrets as a production best practice
- How Helm stores release data (including secrets!) in cluster

## Prerequisites
- Helm 3 installed
- Kind cluster running with 3 nodes
- `kubectl` configured to talk to your cluster

## Key Concepts

### The Secrets Problem
Helm charts often need secrets (database passwords, API keys, TLS certs). But:
1. `--set` flags are saved in Helm release history (visible with `helm get values`)
2. Values files with secrets get committed to Git
3. Kubernetes Secrets are only base64-encoded, not encrypted

### Approaches (Least to Most Secure)

| Approach | Security | Ease of Use | Production Ready |
|----------|----------|-------------|------------------|
| `--set` on CLI | Poor | Easy | No |
| Values file | Poor | Easy | No |
| `lookup` function | Medium | Medium | Partial |
| Sealed Secrets | High | Medium | Yes |
| External Secrets Operator | High | Medium | Yes |
| CSI Secret Store | High | Complex | Yes |

### The lookup Function
```yaml
# Check if secret already exists, reuse it instead of overwriting
{{- $existingSecret := lookup "v1" "Secret" .Release.Namespace "my-secret" -}}
{{- if $existingSecret }}
  # Reuse existing secret data
{{- else }}
  # Create new secret from values
{{- end }}
```

## Chart Structure
```
07-secrets-management/
  Chart.yaml
  values.yaml
  templates/
    _helpers.tpl
    deployment.yaml
    secret.yaml
```

## Duration
25 minutes

## Difficulty
Hard
