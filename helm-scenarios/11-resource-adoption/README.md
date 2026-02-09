# Resource Adoption Scenario

## Overview
Learn how to import existing Kubernetes resources into Helm management without deleting and recreating them. This is a common production challenge: you have resources deployed manually with `kubectl apply` and want to bring them under Helm's lifecycle management. The key technique uses Helm's ownership annotations and labels to "adopt" resources that already exist in the cluster.

## What You'll Learn
- How Helm tracks ownership of resources (annotations and labels)
- How to annotate existing resources so Helm recognizes them as managed
- How to create a Helm chart that matches existing resource specs exactly
- How to use `helm install` to adopt pre-existing resources
- How to verify Helm successfully manages adopted resources
- How to upgrade adopted resources through Helm to prove full management

## Prerequisites
- Helm 3.x installed
- Kind cluster running with 3 nodes
- No internet access required (uses local manifests and chart)

## Resources Created
- Namespace: helm-scenarios
- Deployment: adopted-app (initially via kubectl, then Helm-managed)
- Service: adopted-app (initially via kubectl, then Helm-managed)

## How Resource Adoption Works
1. **Deploy manually** with `kubectl apply` -- resources exist but are not Helm-managed
2. **Create a Helm chart** whose templates produce identical resource specs
3. **Annotate existing resources** with Helm's ownership metadata:
   - `meta.helm.sh/release-name: <release-name>`
   - `meta.helm.sh/release-namespace: <namespace>`
   - Label: `app.kubernetes.io/managed-by: Helm`
4. **Run `helm install`** -- Helm sees the annotations and adopts the resources instead of failing with "already exists"

## Files
- `commands.json` - Step-by-step commands for the scenario
- `existing-deployment.yaml` - Standalone deployment manifest (deployed via kubectl)
- `existing-service.yaml` - Standalone service manifest (deployed via kubectl)
- `Chart.yaml` - Chart metadata for the adoption chart
- `values.yaml` - Chart values matching the existing resource configuration
- `templates/deployment.yaml` - Helm template matching existing-deployment.yaml
- `templates/service.yaml` - Helm template matching existing-service.yaml
- `templates/_helpers.tpl` - Template helper functions

## Cleanup
Run the cleanup commands to remove the Helm release and all resources created in this scenario.
