# Helm Diff Plugin Scenario

## Overview
Learn how to use the `helm-diff` plugin to preview changes before deploying them to your cluster. The diff plugin compares a Helm release against a proposed upgrade, showing exactly what Kubernetes resources will change -- additions, deletions, and modifications -- before any changes are applied.

## What You'll Learn
- How to install and use the `helm-diff` plugin
- How to preview changes before running `helm upgrade`
- How to read and interpret diff output (added, removed, changed lines)
- How to verify zero drift after an upgrade completes
- Why `helm diff` is essential for safe production deployments

## Prerequisites
- Helm 3.x installed
- Kind cluster running with 3 nodes
- Internet access (to pull charts from Bitnami repo and install plugins)

## Resources Created
- Namespace: helm-scenarios
- Helm release: diff-demo (bitnami/nginx chart)

## How Helm Diff Works
The `helm-diff` plugin renders the proposed upgrade locally and compares it against the currently deployed release. It shows a colorized diff output similar to `git diff`:
- **Green (+)**: Lines that will be added
- **Red (-)**: Lines that will be removed
- **Context**: Surrounding lines for reference

This lets you catch unintended changes, verify configuration updates, and build confidence before applying upgrades.

## Files
- `commands.json` - Step-by-step commands for the scenario
- `values-v1.yaml` - Initial values for the nginx release (v1 configuration)
- `values-v2.yaml` - Updated values with changes to preview via diff (v2 configuration)

## Cleanup
Run the cleanup commands to remove the Helm release and all resources created in this scenario.
