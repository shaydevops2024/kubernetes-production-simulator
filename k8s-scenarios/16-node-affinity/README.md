# Node Affinity Scenario

## Overview
Control pod placement using node affinity rules to schedule pods on specific nodes based on labels and expressions.

## What You'll Learn
- Labeling nodes
- Required vs preferred affinity rules
- Node selector vs node affinity
- Scheduling based on node properties
- Advanced scheduling techniques

## Prerequisites
- Multi-node cluster with labeled nodes
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: affinity-demo (2 replicas with node affinity)

## Scenario Flow
1. Create namespace
2. Label nodes with custom labels
3. Deploy pods with node affinity rules
4. Verify pods scheduled on correct nodes
5. Test required affinity (must match)
6. Test preferred affinity (best effort)
7. Remove node labels and observe behavior
8. Compare with nodeSelector

## Key Concepts
- **Node Affinity:** Advanced node selection rules
- **Required:** Must match (hard requirement)
- **Preferred:** Try to match (soft requirement)
- **Node Labels:** Key-value pairs on nodes
- **Operators:** In, NotIn, Exists, DoesNotExist, Gt, Lt

## Affinity Types
```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      # MUST match - pod won't schedule otherwise
      nodeSelectorTerms:
      - matchExpressions:
        - key: disktype
          operator: In
          values: ["ssd"]
    
    preferredDuringSchedulingIgnoredDuringExecution:
      # PREFERS to match - best effort
      - weight: 1
        preference:
          matchExpressions:
          - key: zone
            operator: In
            values: ["us-west-1a"]
```

## Node Affinity vs Node Selector
| Feature | nodeSelector | nodeAffinity |
|---------|--------------|--------------|
| Syntax | Simple | Complex |
| Logic | AND only | AND/OR |
| Operators | Equality only | In, NotIn, Exists, etc. |
| Required/Preferred | Required only | Both |
| Multiple Rules | No | Yes |

## Labeling Nodes
```bash
kubectl label nodes node1 disktype=ssd
kubectl label nodes node2 disktype=hdd
kubectl label nodes node1 zone=us-west-1a
```

## Expected Outcomes
- Pods schedule only on nodes matching required rules
- Preferred rules influence but don't block scheduling
- Understanding of advanced scheduling
- Knowledge of when to use affinity vs selectors

## Use Cases
- **Hardware Requirements:** GPU nodes, SSD storage
- **Geographic Placement:** Specific zones or regions
- **License Compliance:** Certain nodes for licensed software
- **Cost Optimization:** Use cheaper nodes when possible
- **Regulatory:** Data sovereignty requirements

## Operators Explained
- **In:** Label value in list
- **NotIn:** Label value not in list
- **Exists:** Label key exists (any value)
- **DoesNotExist:** Label key doesn't exist
- **Gt:** Greater than (numbers only)
- **Lt:** Less than (numbers only)

## Best Practices
- Label nodes consistently
- Use required for hard requirements only
- Combine required and preferred for flexibility
- Document node label meanings
- Monitor pod pending status

## Common Patterns
```yaml
# SSD nodes only (required)
required:
  - disktype=ssd

# Prefer zone-a, allow others (preferred)
preferred:
  - zone=us-west-1a (weight: 100)
  - zone=us-west-1b (weight: 50)
```

## Cleanup
Run the cleanup commands and remove node labels.

## Time Required
Approximately 20 minutes

## Difficulty
Medium - Requires understanding of scheduling