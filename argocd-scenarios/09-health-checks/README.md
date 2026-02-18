# Scenario 09: Resource Health & Custom Health Checks

## Overview

This scenario explores how ArgoCD assesses and tracks the health of Kubernetes resources. ArgoCD provides built-in health checks for standard Kubernetes resources and allows custom health checks for CRDs and non-standard resources.

## ArgoCD Health Assessment

ArgoCD continuously monitors the health of all resources it manages. Health status is derived from the Kubernetes resource status fields, conditions, and spec. ArgoCD understands the semantics of each resource type and translates them into a unified health model.

## Health States

ArgoCD uses four health states for resources:

- **Healthy**: The resource is operating normally. For Deployments, this means all replicas are available and up-to-date. For Services, endpoints are populated.
- **Progressing**: The resource is not yet healthy but is actively working toward a healthy state. For example, a Deployment that is rolling out new pods or a pod waiting for its init containers to complete.
- **Degraded**: The resource has failed or is in an error state. For example, a pod in CrashLoopBackOff or a Deployment with unavailable replicas due to failing readiness probes.
- **Missing**: The resource does not exist in the cluster but is defined in the desired state (Git).

## How ArgoCD Derives Health

ArgoCD uses built-in health assessment functions for standard Kubernetes resources:

- **Deployments**: Healthy when `.status.updatedReplicas == .spec.replicas` and `.status.availableReplicas == .spec.replicas` and no unavailable replicas.
- **Pods**: Healthy when all containers are ready and the pod phase is Running. Progressing during init containers or container startup.
- **Services**: Healthy when at least one endpoint exists (for ClusterIP/LoadBalancer types).
- **StatefulSets**: Similar to Deployments, based on ready replicas matching desired replicas.
- **Ingress**: Healthy when a load balancer IP or hostname is assigned.

## What This Scenario Demonstrates

1. **Init Container Delays**: The deployment uses a 30-second init container. During this time, ArgoCD shows the application as "Progressing" because pods are not yet ready.
2. **Health Probes Impact**: Both readiness and liveness probes are configured. ArgoCD reflects the probe results in its health assessment.
3. **Degraded Detection**: By breaking the readiness probe (removing the file it checks), we cause ArgoCD to detect and report "Degraded" health.
4. **Real-time Monitoring**: ArgoCD continuously re-evaluates health, so changes are reflected within seconds.

## Key Takeaways

- ArgoCD health assessment goes beyond sync status - an app can be "Synced" but "Degraded"
- Health checks are evaluated continuously, not just during sync operations
- The ArgoCD UI provides a visual resource tree showing health status of each individual resource
- Init containers and slow-starting pods are correctly identified as "Progressing" rather than "Degraded"
- Custom health checks can be defined in the ArgoCD ConfigMap for CRDs and non-standard resources using Lua scripts

## Files in This Scenario

- `application.yaml` - ArgoCD Application CR with self-heal enabled
- `manifests/deployment.yaml` - Deployment with init container and health probes
- `manifests/service.yaml` - ClusterIP service for the health-app
- `commands.json` - Step-by-step commands for the scenario
