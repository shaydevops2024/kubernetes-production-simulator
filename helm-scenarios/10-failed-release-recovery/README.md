# Failed Release Recovery Scenario

## Overview
Learn how to diagnose and recover from failed or stuck Helm releases. In production, upgrades can fail due to bad images, misconfigured resources, or timeout issues, leaving releases in a FAILED or pending-install state. This scenario teaches you how to identify the problem, use Helm history for forensics, and recover using rollback or reinstallation strategies.

## What You'll Learn
- How to recognize a failed Helm release (FAILED, pending-install, pending-upgrade states)
- How to use `helm status` and `helm history` for release forensics
- How to diagnose why an upgrade failed using pod events and logs
- How to recover using `helm rollback` to a known-good revision
- When to use `helm uninstall` and reinstall as an alternative recovery strategy
- How short `--timeout` values interact with slow-starting containers

## Prerequisites
- Helm 3.x installed
- Kind cluster running with 3 nodes
- No internet access required (uses a local chart)

## Resources Created
- Namespace: helm-scenarios
- Helm release: recovery-demo (custom chart in this directory)

## Release States Explained
| State | Meaning | Recovery |
|-------|---------|----------|
| deployed | Release is live and healthy | No action needed |
| failed | Last operation failed | Rollback or fix and re-upgrade |
| pending-install | Install is in progress or timed out | Uninstall and retry |
| pending-upgrade | Upgrade is in progress or timed out | Rollback to previous revision |
| superseded | Replaced by a newer revision | Normal state for old revisions |

## Files
- `commands.json` - Step-by-step commands for the scenario
- `Chart.yaml` - Chart metadata for the recovery-demo chart
- `values.yaml` - Default values (working configuration)
- `bad-values.yaml` - Intentionally broken values that cause deployment failure
- `templates/deployment.yaml` - Deployment template
- `templates/service.yaml` - Service template
- `templates/_helpers.tpl` - Template helper functions

## Cleanup
Run the cleanup commands to remove the Helm release and all resources created in this scenario.
