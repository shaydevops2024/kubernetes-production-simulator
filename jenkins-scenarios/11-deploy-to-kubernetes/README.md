# Deploy to Kubernetes

Full CI/CD pipeline: build, push, deploy to Kubernetes, verify health, and rollback on failure.

## Learning Objectives
- Design a complete Jenkins CI/CD pipeline for Kubernetes deployments
- Implement rolling update deployment strategies
- Add health checks and deployment verification
- Perform automatic rollback on failed deployments
- Understand production readiness patterns

## Prerequisites
- Completed Scenarios 01-07
- Understanding of Kubernetes deployments and services

## Resources Created
- Kubernetes namespace: jenkins-scenarios
- Deployments: jenkins-k8s-app (v1, v2, v3)
- Services: jenkins-k8s-app-svc
- Rolling update and rollback demonstrations

## Cleanup
Run the final cleanup command to remove all created resources.
