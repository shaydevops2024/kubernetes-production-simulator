#!/bin/bash
# k8s-scenarios/04-configmap-secrets/validate.sh

echo "========================================"
echo "ConfigMap/Secrets Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

# Test 1: Check deployment is running
echo "[TEST 1] Checking deployment status..."
READY=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
if [ ! -z "$READY" ] && [ "$READY" -ge 1 ]; then
    echo "✅ PASSED: Deployment has $READY ready pods"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not ready"
    ((FAILED++))
fi
echo ""

# Test 2: Check all pods are running
echo "[TEST 2] Checking pod status..."
NOT_RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l)
if [ "$NOT_RUNNING" -eq 0 ]; then
    echo "✅ PASSED: All pods are Running"
    ((PASSED++))
else
    echo "❌ FAILED: Found $NOT_RUNNING pods not in Running state"
    ((FAILED++))
fi
echo ""

# Summary
echo "========================================"
echo "VALIDATION SUMMARY"
echo "========================================"
echo "Tests Passed: $PASSED"
echo "Tests Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ ALL TESTS PASSED! Scenario completed successfully!"
    exit 0
else
    echo "❌ SOME TESTS FAILED. Please review the output above."
    exit 1
fi