# Upgrade and Rollback Scenario

## Overview
Learn how to manage Helm release lifecycle by upgrading releases with new values, inspecting release history, and rolling back to a previous revision when something goes wrong.

## What You'll Learn
- How to upgrade a Helm release with new values
- How Helm tracks release revisions and history
- How to roll back to a previous revision with `helm rollback`
- How to inspect release history with `helm history`
- The difference between release revisions and their configurations

## Prerequisites
- Helm 3.x installed
- Kind cluster running with 3 nodes
- Internet access (to pull charts from Bitnami repo)

## Resources Created
- Namespace: helm-scenarios
- Helm release: my-nginx (bitnami/nginx chart)

## Release Lifecycle
```
Install (rev 1) --> Upgrade (rev 2) --> Rollback to rev 1 (creates rev 3)
```

Key concept: A rollback does not delete history. It creates a **new** revision with the configuration of the target revision. So rolling back to revision 1 creates revision 3 that is identical to revision 1.

## Files
- `commands.json` - Step-by-step commands for the scenario
- `values-v1.yaml` - Initial release values (version 1 configuration)
- `values-v2.yaml` - Updated release values (version 2 configuration with intentional changes)

## Cleanup
Run the cleanup commands to remove the Helm release and all resources created in this scenario.
