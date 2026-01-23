#!/bin/bash
# k8s-scenarios/16-node-affinity/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Node Affinity & Taints Validation"
echo "=================================="

NODES=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
if [ "$NODES" -ge 1 ]; then
    echo "✅ PASSED: Nodes available"
    ((PASSED++))
else
    echo "❌ FAILED: No nodes"
    ((FAILED++))
fi

RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$RUNNING" -ge 1 ]; then
    echo "✅ PASSED: Pods running"
    ((PASSED++))
else
    echo "❌ FAILED: No running pods"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
