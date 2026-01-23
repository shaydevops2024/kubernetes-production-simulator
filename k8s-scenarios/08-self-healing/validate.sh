#!/bin/bash
# k8s-scenarios/08-self-healing/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Self-Healing Validation"
echo "======================="

RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers | wc -l)
TOTAL=$(kubectl get pods -n $NAMESPACE --no-headers | wc -l)

if [ "$RUNNING" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "✅ PASSED: All pods running"
    ((PASSED++))
else
    echo "❌ FAILED: Not all pods recovered"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
