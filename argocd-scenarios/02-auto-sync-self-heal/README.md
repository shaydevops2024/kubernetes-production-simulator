# Scenario 02: Auto-Sync and Self-Heal with ArgoCD

## Overview
Explore ArgoCD automated sync policies and self-healing capabilities. Learn how ArgoCD can automatically deploy changes from Git and revert any manual drift in the cluster.

## What You Will Learn
- How automated sync deploys changes without manual intervention
- How self-heal detects and reverts configuration drift
- The difference between prune and self-heal policies
- Why self-heal is critical for production environments

## Key Concepts

### Automated Sync Policy
When `automated` is enabled in the syncPolicy, ArgoCD continuously monitors the Git repository and automatically applies changes to the cluster. No manual sync button clicks needed.

### Self-Heal
With `selfHeal: true`, ArgoCD monitors the live cluster state and compares it to the desired state in Git. If someone manually changes a resource (e.g., scaling replicas, modifying environment variables), ArgoCD will automatically revert the change to match Git.

### Prune
With `prune: true`, ArgoCD will delete resources from the cluster that are no longer defined in the Git repository. Without prune, removed manifests would leave orphaned resources in the cluster.

## Why Self-Heal Matters in Production
- Prevents configuration drift caused by manual kubectl changes
- Ensures the cluster always matches the declared state in Git
- Provides an audit trail of all changes through Git history
- Reduces "snowflake" environments where clusters diverge from their intended configuration

## Architecture
ArgoCD runs a reconciliation loop that continuously compares the live cluster state with the desired state in Git. When drift is detected, self-heal triggers an automatic sync to restore the desired state.

## Prerequisites
- ArgoCD installed and accessible at http://localhost:30800
- Git repository accessible from the cluster
