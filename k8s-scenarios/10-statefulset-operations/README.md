# StatefulSet Operations Scenario

## Overview
Work with StatefulSets for stateful applications requiring stable pod identities, ordered deployment, and persistent storage.

## What You'll Learn
- Creating StatefulSets
- Understanding stable network identities
- Working with persistent volume claims
- Ordered pod creation and deletion
- StatefulSet scaling behavior

## Prerequisites
- Storage provisioner configured in cluster
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Service: nginx-headless (ClusterIP: None)
- StatefulSet: nginx-sts (3 replicas)
- PersistentVolumeClaims: data-nginx-sts-0, data-nginx-sts-1, data-nginx-sts-2

## Scenario Flow
1. Create namespace and headless service
2. Deploy StatefulSet with 3 replicas
3. Observe ordered pod creation (0, 1, 2)
4. Verify stable pod names (nginx-sts-0, nginx-sts-1, nginx-sts-2)
5. Write data to pod storage
6. Delete a pod and watch recreation with same identity
7. Verify data persisted after recreation
8. Scale StatefulSet up and down
9. Observe ordered scaling behavior

## Key Concepts
- **Stable Identity:** Pods have predictable names (app-0, app-1, app-2)
- **Ordered Deployment:** Pods created sequentially
- **Headless Service:** DNS records for each pod
- **PVC per Pod:** Each pod gets its own storage
- **Stable Storage:** Data survives pod deletion

## StatefulSet vs Deployment
| Feature | StatefulSet | Deployment |
|---------|-------------|------------|
| Pod Names | Predictable (app-0) | Random (app-abc123) |
| Ordering | Sequential | Parallel |
| Storage | Persistent per pod | Shared or ephemeral |
| Network ID | Stable DNS | Load balanced |
| Use Case | Databases, queues | Stateless apps |

## DNS Records
Each pod gets a DNS record:
```
nginx-sts-0.nginx-headless.scenarios.svc.cluster.local
nginx-sts-1.nginx-headless.scenarios.svc.cluster.local
nginx-sts-2.nginx-headless.scenarios.svc.cluster.local
```

## Expected Outcomes
- Pods created in order (0, then 1, then 2)
- Each pod has stable name and hostname
- Data persists after pod deletion
- Understanding of StatefulSet guarantees

## Use Cases
- Databases (MySQL, PostgreSQL, MongoDB)
- Message queues (Kafka, RabbitMQ)
- Distributed systems (Zookeeper, etcd)
- Any app requiring stable identity or storage

## Cleanup
Run the cleanup commands including PVC deletion.

## Time Required
Approximately 25 minutes

## Difficulty
Medium - Important for stateful applications