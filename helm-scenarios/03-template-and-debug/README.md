# Template and Debug Scenario

## Overview
Learn how to use Helm's templating and debugging tools to understand what a chart will deploy before actually installing it. Master `helm template`, `helm lint`, `--dry-run --debug`, and `helm get manifest` to gain full visibility into chart rendering.

## What You'll Learn
- How to create a new Helm chart from scratch with `helm create`
- How to validate a chart's structure and templates with `helm lint`
- How to render templates locally without a cluster using `helm template`
- How to simulate an install server-side with `--dry-run --debug`
- How to inspect what was actually deployed with `helm get manifest`
- The differences between local rendering (`helm template`) and server-side rendering (`--dry-run`)

## Prerequisites
- Helm 3.x installed
- Kind cluster running with 3 nodes

## Key Differences

| Tool | Cluster Required | Validates Against API | Shows Notes |
|------|-----------------|----------------------|-------------|
| `helm template` | No | No | No |
| `helm lint` | No | No | No |
| `--dry-run --debug` | Yes | Yes | Yes |
| `helm get manifest` | Yes (post-install) | N/A | No |

## Resources Created
- Namespace: helm-scenarios
- Helm chart: debug-app (created locally)
- Helm release: debug-app (installed in Step 6)

## Files
- `commands.json` - Step-by-step commands for the scenario

## Cleanup
Run the cleanup commands to remove the Helm release, chart directory, and all resources created in this scenario.
