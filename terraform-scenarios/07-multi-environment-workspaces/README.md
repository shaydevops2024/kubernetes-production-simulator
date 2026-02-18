# Multi-Environment Workspaces
Learn how to manage multiple environments (dev, staging, prod) using Terraform workspaces with workspace-aware variables and conditional logic.

## Learning Objectives
- Understand the Terraform workspace concept and when to use it
- Create and switch between dev, staging, and prod workspaces
- Use terraform.workspace in resource naming for environment isolation
- Implement conditional sizing per workspace using lookup maps
- Create workspace-specific tfvars files for environment configuration
- Compare workspace-based vs directory-based environment strategies

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible

## Resources Created
- Terraform workspace configurations (dev, staging, prod)
- Workspace-aware resource naming patterns
- Lookup maps for environment-specific sizing
- Workspace-specific tfvars files
- Conditional logic blocks using terraform.workspace

## Cleanup
Run the cleanup command (last step) to remove all resources.
