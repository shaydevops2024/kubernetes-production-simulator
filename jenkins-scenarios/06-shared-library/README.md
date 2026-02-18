# Shared Library Scenario

## Overview
Learn how to create and use Jenkins Shared Libraries to build reusable pipeline steps, eliminating code duplication across multiple Jenkinsfiles.

## What You'll Learn
- The standard Shared Library directory structure (vars/, src/, resources/)
- Writing global functions in vars/ with the call() method convention
- Creating reusable Groovy classes in src/ with Serializable support
- Importing libraries using the @Library annotation with version pinning
- Building a clean, minimal Jenkinsfile that delegates to library functions

## Prerequisites
- Basic understanding of Jenkins pipelines (Scenarios 01-04)
- Familiarity with Groovy syntax basics
- kubectl access to the cluster

## Resources Created
- Namespace: jenkins-scenarios (created if not present)
- ConfigMap: shared-library-demo (library usage metadata)

## Cleanup
Run the cleanup command (Step 9) to remove all ConfigMaps created during this scenario. The jenkins-scenarios namespace is preserved for use by other scenarios.
