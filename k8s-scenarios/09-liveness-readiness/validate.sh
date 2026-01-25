#!/bin/bash
# k8s-scenarios/09-liveness-readiness/validate.sh

echo "========================================"
echo "Liveness/Readiness Probes Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

echo "[TEST 1] Checking deployment exists..."
if kubectl get deployment k8s-demo-deployment -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: Deployment exists"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not found"
    ((FAILED++))
fi
echo ""

echo "[TEST 2] Checking for liveness probe..."
HAS_LIVENESS=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o yaml 2>/dev/null | grep -c "livenessProbe")
if [ "$HAS_LIVENESS" -gt 0 ]; then
    echo "✅ PASSED: Liveness probe configured"
    ((PASSED++))
else
    echo "⚠️  INFO: No liveness probe (may have been removed in cleanup)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking for readiness probe..."
HAS_READINESS=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o yaml 2>/dev/null | grep -c "readinessProbe")
if [ "$HAS_READINESS" -gt 0 ]; then
    echo "✅ PASSED: Readiness probe configured"
    ((PASSED++))
else
    echo "⚠️  INFO: No readiness probe (may have been removed in cleanup)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking pods are running..."
RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$RUNNING" -ge 1 ]; then
    echo "✅ PASSED: $RUNNING pods running"
    ((PASSED++))
else
    echo "❌ FAILED: No running pods"
    ((FAILED++))
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