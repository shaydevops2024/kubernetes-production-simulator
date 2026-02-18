# Scenario 11: Canary Rollout (Argo Rollouts)

## Overview

This scenario demonstrates progressive delivery using Argo Rollouts integrated with ArgoCD. Argo Rollouts extends Kubernetes with advanced deployment strategies like canary and blue-green deployments, which are not available with standard Kubernetes Deployments.

## What is Argo Rollouts?

Argo Rollouts is a Kubernetes controller and set of CRDs that provides advanced deployment capabilities:

- **Canary Deployments**: Gradually shift traffic from old version to new version
- **Blue-Green Deployments**: Run two versions simultaneously and switch traffic instantly
- **Analysis Runs**: Automated analysis to determine if a rollout should proceed or abort
- **Traffic Management**: Integration with service meshes and ingress controllers for fine-grained traffic control

## Canary vs Blue-Green

### Canary Strategy
- Gradually increases traffic to the new version in defined steps (e.g., 25% -> 50% -> 75% -> 100%)
- Allows real user traffic to test the new version with minimal risk
- Can pause at any step for manual verification or automated analysis
- Uses fewer resources since old and new versions share the replica count

### Blue-Green Strategy
- Runs both versions at full capacity simultaneously
- Switches all traffic at once from blue (old) to green (new)
- Allows instant rollback by switching back to blue
- Requires double the resources during deployment

## Progressive Delivery

Progressive delivery is the practice of deploying changes to a small subset of users, validating them, and then gradually rolling them out to more users. This scenario demonstrates:

1. **Initial Deployment**: 4 replicas running v1 (nginx:1.20-alpine)
2. **Canary Start**: 25% of replicas updated to v2 (nginx:1.21-alpine), paused for manual review
3. **Manual Promotion**: After verifying v2 is healthy, promote to continue
4. **Gradual Rollout**: 50% -> wait 30s -> 75% -> wait 30s -> 100%
5. **Stable State**: All replicas running v2

## ArgoCD + Argo Rollouts Integration

ArgoCD and Argo Rollouts complement each other:

- **ArgoCD** manages the desired state in Git and deploys the Rollout resource
- **Argo Rollouts** handles the deployment strategy (canary steps, traffic shifting)
- ArgoCD natively understands Rollout resources and displays their health correctly
- The ArgoCD UI shows canary progress, current step, and replica status
- ArgoCD's self-heal works with Rollouts - if someone manually changes the Rollout, ArgoCD reverts it

## Manual vs Automated Promotion

### Manual Promotion
- A `pause: {}` step (without duration) requires manual promotion
- Useful for human verification of canary health before proceeding
- Promote via CLI: `kubectl argo rollouts promote <name>`
- Promote via ArgoCD UI or Argo Rollouts Dashboard

### Automated Promotion
- A `pause: {duration: 30s}` step auto-promotes after the specified duration
- Can be combined with Analysis Runs for automated health verification
- Analysis Runs can query Prometheus, Datadog, or other metrics providers
- If analysis fails, the rollout automatically aborts and rolls back

## Key Takeaways

- Argo Rollouts provides deployment strategies beyond what standard Kubernetes offers
- Canary deployments reduce blast radius by testing with a small percentage of traffic first
- Manual pause steps allow human verification before proceeding with rollout
- ArgoCD and Argo Rollouts work together seamlessly for GitOps-driven progressive delivery
- In production, combine canary steps with automated analysis for fully automated safe deployments

## Files in This Scenario

- `application.yaml` - ArgoCD Application CR pointing to the Rollout manifests
- `manifests/rollout.yaml` - Argo Rollout with canary strategy and pause steps
- `manifests/service.yaml` - ClusterIP service for the canary-app
- `commands.json` - Step-by-step commands for the scenario
