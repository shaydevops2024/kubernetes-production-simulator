#!/bin/bash
# k8s-scenarios/09-liveness-readiness/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Liveness & Readiness Probes Validation"
echo "======================================="

READY=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -o True | wc -l)
TOTAL=$(kubectl get pods -n $NAMESPACE --no-headers | wc -l)

if [ "$READY" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "✅ PASSED: All pods ready"
    ((PASSED++))
else
    echo "❌ FAILED: Not all pods ready"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
