# Pod Disruption Budget Scenario

## Overview
Protect application availability during voluntary disruptions using Pod Disruption Budgets (PDB) to ensure minimum replicas remain available.

## What You'll Learn
- Creating Pod Disruption Budgets
- Understanding voluntary vs involuntary disruptions
- Protecting against maintenance operations
- Ensuring high availability during updates
- Balancing availability with cluster operations

## Prerequisites
- Multi-replica deployments
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: pdb-demo (3 replicas)
- PodDisruptionBudget: pdb-demo (minAvailable: 2)

## Scenario Flow
1. Create namespace and deploy application with 3 replicas
2. Create PDB requiring minimum 2 pods available
3. Attempt to drain a node
4. Observe PDB prevents draining if it would violate budget
5. Scale up to allow drain
6. Test PDB protection during disruptions

## Key Concepts
- **Voluntary Disruptions:** Intentional (drain, delete, update)
- **Involuntary Disruptions:** Hardware failure, kernel panic
- **minAvailable:** Minimum pods that must remain available
- **maxUnavailable:** Maximum pods that can be unavailable
- **Eviction:** Graceful pod termination

## PDB Configuration
```yaml
spec:
  minAvailable: 2     # At least 2 pods must stay running
  selector:
    matchLabels:
      app: pdb-demo
```

## Expected Outcomes
- PDB prevents draining if it would violate availability
- Cluster operations respect application requirements
- Understanding of how PDB protects critical applications
- Knowledge of when to use minAvailable vs maxUnavailable

## Use Cases
- Protecting critical production services
- Safe cluster maintenance and upgrades
- Ensuring SLA compliance during operations
- Gradual rollouts and updates

## Best Practices
- Set PDB for all critical services
- Use minAvailable for absolute requirements
- Use maxUnavailable for flexible scenarios
- Consider with HPA for auto-scaling services
- Test PDB before production use

## Cleanup
Run the cleanup commands to remove all resources.

## Time Required
Approximately 20 minutes

## Difficulty
Medium - Requires understanding of availability concepts