# Custom Values Override Scenario

## Overview
Learn how Helm values work by installing an Nginx chart with default values, then overriding them using `--set` flags and custom values files (`-f`). Understand the precedence rules that determine which values take effect.

## What You'll Learn
- How to install a Helm chart with default values
- How to override values using the `--set` flag
- How to override values using a custom values file (`-f`)
- The precedence order: defaults < values file (`-f`) < `--set` flag
- How to inspect effective values with `helm get values`

## Prerequisites
- Helm 3.x installed
- Kind cluster running with 3 nodes
- Internet access (to pull charts from Bitnami repo)

## Resources Created
- Namespace: helm-scenarios
- Helm release: my-nginx (bitnami/nginx chart)

## Values Precedence (Lowest to Highest)
1. Chart's default `values.yaml`
2. Parent chart's `values.yaml` (if subchart)
3. Values file passed with `-f` / `--values`
4. Values set with `--set`

This means `--set` always wins over `-f`, which always wins over defaults.

## Files
- `commands.json` - Step-by-step commands for the scenario
- `custom-values.yaml` - Custom values file demonstrating `-f` overrides

## Cleanup
Run the cleanup commands to remove the Helm release and all resources created in this scenario.
