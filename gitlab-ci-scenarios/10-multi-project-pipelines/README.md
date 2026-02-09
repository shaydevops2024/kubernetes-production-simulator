# Scenario 10: Multi-Project Pipelines & Cross-Repo Orchestration

## Overview
Microservices span multiple repositories. When the API repo deploys, it should trigger integration tests in a separate repo, then trigger the deployment orchestrator. Learn how to chain pipelines across GitLab projects with status propagation and variable passing.

## What You Will Learn
- Triggering pipelines in other GitLab projects
- Passing variables between cross-project pipelines
- Using strategy: depend for status propagation
- Building a deployment orchestrator pattern
- Managing cross-project dependencies

## Key Concepts
- **trigger:project**: Trigger a pipeline in another GitLab project
- **strategy: depend**: Parent pipeline waits for and mirrors triggered pipeline status
- **CI_JOB_TOKEN**: Automatic token for cross-project authentication
- **Downstream Variables**: Passing data to triggered pipelines
- **Pipeline Bridges**: Jobs that create downstream pipelines

## Prerequisites
- Completed Scenario 01 (Pipeline Fundamentals)
- Understanding of microservice architecture
