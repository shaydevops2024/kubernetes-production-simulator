# High Availability Scenario (Special)

## Overview
Build a highly available application combining Pod Disruption Budget (PDB), Horizontal Pod Autoscaler (HPA), and pod anti-affinity to ensure resilience against node failures and traffic spikes.

## What You'll Learn
- Combining multiple HA strategies
- Pod anti-affinity for distribution
- PDB for disruption protection
- HPA for automatic scaling
- Testing resilience under stress

## Prerequisites
- Multi-node cluster
- Metrics Server installed
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: ha-app (3+ replicas with anti-affinity)
- PodDisruptionBudget: ha-pdb (minAvailable: 2)
- HorizontalPodAutoscaler: ha-hpa (2-10 replicas based on CPU)

## Scenario Flow
1. Create namespace
2. Deploy application with pod anti-affinity
3. Create PDB protecting availability
4. Create HPA for auto-scaling
5. Verify pods distributed across nodes
6. Generate load to trigger scaling
7. Attempt to drain node (PDB protects)
8. Delete pods (self-healing + scaling)
9. Verify application stays available throughout

## Key Concepts
- **High Availability:** Service remains available despite failures
- **Pod Anti-Affinity:** Spread pods across different nodes
- **PDB:** Protect against voluntary disruptions
- **HPA:** Scale based on metrics
- **Multi-Layer Protection:** Defense in depth

## HA Strategy Components
```yaml
# 1. Distribution (anti-affinity)
affinity:
  podAntiAffinity:
    preferredDuringScheduling...:
      - podAffinityTerm:
          topologyKey: kubernetes.io/hostname

# 2. Disruption Protection (PDB)
spec:
  minAvailable: 2

# 3. Auto-Scaling (HPA)
spec:
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilization: 50%
```

## Multi-Phase Testing
### Phase 1: Pod Distribution
- Verify pods on different nodes
- Check anti-affinity effectiveness

### Phase 2: Load Testing
- Generate CPU load
- Watch HPA scale up
- Verify distributed scaling

### Phase 3: Disruption Testing
- Attempt node drain
- PDB blocks if would violate minAvailable
- Verify application continues

## Expected Outcomes
- Pods distributed across multiple nodes
- Application scales with load
- PDB prevents unsafe operations
- Zero downtime through all tests
- Understanding of HA architecture

## HA Principles
1. **Redundancy:** Multiple replicas
2. **Distribution:** Across failure domains
3. **Auto-Recovery:** Self-healing + scaling
4. **Protection:** PDB prevents disruption
5. **Monitoring:** Metrics-driven decisions

## Production HA Checklist
- [ ] Multiple replicas (3+ minimum)
- [ ] Pod anti-affinity configured
- [ ] PDB with appropriate minAvailable
- [ ] HPA for automatic scaling
- [ ] Health probes configured
- [ ] Resource requests/limits set
- [ ] Multi-zone deployment
- [ ] Monitoring and alerting
- [ ] Regular DR testing

## Failure Scenarios Handled
- **Node Failure:** Pods reschedule to healthy nodes
- **Pod Failure:** Self-healing recreates pods
- **Traffic Spike:** HPA scales up automatically
- **Maintenance:** PDB prevents over-disruption
- **Zone Outage:** Anti-affinity ensures distribution

## Cost vs Availability
- **3 replicas:** Basic HA, single node failure tolerance
- **5 replicas:** Better HA, two node failures
- **9+ replicas:** Very high HA, expensive

## Monitoring HA Health
```bash
# Check distribution
kubectl get pods -o wide

# Check PDB status
kubectl get pdb

# Check HPA metrics
kubectl get hpa

# Test disruption protection
kubectl drain node1 --ignore-daemonsets
```

## Cleanup
Run the cleanup commands to remove all HA resources.

## Time Required
Approximately 45 minutes (comprehensive testing)

## Difficulty
Hard - Combines multiple advanced concepts