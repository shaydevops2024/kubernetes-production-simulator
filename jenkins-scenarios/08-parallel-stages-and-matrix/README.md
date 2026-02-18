# Parallel Stages and Matrix Scenario

## Overview
Learn how to run Jenkins pipeline stages in parallel and use the matrix directive to test across multiple environments, dramatically reducing pipeline execution time.

## What You'll Learn
- Parallel stage syntax for running independent stages concurrently
- The matrix directive for automatic cross-platform and multi-version testing
- Timing benefits of parallel vs sequential execution with visual comparisons
- The failFast option for early failure detection and resource savings
- When to use parallel stages and when to avoid them
- Resource planning considerations for parallel execution

## Prerequisites
- Basic understanding of Jenkins pipelines (Scenarios 01-04)
- Familiarity with testing concepts (unit, integration, e2e)
- kubectl access to the cluster

## Resources Created
- Namespace: jenkins-scenarios (created if not present)
- ConfigMap: parallel-test-results (test execution results)
- ConfigMap: parallel-deploy-info (deployment and timing metrics)

## Cleanup
Run the cleanup command (Step 9) to remove all ConfigMaps created during this scenario. The jenkins-scenarios namespace is preserved for use by other scenarios.
