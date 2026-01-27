# DaemonSet Deployment Scenario

## Overview
Deploy system daemons using DaemonSets to ensure exactly one pod runs on every node for logging, monitoring, or node-level operations.

## What You'll Learn
- Creating DaemonSets
- Understanding node-level pod scheduling
- Tolerations for control-plane nodes
- DaemonSet update strategies
- Use cases for system daemons

## Prerequisites
- Multi-node cluster (to see effect on multiple nodes)
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- DaemonSet: fluentd-ds (log collection agent)

## Scenario Flow
1. Create namespace
2. Deploy DaemonSet (Fluentd example)
3. Verify one pod per node
4. Add a new node (if possible)
5. Watch pod automatically scheduled on new node
6. View pod distribution across nodes
7. Update DaemonSet image
8. Observe rolling update across all nodes

## Key Concepts
- **DaemonSet:** Ensures pod runs on all (or selected) nodes
- **Node Affinity:** Control which nodes get pods
- **Tolerations:** Run on tainted nodes (like control-plane)
- **Host Networking:** Access node-level resources
- **Update Strategy:** OnDelete or RollingUpdate

## DaemonSet vs Deployment
| Feature | DaemonSet | Deployment |
|---------|-----------|------------|
| Replicas | One per node | User-specified count |
| Scheduling | Node-level | Cluster-level |
| Scaling | Automatic (with nodes) | Manual or HPA |
| Use Case | System daemons | Applications |

## Common Use Cases
- **Logging:** Fluentd, Filebeat (collect logs from all nodes)
- **Monitoring:** Node Exporter, cAdvisor (metrics from nodes)
- **Networking:** CNI plugins, kube-proxy
- **Storage:** CSI drivers, storage daemons
- **Security:** Security scanning, policy enforcement

## Expected Outcomes
- Exactly one pod per node
- Pods automatically scheduled on new nodes
- Understanding of node-level scheduling
- Knowledge of when to use DaemonSets

## Host Access
DaemonSets often need access to host resources:
```yaml
volumes:
- name: varlog
  hostPath:
    path: /var/log     # Access node's /var/log
```

## Cleanup
Run the cleanup commands to remove the DaemonSet.

## Time Required
Approximately 15 minutes

## Difficulty
Easy - Straightforward concept