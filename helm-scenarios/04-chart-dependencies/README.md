# Chart Dependencies Scenario

## Overview
Learn how to manage chart dependencies (subcharts) in Helm. Build an application chart that depends on a PostgreSQL database, use `helm dependency update` to fetch the subchart, and override subchart values from the parent chart.

## What You'll Learn
- How to declare dependencies in `Chart.yaml`
- How to use `helm dependency update` to download subcharts
- How to use `helm dependency build` and when it differs from `update`
- How the `charts/` directory stores downloaded dependencies
- How to override subchart values from the parent chart's `values.yaml`
- How to verify both the application and its database dependency are running

## Prerequisites
- Helm 3.x installed
- Kind cluster running with 3 nodes
- Internet access (to pull the PostgreSQL subchart from Bitnami)

## How Dependencies Work
```
myapp/
  Chart.yaml          <-- declares: dependencies: [{name: postgresql, ...}]
  values.yaml         <-- overrides subchart values under "postgresql:" key
  charts/             <-- helm dependency update downloads tarballs here
    postgresql-XX.tgz
  templates/          <-- your app's templates
```

The parent chart's `values.yaml` can override any subchart value by nesting it under the dependency's alias or name:
```yaml
postgresql:
  auth:
    postgresPassword: "mypassword"
```

## Resources Created
- Namespace: helm-scenarios
- Helm chart: myapp (created locally with PostgreSQL dependency)
- Helm release: myapp (application + PostgreSQL database)

## Files
- `commands.json` - Step-by-step commands for the scenario
- `Chart.yaml` - Chart metadata with PostgreSQL dependency declaration
- `values.yaml` - Values file overriding subchart defaults

## Cleanup
Run the cleanup commands to remove the Helm release, chart directory, and all resources created in this scenario.
