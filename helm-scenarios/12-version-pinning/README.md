# Version Pinning Scenario

## Overview
Learn how to pin Helm chart versions for reproducible deployments, search for available chart versions, and manage version upgrades across environments. In production, running unversioned `helm install` commands can lead to unexpected breaking changes when chart maintainers publish new versions. This scenario teaches the discipline of explicit version pinning and controlled version upgrades.

## What You'll Learn
- How to search for all available versions of a Helm chart
- How to install a specific chart version using `--version`
- How to verify which chart version is currently deployed
- How to discover newer versions and review changelogs
- How to upgrade to a specific newer version in a controlled manner
- How to compare what changed between two chart versions
- Why version pinning is critical for production stability

## Prerequisites
- Helm 3.x installed
- Kind cluster running with 3 nodes
- Internet access (to pull charts from Bitnami repo)

## Resources Created
- Namespace: helm-scenarios
- Helm release: pinned-nginx (bitnami/nginx chart at a specific version)

## Why Version Pinning Matters
Without version pinning:
```bash
helm install my-app bitnami/nginx  # Installs latest -- could be any version!
```

With version pinning:
```bash
helm install my-app bitnami/nginx --version 15.0.0  # Always installs exactly 15.0.0
```

Version pinning ensures:
- **Reproducibility**: The same command always produces the same result
- **Predictability**: No surprise breaking changes from upstream updates
- **Auditability**: You know exactly which version is running in each environment
- **Safe upgrades**: Version bumps are explicit, reviewed, and tested

## Files
- `commands.json` - Step-by-step commands for the scenario
- `README.md` - This documentation file

## Cleanup
Run the cleanup commands to remove the Helm release and all resources created in this scenario.
