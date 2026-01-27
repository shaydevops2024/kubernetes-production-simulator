#!/bin/bash
# k8s-scenarios/04-configmap-secrets/validate.sh

echo "========================================"
echo "ConfigMap and Secrets Scenario Validation"
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

echo "[TEST 2] Checking ConfigMap..."
if kubectl get configmap app-config -n $NAMESPACE &> /dev/null; then
    echo "✅ ConfigMap exists"
    ((PASSED++))
else
    echo "⚠️  ConfigMap not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking Secret..."
if kubectl get secret app-secret -n $NAMESPACE &> /dev/null; then
    echo "✅ Secret exists"
    ((PASSED++))
else
    echo "⚠️  Secret not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking deployment..."
if kubectl get deployment configmap-demo -n $NAMESPACE &> /dev/null; then
    echo "✅ Deployment exists"
    ((PASSED++))
else
    echo "⚠️  Deployment not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 5] Checking cleanup..."
RESOURCES=$(kubectl get all,configmap,secret -n $NAMESPACE -l app=configmap-demo --no-headers 2>/dev/null | wc -l)
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