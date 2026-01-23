#!/bin/bash
# k8s-scenarios/10-statefulset-operations/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "StatefulSet Operations Validation"
echo "=================================="

STS=$(kubectl get statefulset -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$STS" -ge 1 ]; then
    echo "✅ PASSED: StatefulSet found"
    ((PASSED++))
else
    echo "❌ FAILED: No StatefulSet"
    ((FAILED++))
fi

PVC=$(kubectl get pvc -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$PVC" -ge 1 ]; then
    echo "✅ PASSED: PVCs exist"
    ((PASSED++))
else
    echo "❌ FAILED: No PVCs"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
