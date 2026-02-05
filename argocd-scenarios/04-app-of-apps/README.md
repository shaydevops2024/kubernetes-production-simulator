# Scenario 04: App-of-Apps Pattern

## Overview
Learn the App-of-Apps pattern, one of the most powerful patterns in ArgoCD for managing multiple applications. A single parent Application manages child Application CRs, enabling hierarchical deployment of entire platforms.

## What You Will Learn
- How the App-of-Apps pattern works
- Parent and child Application relationship
- Cascading sync and delete behavior
- When and why to use this pattern in production

## Key Concepts

### The App-of-Apps Pattern
Instead of manually creating each ArgoCD Application, you create a single "parent" Application that points to a directory containing child Application CRs. When ArgoCD syncs the parent, it creates all child Applications automatically.

### Parent Application
The parent Application points to a directory containing Application CRs (not Kubernetes workload manifests). Its destination is the `argocd` namespace because Application CRs must live in the ArgoCD namespace.

### Child Applications
Each child Application is a standard ArgoCD Application CR that points to its own manifests directory. Children are independently managed - they have their own sync policies, health status, and history.

### Cascading Behavior
- **Sync**: When the parent syncs, it creates/updates child Application CRs
- **Prune**: When a child Application CR is removed from Git, the parent prunes it
- **Delete**: Deleting the parent can cascade to delete children (with prune enabled)

## When to Use App-of-Apps
- Managing microservices platforms with many services
- Organizing applications by team, environment, or tier
- Providing a single entry point for deploying an entire stack
- Enabling self-service onboarding (teams add their own child App CR)
- Managing multi-cluster deployments from a single control plane

## Architecture
```
Parent Application (sc04-parent-app)
  |
  |-- children/frontend-app.yaml --> sc04-frontend Application
  |     |-- manifests/frontend/deployment.yaml
  |     |-- manifests/frontend/service.yaml
  |
  |-- children/backend-app.yaml  --> sc04-backend Application
        |-- manifests/backend/deployment.yaml
        |-- manifests/backend/service.yaml
```

## Prerequisites
- ArgoCD installed and accessible at http://localhost:30800
- Git repository accessible from the cluster
