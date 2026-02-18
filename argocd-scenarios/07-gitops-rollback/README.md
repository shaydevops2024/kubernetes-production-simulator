# Scenario 07: GitOps Rollback

## Overview
Learn how to perform rollbacks the GitOps way using ArgoCD. When a bad deployment goes out, you need to quickly revert to a known-good state. ArgoCD provides multiple rollback strategies.

## What You'll Learn
- How ArgoCD tracks application revision history
- Rolling back to a previous sync revision
- The difference between Git revert vs ArgoCD rollback
- How auto-sync interacts with rollback

## Prerequisites
- ArgoCD installed and running
- Access to the ArgoCD UI

## Key Concepts
- **Revision History**: ArgoCD keeps a history of synced revisions
- **Rollback**: Revert to a previously synced state
- **Git Revert**: The GitOps-preferred way to undo changes (revert commit in Git)
- **Auto-Sync Conflict**: If auto-sync is enabled, ArgoCD will re-sync to HEAD after rollback
