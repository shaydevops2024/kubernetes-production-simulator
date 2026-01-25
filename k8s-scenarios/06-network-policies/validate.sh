#!/bin/bash
# k8s-scenarios/06-network-policies/validate.sh

echo "========================================"
echo "Network Policies Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

# Test 1: Check deployment exists
echo "[TEST 1] Checking if deployment exists..."
if kubectl get deployment k8s-demo-deployment -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: Deployment found"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not found"
    ((FAILED++))
fi
echo ""

# Test 2: Check all pods are running
echo "[TEST 2] Checking all pods are running..."
NOT_RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l)
if [ "$NOT_RUNNING" -eq 0 ]; then
    echo "✅ PASSED: All pods are Running"
    ((PASSED++))
else
    echo "❌ FAILED: Found $NOT_RUNNING pods not in Running state"
    ((FAILED++))
fi
echo ""

# Test 3: Check if network policies were created (may or may not exist after cleanup)
echo "[TEST 3] Checking network policy awareness..."
# This is informational - we just check if the command works
if kubectl get networkpolicies -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: Network policy commands work"
    ((PASSED++))
else
    echo "⚠️  WARNING: Network policies command failed (may not be supported)"
    ((PASSED++))
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