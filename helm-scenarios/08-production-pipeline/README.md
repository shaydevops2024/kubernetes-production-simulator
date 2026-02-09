# Scenario 08: Production Helm Pipeline

## Overview
Simulate a real production CI/CD pipeline using Helm - from linting and testing to deploying across environments with proper validation, canary releases, and automated rollback.

## Learning Objectives
- Lint and validate charts before deployment
- Run helm test to verify deployments
- Implement blue-green and canary deployment strategies with Helm
- Build a production-grade upgrade pipeline with automated rollback
- Understand Helm's release lifecycle in CI/CD

## Prerequisites
- Helm CLI installed
- kubectl configured
- Basic understanding of Helm charts and CI/CD concepts

## Resources Created
- Namespace: `helm-scenarios`
- Helm releases: `pipeline-app`, `pipeline-canary`
- Deployments, Services, ConfigMaps, test Pods

## Cleanup
Run the cleanup commands at the end of the scenario to remove all created resources.
