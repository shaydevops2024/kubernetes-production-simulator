# Pipeline Failure Debugging

Learn to read Jenkins console logs, identify error types, and systematically debug failing pipelines.

## Learning Objectives
- Read and navigate Jenkins console output to find the root cause of failures
- Identify the five most common failure categories (dependency, test, auth, infrastructure, syntax)
- Understand exit codes and what they indicate (1, 126, 127)
- Fix a broken pipeline by addressing missing dependencies and syntax errors
- Add defensive improvements: credentials, rollout checks, and post actions

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible
- Namespace: jenkins-scenarios (created automatically)

## Resources Created
- Namespace: jenkins-scenarios
- Deployment: my-app-fixed (2 replicas, nginx:1.25-alpine)
- Service: my-app-fixed-svc (ClusterIP, port 80)

## Cleanup
Run the cleanup command (Step 9) to remove all resources created in this scenario.
