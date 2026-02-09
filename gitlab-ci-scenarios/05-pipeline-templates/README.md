# Scenario 05: Pipeline Templates & Includes (DRY Pipelines)

## Overview
Production teams manage dozens of repositories. Learn how to create reusable pipeline templates using includes, extends, and YAML anchors. Change one template, and all repositories get the update automatically.

## What You Will Learn
- How to use extends: for job inheritance
- The four include: methods (local, remote, project, template)
- YAML anchors and aliases for repeated configuration
- How to build a shared pipeline library
- Overriding template defaults per project

## Key Concepts
- **extends**: Inherit and override job configuration from a template
- **include:local**: Include another YAML file from the same repo
- **include:project**: Include from another GitLab project (pipeline library)
- **include:remote**: Include from any URL
- **YAML Anchors**: DRY technique for repeated YAML blocks

## Prerequisites
- Completed Scenario 01 (Pipeline Fundamentals)
