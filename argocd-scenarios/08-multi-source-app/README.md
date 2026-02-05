# Scenario 08: Multi-Source Application

## Overview
Learn how ArgoCD can deploy an application that pulls manifests from multiple Git repositories or sources. This is common in real-world setups where infrastructure configs and application configs live in separate repos.

## What You'll Learn
- How to configure an ArgoCD Application with multiple sources
- Combining Helm charts with custom value overrides from a different source
- Understanding source precedence and merge behavior

## Prerequisites
- ArgoCD installed and running
- Access to the ArgoCD UI

## Architecture
This scenario deploys an nginx application using a Helm chart as the primary source, with custom values provided as a secondary source. This pattern is common when teams want to use upstream Helm charts but maintain their own value overrides in a separate repository.
