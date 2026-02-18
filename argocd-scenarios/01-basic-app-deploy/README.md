# Scenario 01: Basic Application Deployment with ArgoCD

## Overview
Learn the fundamentals of ArgoCD by deploying a simple application using the GitOps approach. You will create an ArgoCD Application resource that points to Kubernetes manifests in a Git repository.

## What You Will Learn
- How ArgoCD Application custom resources work
- The relationship between source (Git) and destination (cluster)
- Manual sync workflow
- How to verify deployments through both ArgoCD UI and kubectl

## Key Concepts
- **Application CR**: The core ArgoCD resource that defines what to deploy and where
- **Source**: The Git repository and path containing your Kubernetes manifests
- **Destination**: The target cluster and namespace for deployment
- **Sync**: The process of applying Git manifests to the cluster

## Architecture
ArgoCD watches the Git repository for changes. When you sync, it applies the manifests from the specified path to the target namespace.

## Prerequisites
- ArgoCD installed and accessible at http://localhost:30800
- Git repository accessible from the cluster
