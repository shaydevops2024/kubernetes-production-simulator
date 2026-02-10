# Parameterized Builds

Create flexible pipelines with user-defined parameters, conditional stage execution, and environment-specific deployments.

## Learning Objectives
- Define pipeline parameters: string, choice, boolean, password, and text types
- Use when{} blocks to conditionally skip or execute stages based on parameter values
- Combine conditions with allOf (AND) and anyOf (OR) logic
- Build one pipeline that handles dev, staging, and production with different behaviors
- Deploy with environment-specific ConfigMaps driven by parameters

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible
- Namespace: jenkins-scenarios (created automatically)

## Resources Created
- Namespace: jenkins-scenarios
- ConfigMap: app-config-staging (environment-specific settings)
- Deployment: parameterized-app (2 replicas, nginx:1.25-alpine)
- Service: parameterized-app-svc (ClusterIP, port 80)

## Cleanup
Run the cleanup command (Step 8) to remove all resources created in this scenario.
