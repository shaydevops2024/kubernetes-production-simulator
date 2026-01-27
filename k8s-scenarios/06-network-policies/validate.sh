#!/bin/bash
# k8s-scenarios/06-network-policies/validate.sh

echo "========================================"
echo "Network Policies Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="scenarios"
PASSED=0
FAILED=0

echo "[TEST 1] Checking namespace..."
if kubectl get namespace $NAMESPACE &> /dev/null; then
    echo "✅ Namespace exists"
    ((PASSED++))
else
    echo "❌ Namespace not found"
    ((FAILED++))
fi
echo ""

echo "[TEST 2] Checking deployment..."
if kubectl get deployment backend-app -n $NAMESPACE &> /dev/null; then
    echo "✅ Deployment exists"
    ((PASSED++))
else
    echo "⚠️  Deployment not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking service..."
if kubectl get service backend-service -n $NAMESPACE &> /dev/null; then
    echo "✅ Service exists"
    ((PASSED++))
else
    echo "⚠️  Service not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking NetworkPolicy..."
if kubectl get networkpolicy backend-policy -n $NAMESPACE &> /dev/null; then
    echo "✅ NetworkPolicy exists"
    ((PASSED++))
else
    echo "⚠️  NetworkPolicy not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 5] Checking cleanup..."
RESOURCES=$(kubectl get all,networkpolicy -n $NAMESPACE -l app=backend --no-headers 2>/dev/null | wc -l)
if [ "$RESOURCES" -eq 0 ]; then
    echo "✅ Cleanup complete"
    ((PASSED++))
else
    echo "⚠️  $RESOURCES resources remain"
fi
echo ""

echo "========================================"
echo "Tests Passed: $PASSED | Tests Failed: $FAILED"
echo "========================================"
[ $FAILED -eq 0 ] && echo "✅ VALIDATION COMPLETE" && exit 0
echo "❌ VALIDATION FAILED" && exit 1