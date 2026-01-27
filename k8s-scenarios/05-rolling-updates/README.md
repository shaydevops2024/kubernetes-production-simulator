# Rolling Updates Scenario

## Overview
Perform zero-downtime rolling updates by gradually replacing old pods with new versions while maintaining application availability.

## What You'll Learn
- Performing rolling updates
- Controlling rollout speed with maxSurge and maxUnavailable
- Monitoring update progress
- Rolling back failed updates
- Ensuring zero downtime during updates

## Prerequisites
- Basic Kubernetes knowledge
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: rolling-demo (3 replicas)
- Service: rolling-service (ClusterIP)

## Scenario Flow
1. Create namespace and deploy v1 application
2. Verify all pods are running
3. Update deployment to v2 (new image version)
4. Watch rolling update in progress
5. Verify pods replaced gradually
6. Check rollout history
7. Perform rollback to v1
8. Verify rollback success

## Key Concepts
- **Rolling Update:** Default deployment strategy
- **maxSurge:** Maximum extra pods during update
- **maxUnavailable:** Maximum pods that can be unavailable
- **Rollback:** Revert to previous revision
- **Revision History:** Track deployment changes

## Rolling Update Strategy
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1        # Can create 1 extra pod
    maxUnavailable: 1  # At most 1 pod down
```

## Expected Outcomes
- Application remains available during entire update
- Pods replaced gradually (not all at once)
- Ability to rollback if issues occur
- Understanding of deployment strategies

## Common Use Cases
- Deploying new application versions
- Updating container images
- Changing environment variables
- Scaling deployment configurations

## Cleanup
Run the cleanup commands to remove all resources.

## Time Required
Approximately 20 minutes

## Difficulty
Medium - Requires understanding of deployment strategies