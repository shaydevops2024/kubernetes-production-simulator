# Scenario 10: RBAC & Project Isolation

## Overview

This scenario demonstrates how ArgoCD uses AppProjects to enforce Role-Based Access Control (RBAC) and multi-tenancy. AppProjects are the primary security boundary in ArgoCD, controlling what applications can do and where they can deploy.

## ArgoCD RBAC Model

ArgoCD implements RBAC at multiple levels:

1. **AppProjects** - Define what an application is allowed to do (source repos, destination namespaces, resource types)
2. **RBAC Policies** - Define what users/groups can do within ArgoCD (via argocd-rbac-cm ConfigMap)
3. **SSO Integration** - Map external identity provider groups to ArgoCD roles

## AppProject as Security Boundary

An AppProject is the fundamental unit of multi-tenancy in ArgoCD. Each project defines:

- **sourceRepos**: Which Git repositories can be used as sources. Use `'*'` to allow all repos, or list specific repos for strict control.
- **destinations**: Which clusters and namespaces applications can deploy to. This prevents team A from deploying into team B's namespace.
- **clusterResourceWhitelist/Blacklist**: Which cluster-scoped resources (Namespaces, ClusterRoles, etc.) applications can create.
- **namespaceResourceWhitelist/Blacklist**: Which namespace-scoped resources (Deployments, Services, etc.) applications can create.

## Multi-Tenancy Pattern

In a multi-tenant ArgoCD setup:

1. Each team gets their own AppProject with restricted permissions
2. Projects limit deployments to team-specific namespaces
3. Projects restrict source repositories to team-owned repos
4. Projects can limit which Kubernetes resource types are allowed
5. RBAC policies control which users can manage which projects

## Namespace Isolation

This scenario demonstrates namespace isolation:

- **team-frontend** project can only deploy to `argocd-sc-10-fe`
- **team-backend** project can only deploy to `argocd-sc-10-be`
- Attempting to deploy across project boundaries results in a sync error

## What This Scenario Demonstrates

1. **Project Creation**: Creating two separate AppProjects with different permissions
2. **Successful Deployment**: Applications deploying within their allowed namespaces
3. **RBAC Enforcement**: An application failing to deploy to a namespace outside its project's allowed destinations
4. **Error Reporting**: How ArgoCD reports RBAC violations in the UI and CLI

## Key Takeaways

- Always use AppProjects (not the `default` project) in production environments
- The `default` project allows deployment to any namespace - restrict it or avoid using it
- Source repository restrictions prevent teams from deploying unauthorized code
- Resource whitelists prevent applications from creating dangerous resources (e.g., ClusterRoleBindings)
- AppProjects should be managed by platform/DevOps teams, not application teams
- Combine AppProjects with Kubernetes RBAC and NetworkPolicies for defense in depth

## Files in This Scenario

- `project-frontend.yaml` - AppProject for the frontend team
- `project-backend.yaml` - AppProject for the backend team
- `app-frontend.yaml` - Frontend Application CR (deploys to allowed namespace)
- `app-backend.yaml` - Backend Application CR (deploys to allowed namespace)
- `app-frontend-wrong-ns.yaml` - Frontend app targeting wrong namespace (will fail)
- `manifests/frontend/` - Frontend deployment and service
- `manifests/backend/` - Backend deployment and service
- `commands.json` - Step-by-step commands for the scenario
