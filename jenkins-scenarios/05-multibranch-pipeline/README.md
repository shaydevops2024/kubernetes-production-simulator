# Multibranch Pipeline Scenario

## Overview
Learn how Jenkins Multibranch Pipelines automatically discover branches and pull requests, executing branch-specific pipeline behavior from a single Jenkinsfile.

## What You'll Learn
- How Multibranch Pipelines auto-discover branches and PRs in a Git repository
- Using `when { branch }` directives for branch-specific stage execution
- Deploying to different environments (dev/staging/prod) based on branch name
- Validating pull requests with dedicated pipeline runs and status checks
- Environment variables available in Multibranch Pipelines (BRANCH_NAME, CHANGE_ID, CHANGE_TARGET)

## Prerequisites
- Basic understanding of Jenkins pipelines (Scenarios 01-04)
- Familiarity with Git branching strategies (GitFlow or trunk-based)
- kubectl access to the cluster

## Resources Created
- Namespace: jenkins-scenarios (created if not present)
- ConfigMap: develop-branch-info (branch deployment metadata)
- ConfigMap: staging-branch-info (branch deployment metadata)
- ConfigMap: main-branch-info (branch deployment metadata)

## Cleanup
Run the cleanup command (Step 9) to remove all ConfigMaps created during this scenario. The jenkins-scenarios namespace is preserved for use by other scenarios.
