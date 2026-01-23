# StatefulSet Data Recovery (SPECIAL)

## Objective
This advanced **multi-scenario** simulates StatefulSet failure, verifies PVC persistence, and demonstrates data recovery - critical skills for managing stateful applications.

## What You'll Learn
- Simulate StatefulSet failures
- Verify PersistentVolume data persistence
- Recover StatefulSet with existing data
- Test data integrity after recovery
- Understand StatefulSet ordering guarantees

## Prerequisites
- Completion of StatefulSet Operations scenario
- Understanding of PersistentVolumes and PVCs
- Knowledge of stateful application requirements

## Duration
40 minutes

## Combined Concepts
1. **StatefulSet Management** - Ordered deployment and scaling
2. **Persistent Storage** - PVC lifecycle and data retention
3. **Data Recovery** - Restoring state after failures
4. **Verification** - Confirming data integrity

## Scenario Flow
### Phase 1: Setup and Baseline (10 min)
- Verify StatefulSet is running
- Write test data to persistent storage
- Confirm data is persisted
- Document baseline state

### Phase 2: Simulate Failure (15 min)
- Delete StatefulSet (keep PVCs)
- Verify PVCs remain bound
- Confirm data still exists in PVs
- Document failure state

### Phase 3: Recovery (15 min)
- Recreate StatefulSet with same config
- Watch ordered pod recreation
- Verify pods mount existing PVCs
- Confirm data was recovered
- Validate data integrity

## Success Criteria
- StatefulSet deleted without data loss
- PVCs remain bound throughout
- StatefulSet recreates successfully
- Pods mount correct PVCs by identity
- All test data recovered intact
- Ordered startup maintained

## Advanced Tips
- Use `kubectl get pvc` to verify claim persistence
- Check pod-to-PVC mapping with `kubectl describe pod`
- Verify data with `kubectl exec` before and after
- Monitor PV status throughout recovery

## Challenge Questions
1. What happens if you scale down before recovery?
2. How does StatefulSet name affect PVC matching?
3. Can you recover if you change the volumeClaimTemplate?
