# High Availability Multi-Scenario Test (SPECIAL)

## Objective
This is an advanced **multi-scenario** challenge that combines pod deletion, node draining, and Pod Disruption Budget (PDB) management to test high availability and resilience.

## What You'll Learn
- Combine multiple Kubernetes concepts in a single workflow
- Implement Pod Disruption Budgets for availability guarantees
- Handle simultaneous pod deletions and node failures
- Maintain service availability during planned maintenance
- Understand the interaction between PDB, HPA, and node management

## Prerequisites
- Completion of individual scenarios: HPA, Node Failure, and PDB
- Advanced kubectl knowledge
- Understanding of Kubernetes scheduling and disruption management

## Duration
45 minutes

## Combined Concepts
1. **Pod Disruption Budget (PDB)** - Ensures minimum availability
2. **Node Draining** - Simulates planned maintenance
3. **Pod Deletion** - Tests resilience and recovery
4. **HPA Integration** - Maintains desired pod count

## Scenario Flow
### Phase 1: Setup PDB and Baseline (10 min)
- Create Pod Disruption Budget
- Verify current deployment state
- Establish baseline availability

### Phase 2: Chaos Testing (20 min)
- Randomly delete pods while PDB is active
- Drain a node with PDB constraints
- Monitor PDB enforcement
- Verify no disruption beyond PDB limits

### Phase 3: Recovery and Validation (15 min)
- Restore normal operations
- Verify all pods are running
- Check PDB compliance logs
- Validate zero downtime was maintained

## Success Criteria
- PDB successfully prevents disruption beyond limits
- Service remains available throughout testing
- All pods recover successfully
- No violations of PDB constraints
- Node successfully drained respecting PDB

## Advanced Tips
- Use `kubectl get pdb -w` to monitor PDB status
- Check disruptions allowed with `kubectl describe pdb`
- Monitor events for PDB-related messages
- Verify endpoint availability during disruptions

## Challenge Questions
1. What happens when you try to drain with PDB maxUnavailable=0?
2. How does HPA interact with PDB during scaling?
3. Can you violate PDB with `--force`? (Don't do this in production!)
