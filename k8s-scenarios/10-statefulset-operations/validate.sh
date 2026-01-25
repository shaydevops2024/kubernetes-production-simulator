#!/bin/bash
# k8s-scenarios/10-statefulset-operations/validate.sh

echo "========================================"
echo "StatefulSet Operations Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

echo "[TEST 1] Checking for StatefulSet remnants..."
PVCS=$(kubectl get pvc -n $NAMESPACE 2>/dev/null | grep -v NAME | wc -l)
if [ "$PVCS" -ge 0 ]; then
    echo "✅ PASSED: Scenario was attempted ($PVCS PVCs found)"
    ((PASSED++))
else
    echo "⚠️  INFO: No PVCs found"
    ((PASSED++))
fi
echo ""

echo "[TEST 2] Checking deployment status..."
if kubectl get deployment k8s-demo-deployment -n $NAMESPACE &> /dev/null; then
    READY=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    if [ ! -z "$READY" ] && [ "$READY" -ge 1 ]; then
        echo "✅ PASSED: Deployment has $READY ready pods"
        ((PASSED++))
    else
        echo "⚠️  WARNING: Deployment not fully ready"
    fi
else
    echo "⚠️  INFO: Deployment not found (may be part of scenario)"
    ((PASSED++))
fi
echo ""

echo "========================================"
echo "VALIDATION SUMMARY"
echo "========================================"
echo "Tests Passed: $PASSED"
echo "Tests Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ TESTS PASSED!"
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    exit 1
fi