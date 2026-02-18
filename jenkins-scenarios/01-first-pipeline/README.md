# Your First Jenkins Pipeline

Build and understand a complete declarative Jenkinsfile with Build, Test, and Deploy stages.

## Learning Objectives
- Understand the structure of a declarative Jenkinsfile (pipeline, agent, stages, post)
- Learn how stages execute sequentially and fail fast on errors
- Explore step types: echo, sh, retry, timeout, and more
- Understand post actions for cleanup and notifications (always, success, failure)
- Deploy a sample application to Kubernetes to simulate a real Deploy stage

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible
- Namespace: jenkins-scenarios (created in Step 5)

## Resources Created
- Namespace: jenkins-scenarios
- Deployment: my-web-app (2 replicas, nginx:1.25-alpine)
- Service: my-web-app-svc (ClusterIP, port 80)

## Cleanup
Run the cleanup command (Step 8) to remove all resources created in this scenario.
