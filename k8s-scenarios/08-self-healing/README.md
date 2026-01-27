# Self-Healing Scenario

## Overview
Demonstrate Kubernetes self-healing capabilities by deleting pods and watching automatic recreation to maintain desired state.

## What You'll Learn
- Understanding desired state reconciliation
- Pod recreation behavior
- ReplicaSet controller operation
- Self-healing capabilities
- Resilience patterns

## Prerequisites
- Basic Kubernetes knowledge
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: selfheal-demo (3 replicas)
- Service: selfheal-service

## Scenario Flow
1. Create namespace and deploy application
2. Verify 3 pods running
3. Delete one pod manually
4. Watch Kubernetes immediately create replacement
5. Delete multiple pods simultaneously
6. Observe all pods recreated
7. Verify service continues working

## Key Concepts
- **Desired State:** Declared configuration in YAML
- **Current State:** Actual running resources
- **Reconciliation Loop:** Controllers ensure current matches desired
- **ReplicaSet:** Ensures correct number of pod replicas
- **Self-Healing:** Automatic recovery from failures

## How It Works
```
Deployment (desired: 3 replicas)
    ↓
ReplicaSet (maintains 3 pods)
    ↓
Pods (actual: 2 after deletion)
    ↓
Controller detects mismatch
    ↓
Creates new pod (actual: 3 again)
```

## Expected Outcomes
- Deleted pods automatically recreated
- Desired state always maintained
- Service remains available during pod recreation
- Understanding of Kubernetes control loops

## Real-World Scenarios
- Pod crashes due to application bug
- Node failure kills all pods on node
- OOM killer terminates container
- Network partition causes pod loss
- Manual pod deletion by mistake

## Why This Matters
- Automatic recovery from failures
- No manual intervention needed
- High availability by design
- Reduced operational burden
- Built-in resilience

## Cleanup
Run the cleanup commands to remove all resources.

## Time Required
Approximately 15 minutes

## Difficulty
Easy - Perfect introduction to Kubernetes concepts