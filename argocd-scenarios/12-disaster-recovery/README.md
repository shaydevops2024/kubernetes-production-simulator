# Scenario 12: Disaster Recovery with ArgoCD

## Overview
Learn how ArgoCD enables disaster recovery by serving as the single source of truth. When a namespace or resources are accidentally deleted, ArgoCD can restore everything from Git automatically.

## What You'll Learn
- How ArgoCD acts as a disaster recovery mechanism
- Recovering from accidental namespace deletion
- Recovering from individual resource deletion
- How auto-sync enables automatic recovery
- Understanding the GitOps recovery pattern

## Prerequisites
- ArgoCD installed and running
- Access to the ArgoCD UI

## Key Concepts
- **GitOps Recovery**: Since Git is the source of truth, ArgoCD can re-create any resource
- **Self-Healing**: With auto-sync and self-heal, ArgoCD automatically restores deleted resources
- **Namespace Recovery**: Even if an entire namespace is deleted, ArgoCD re-creates it
- **Declarative State**: The desired state always exists in Git, making recovery trivial
