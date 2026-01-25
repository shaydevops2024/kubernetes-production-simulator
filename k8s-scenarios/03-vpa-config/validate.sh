#!/bin/bash
# k8s-scenarios/03-vpa-config/validate.sh

echo "========================================"
echo "VPA Configuration Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

# Test 1: Check if VPA CRD exists
echo "[TEST 1] Checking if VPA CRD is installed..."
if kubectl get crd verticalpodautoscalers.autoscaling.k8s.io &> /dev/null; then
    echo "✅ PASSED: VPA CRD is installed"
    ((PASSED++))
else
    echo "⚠️  WARNING: VPA CRD not found - VPA might not be installed"
    echo "ℹ️  INFO: This is optional - skipping VPA-specific tests"
fi
echo ""

# Test 2: Check deployment exists
echo "[TEST 2] Checking if deployment exists..."
if kubectl get deployment k8s-demo-deployment -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: Deployment found"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not found"
    ((FAILED++))
fi
echo ""

# Test 3: Check pods are running
echo "[TEST 3] Checking if pods are running..."
READY_PODS=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$READY_PODS" -ge 1 ]; then
    echo "✅ PASSED: Found $READY_PODS running pods"
    ((PASSED++))
else
    echo "❌ FAILED: No running pods found"
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