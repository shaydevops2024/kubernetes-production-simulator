#!/bin/bash
# k8s-scenarios/02-node-failure/validate.sh

echo "========================================"
echo "Node Failure Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

echo "[TEST 1] Checking if all nodes are ready and schedulable..."
UNSCHEDULABLE_NODES=$(kubectl get nodes -o json | jq -r '.items[] | select(.spec.unschedulable==true) | .metadata.name' | wc -l)

if [ "$UNSCHEDULABLE_NODES" -eq 0 ]; then
    echo "✅ PASSED: All nodes are schedulable"
    ((PASSED++))
else
    echo "❌ FAILED: Found $UNSCHEDULABLE_NODES cordoned nodes"
    ((FAILED++))
fi
echo ""

echo "[TEST 2] Checking pod status..."
RUNNING_PODS=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
TOTAL_PODS=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | wc -l)

if [ "$RUNNING_PODS" -eq "$TOTAL_PODS" ] && [ "$TOTAL_PODS" -gt 0 ]; then
    echo "✅ PASSED: All $TOTAL_PODS pods are running"
    ((PASSED++))
else
    echo "❌ FAILED: Only $RUNNING_PODS out of $TOTAL_PODS pods are running"
    ((FAILED++))
fi
echo ""

echo "========================================"
echo "Tests Passed: $PASSED | Tests Failed: $FAILED"
echo "========================================"

if [ $FAILED -eq 0 ]; then
    echo "✅ ALL TESTS PASSED!"
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    exit 1
fi
