# Blue-Green Deployment Scenario

## Overview
Implement blue-green deployment strategy for zero-downtime releases with instant traffic switching between versions.

## What You'll Learn
- Blue-green deployment pattern
- Running multiple versions simultaneously
- Instant traffic switching via service selectors
- Testing new version before switching
- Rollback capability

## Prerequisites
- Understanding of Kubernetes Services
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: app-blue (v1, 3 replicas)
- Deployment: app-green (v2, 3 replicas)
- Service: myapp-service (routes to blue or green)

## Scenario Flow
1. Create namespace
2. Deploy BLUE version (current production)
3. Create service pointing to BLUE
4. Verify BLUE is serving traffic
5. Deploy GREEN version (new release)
6. Test GREEN version directly
7. Switch service to GREEN (instant traffic switch)
8. Verify all traffic goes to GREEN
9. Keep BLUE running for quick rollback if needed
10. Cleanup old BLUE version

## Key Concepts
- **Blue Environment:** Current production version
- **Green Environment:** New version being deployed
- **Service Selector:** Routes traffic based on labels
- **Zero Downtime:** No service interruption during switch
- **Quick Rollback:** Revert by changing service selector

## Traffic Switching
```yaml
# Initially: Service → Blue
selector:
  app: myapp
  version: blue

# After switch: Service → Green
selector:
  app: myapp
  version: green
```

## Deployment Strategy Comparison
| Strategy | Downtime | Resource Cost | Rollback Speed |
|----------|----------|---------------|----------------|
| Blue-Green | None | High (2x resources) | Instant |
| Rolling Update | None | Low | Gradual |
| Recreate | Yes | Low | Slow |
| Canary | None | Medium | Gradual |

## Expected Outcomes
- Both versions running simultaneously
- Instant traffic switch from blue to green
- Zero downtime during deployment
- Understanding of blue-green pattern

## Advantages
- Zero downtime deployments
- Instant rollback capability
- Test new version before switching
- Clear separation of versions

## Disadvantages
- Requires 2x resources during deployment
- Database migrations can be complex
- Both versions must be compatible

## Production Considerations
- Database schema compatibility
- Shared state management
- API version compatibility
- Resource requirements

## When to Use
- Critical production services
- When instant rollback is essential
- When you can afford 2x resources
- For major version changes

## Cleanup
Run the cleanup commands to remove both deployments and service.

## Time Required
Approximately 30 minutes

## Difficulty
Hard - Requires understanding of deployment strategies