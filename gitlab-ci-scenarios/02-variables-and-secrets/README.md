# Scenario 02: Variables, Secrets & Environments

## Overview
Master CI/CD variable management in GitLab. Learn how to securely manage secrets, scope variables to environments, and use predefined CI variables. Proper variable management is the foundation of secure CI/CD pipelines.

## What You Will Learn
- How to define and use CI/CD variables at different levels
- The difference between protected, masked, and file variables
- Variable precedence rules (group > project > pipeline > job)
- How to scope variables to specific environments
- Predefined GitLab CI variables and their uses

## Key Concepts
- **Protected Variables**: Only available on protected branches/tags
- **Masked Variables**: Hidden in job logs (for secrets)
- **File Variables**: Written to a temp file, path set as variable value
- **Environment Scoping**: Different values per environment (staging/production)
- **Predefined Variables**: $CI_COMMIT_SHA, $CI_PIPELINE_ID, etc.

## Prerequisites
- kubectl access to the cluster
- Completed Scenario 01 (Pipeline Fundamentals)
