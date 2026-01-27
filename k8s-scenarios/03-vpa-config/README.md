# VPA Configuration Scenario

## Overview
Learn how to configure Vertical Pod Autoscaler (VPA) to automatically adjust pod resource requests based on actual usage patterns.

## What You'll Learn
- Installing and configuring VPA
- Understanding VPA recommendation modes
- Analyzing resource usage patterns
- Right-sizing pod resource requests
- Balancing between underprovisioning and overprovisioning

## Prerequisites
- VPA installed in cluster (or install during scenario)
- Metrics Server installed
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: vpa-demo-app (2 replicas)
- VPA: vpa-demo (recommendation mode)

## Scenario Flow
1. Create namespace and deploy application
2. Install VPA (if not present)
3. Create VPA resource in recommendation mode
4. Generate load to create usage patterns
5. Analyze VPA recommendations
6. Apply recommendations manually
7. Observe improved resource allocation

## Key Concepts
- **VPA Modes:** Off (recommendations only), Initial (at pod creation), Auto (recreates pods)
- **Resource Requests:** CPU and memory minimum guarantees
- **Right-Sizing:** Balancing resource allocation with actual usage
- **Recommendations:** VPA analyzes historical usage to suggest optimal resources

## Expected Outcomes
- VPA provides resource recommendations
- See the difference between initial requests and recommended values
- Understand how VPA helps optimize resource utilization
- Learn when to use VPA vs HPA

## Cleanup
Run the cleanup commands to remove all resources created in this scenario.

## Time Required
Approximately 25 minutes

## Difficulty
Medium - Requires understanding of resource management