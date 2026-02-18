# Scenario 03: Docker Image Build & Registry Pipeline

## Overview
Build Docker images in GitLab CI, push them to a container registry, and implement production-grade image tagging strategies. Learn the difference between Docker-in-Docker and Kaniko, and why Kaniko is the production standard.

## What You Will Learn
- How to build Docker images inside CI pipelines
- Docker-in-Docker (DinD) vs Kaniko approaches
- Image tagging strategies (commit SHA, semver, latest)
- Layer caching for faster builds
- Multi-stage Docker builds for smaller images
- Container scanning integration

## Key Concepts
- **Kaniko**: Builds Docker images without Docker daemon (more secure, no privileged mode)
- **Docker-in-Docker**: Runs Docker inside Docker (requires privileged mode)
- **Image Tagging**: Using $CI_COMMIT_SHA for traceability
- **Layer Caching**: Reusing unchanged layers to speed up builds
- **GitLab Container Registry**: Built-in registry at registry.gitlab.com

## Prerequisites
- kubectl access to the cluster
- Understanding of Dockerfiles
- Completed Scenario 01 (Pipeline Fundamentals)
