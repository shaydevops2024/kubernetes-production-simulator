# Docker Build and Push Scenario

## Overview
Learn how to build Docker images in a Jenkins pipeline, tag them with the BUILD_NUMBER for traceability, and push them to a container registry for Kubernetes deployment.

## What You'll Learn
- Writing production-quality multi-stage Dockerfiles
- Building Docker images in Jenkins pipelines with proper tagging and labels
- Comparing Docker build strategies: Docker socket mount, Docker-in-Docker, and Kaniko
- Securely authenticating to container registries using Jenkins credentials
- Deploying built images to Kubernetes with rolling updates
- Image tagging strategies for production traceability and rollbacks

## Prerequisites
- Basic understanding of Jenkins pipelines (Scenarios 01-04)
- Familiarity with Docker and Dockerfiles
- kubectl access to the cluster

## Resources Created
- Namespace: jenkins-scenarios (created if not present)
- ConfigMap: docker-build-info (image build metadata)
- ConfigMap: docker-deploy-info (deployment metadata)

## Cleanup
Run the cleanup command (Step 9) to remove all ConfigMaps created during this scenario. The jenkins-scenarios namespace is preserved for use by other scenarios.
