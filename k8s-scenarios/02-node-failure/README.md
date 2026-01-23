# Node Failure Simulation

## Objective
Simulate and recover from node failures, understanding how Kubernetes handles pod rescheduling and maintains application availability.

## What You'll Learn
- Simulate node failures using cordon and drain
- Observe automatic pod rescheduling
- Understand node taints and tolerations
- Monitor cluster recovery behavior
- Verify application availability during node failures

## Prerequisites
- Understanding of Kubernetes nodes and pods
- Knowledge of kubectl commands
- Familiarity with pod scheduling

## Duration
20 minutes

## Steps Overview
1. Check current node status
2. Identify target node for failure simulation
3. Cordon the node to prevent new pods
4. Drain the node to migrate existing pods
5. Observe pod rescheduling
6. Uncordon node to restore it
7. Verify cluster is back to normal

## Success Criteria
- Node successfully cordoned and drained
- All pods rescheduled to other nodes
- No application downtime
- Node successfully restored

## Tips
- Use `kubectl get nodes` to monitor node status
- Watch pod migration with `kubectl get pods -o wide -w`
- Check events with `kubectl get events --sort-by='.lastTimestamp'`
