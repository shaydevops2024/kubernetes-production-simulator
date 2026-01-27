# StatefulSet Recovery Scenario (Special)

## Overview
Test StatefulSet data persistence and recovery capabilities by simulating pod deletions, failures, and chaos scenarios to prove data survives.

## What You'll Learn
- StatefulSet data persistence guarantees
- PVC behavior during pod deletion
- Pod identity preservation
- Recovery from failures
- Data consistency verification

## Prerequisites
- Storage provisioner configured in cluster
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Service: postgres-headless (ClusterIP: None)
- StatefulSet: postgres-sts (3 replicas - PostgreSQL database)
- PersistentVolumeClaims: data-postgres-sts-0, data-postgres-sts-1, data-postgres-sts-2

## Scenario Flow
1. Create namespace and deploy StatefulSet
2. Write test data to each pod's database
3. Verify data written successfully
4. Delete one pod and watch recreation
5. Verify data still present after recreation
6. Delete all pods simultaneously
7. Watch ordered recreation
8. Verify all data intact
9. Scale down and up
10. Confirm data persists through scaling

## Key Concepts
- **Persistent Volume Claim:** Storage request per pod
- **Stable Storage:** PVC reattaches to same pod identity
- **Data Persistence:** Data survives pod deletion
- **Ordered Recovery:** StatefulSet recreates in order
- **Identity Preservation:** Pod names stay the same

## StatefulSet Guarantees
1. **Stable Network Identity:** postgres-sts-0 always same hostname
2. **Stable Storage:** data-postgres-sts-0 always attaches to postgres-sts-0
3. **Ordered Deployment:** Pods 0, 1, 2 (wait for previous ready)
4. **Ordered Termination:** Pods 2, 1, 0 (reverse order)

## Data Persistence Test
```bash
# Write data to pod-0
kubectl exec postgres-sts-0 -n scenarios -- \
  psql -U postgres -c "CREATE TABLE test (id INT, data TEXT);"
kubectl exec postgres-sts-0 -n scenarios -- \
  psql -U postgres -c "INSERT INTO test VALUES (1, 'persistent data');"

# Delete pod-0
kubectl delete pod postgres-sts-0 -n scenarios

# Wait for recreation...

# Verify data survived
kubectl exec postgres-sts-0 -n scenarios -- \
  psql -U postgres -c "SELECT * FROM test;"
# Should show: 1 | persistent data
```

## Recovery Scenarios
### Scenario 1: Single Pod Deletion
- Delete: postgres-sts-1
- Expected: New postgres-sts-1 with same PVC
- Result: Data intact

### Scenario 2: Mass Deletion
- Delete: All 3 pods
- Expected: Recreation in order (0, 1, 2)
- Result: All data intact

### Scenario 3: Scale Down/Up
- Scale: 3 → 1 → 3
- Expected: PVCs persist, data intact
- Result: Original data in all pods

## Expected Outcomes
- Data survives pod deletion
- PVCs reattach to correct pods
- Pod identity preserved after recreation
- Understanding of StatefulSet persistence

## StatefulSet vs Deployment Storage
| Aspect | StatefulSet | Deployment |
|--------|-------------|------------|
| PVC | Per pod (unique) | Shared |
| Identity | Stable | Random |
| Storage | Persistent | Usually ephemeral |
| Recovery | Same pod → same PVC | Any pod → shared PVC |

## Why PostgreSQL?
We use PostgreSQL as example because:
- Real stateful application
- Easy to verify data persistence
- Demonstrates production pattern
- Requires stable identity

## PVC Lifecycle
```
1. StatefulSet creates → PVC created
2. Pod scheduled → PVC bound to PV
3. Pod runs → Data written
4. Pod deleted → PVC remains
5. New pod created → Same PVC reattached
6. Data preserved!
```

## Production Considerations
- **Backups:** Regular database backups essential
- **Replication:** Don't rely only on PVCs
- **Monitoring:** Track PVC usage and health
- **Storage Class:** Use replicated storage for prod
- **Disaster Recovery:** Test restore procedures

## Common Issues
- **PVC Stuck:** PVC in Terminating state
  - Fix: Remove finalizers if needed
- **No Storage:** No dynamic provisioner
  - Fix: Install storage provisioner
- **Access Denied:** PVC permissions wrong
  - Fix: Check fsGroup in pod spec

## Cleanup
**IMPORTANT:** Cleanup includes PVC deletion!
```bash
# Delete StatefulSet
kubectl delete statefulset postgres-sts -n scenarios

# Delete PVCs (data will be lost!)
kubectl delete pvc -l app=postgres-sts -n scenarios

# Delete Service
kubectl delete service postgres-headless -n scenarios
```

## Time Required
Approximately 40 minutes (comprehensive testing)

## Difficulty
Hard - Advanced StatefulSet concepts and testing