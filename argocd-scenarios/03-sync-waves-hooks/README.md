# Scenario 03: Sync Waves and Hooks

## Overview
Learn how to control the order of resource deployment using ArgoCD sync waves, and how to run pre/post deployment tasks using sync hooks. This is essential for applications with resource dependencies.

## What You Will Learn
- How sync waves control deployment ordering
- How PreSync, Sync, and PostSync hooks work
- Hook delete policies and their impact
- Real-world use cases for ordered deployments

## Key Concepts

### Sync Waves
Sync waves allow you to define the order in which resources are deployed. Each resource can have an `argocd.argoproj.io/sync-wave` annotation with a numeric value. Resources with lower wave numbers are deployed first.

- **Wave -1**: ConfigMaps, Secrets, and other prerequisites
- **Wave 0** (default): Main application resources like Deployments
- **Wave 1**: Services, Ingresses, and other dependent resources
- **Wave 2+**: Post-deployment resources

ArgoCD waits for each wave to become healthy before proceeding to the next wave.

### Sync Hooks
Hooks are resources that run at specific phases of the sync process:

- **PreSync**: Runs before the main sync (e.g., database migrations, schema changes)
- **Sync**: Runs during the main sync phase
- **PostSync**: Runs after all resources are synced (e.g., smoke tests, notifications)
- **SyncFail**: Runs if the sync fails (e.g., alerting, rollback triggers)

### Hook Delete Policies
- **HookSucceeded**: Delete the hook resource after it succeeds
- **HookFailed**: Delete the hook resource after it fails
- **BeforeHookCreation**: Delete any existing hook resource before creating a new one

## Use Cases
- Database migrations before application updates (PreSync)
- Creating ConfigMaps/Secrets before Deployments that reference them
- Running smoke tests after deployment (PostSync)
- Sending deployment notifications (PostSync)
- Cleaning up temporary resources in order

## Architecture
In this scenario, the sync order is:
1. ConfigMap (wave -1) - Application configuration
2. Deployment (wave 0) - Main application pods
3. Service (wave 1) - Network exposure
4. PostSync Job - Verification after deployment

## Prerequisites
- ArgoCD installed and accessible at http://localhost:30800
- Git repository accessible from the cluster
