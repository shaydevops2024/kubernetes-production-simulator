# Scenario 09: Dynamic Child Pipelines (Monorepo Strategy)

## Overview
In a monorepo with multiple services, you should only build and deploy the services that changed. Learn how to detect changes, dynamically generate child pipeline YAML, and trigger targeted builds. This pattern saves hours of CI time in large organizations.

## What You Will Learn
- How to detect which files changed in a commit
- Dynamically generating pipeline YAML in a CI job
- Using trigger: to launch child pipelines
- The parent-child pipeline relationship
- Monorepo CI strategies at scale

## Key Concepts
- **Child Pipeline**: A separate pipeline triggered by a parent pipeline job
- **Dynamic Config**: Generating .gitlab-ci.yml content at runtime
- **trigger:include:artifact**: Using job-generated YAML as pipeline config
- **rules:changes**: Running jobs only when specific files change
- **Monorepo**: Multiple services/projects in a single Git repository

## Prerequisites
- Completed Scenario 01 (Pipeline Fundamentals)
- Completed Scenario 04 (Caching & Artifacts)
