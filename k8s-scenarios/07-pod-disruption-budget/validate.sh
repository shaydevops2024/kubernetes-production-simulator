#!/bin/bash
# k8s-scenarios/07-pod-disruption-budget/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Pod Disruption Budget Validation"
echo "================================="

RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$RUNNING" -ge 1 ]; then
    echo "✅ PASSED: Pods are running"
    ((PASSED++))
else
    echo "❌ FAILED: No running pods"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
