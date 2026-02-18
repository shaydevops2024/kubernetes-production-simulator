# ConfigMap and Secrets Scenario

## Overview
Master Kubernetes configuration management by using ConfigMaps for non-sensitive data and Secrets for sensitive information like passwords.

## What You'll Learn
- Creating ConfigMaps from literals and files
- Creating Secrets for sensitive data
- Injecting configuration as environment variables
- Mounting configuration as volumes
- Updating configuration without rebuilding images

## Prerequisites
- Basic Kubernetes knowledge
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- ConfigMap: app-config (application settings)
- Secret: app-secret (database credentials)
- Deployment: configmap-demo (2 replicas using config)

## Scenario Flow
1. Create namespace
2. Create ConfigMap with application settings
3. Create Secret with database credentials
4. Deploy application that uses both
5. Verify environment variables in pods
6. View mounted configuration files
7. Update ConfigMap and observe changes

## Key Concepts
- **ConfigMaps:** Store non-sensitive configuration data
- **Secrets:** Store sensitive data (base64 encoded)
- **Environment Variables:** Inject config as env vars
- **Volume Mounts:** Mount config as files in containers
- **Immutable Config:** Best practice for production

## Expected Outcomes
- ConfigMap data available as environment variables
- Secret data securely injected into pods
- Understanding of configuration management patterns
- Knowledge of when to use ConfigMaps vs Secrets

## Best Practices
- Use Secrets for sensitive data (passwords, tokens, keys)
- Use ConfigMaps for non-sensitive configuration
- Consider marking ConfigMaps as immutable for production
- Use volume mounts for large configuration files
- Use environment variables for simple key-value pairs

## Cleanup
Run the cleanup commands to remove all resources.

## Time Required
Approximately 15 minutes

## Difficulty
Easy - Great for beginners learning Kubernetes configuration