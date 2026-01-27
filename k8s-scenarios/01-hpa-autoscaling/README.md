# HPA Autoscaling Scenario

## Overview
Learn Horizontal Pod Autoscaling (HPA) by watching Kubernetes automatically scale pods based on CPU usage.

## What You'll Learn
- How HPA monitors CPU metrics
- Scale-up behavior under load
- Scale-down behavior when load decreases
- Setting min/max replica bounds

## Prerequisites
- Metrics Server installed in cluster
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: hpa-demo-app (2-10 replicas)
- Service: hpa-demo-service
- HPA: hpa-demo (target: 50% CPU)

## Cleanup
Run the cleanup commands to remove all resources created in this scenario.