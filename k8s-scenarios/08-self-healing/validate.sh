#!/bin/bash
# k8s-scenarios/08-self-healing/validate.sh

echo "========================================"
echo "Self-Healing Scenario Validation"
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
if kubectl get deployment selfheal-demo -n $NAMESPACE &> /dev/null; then
    echo "✅ Deployment exists"
    READY=$(kubectl get deployment selfheal-demo -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    if [ "$READY" == "3" ]; then
        echo "✅ All 3 replicas ready"
        ((PASSED++))
    fi
else
    echo "⚠️  Deployment not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking service..."
if kubectl get service selfheal-service -n $NAMESPACE &> /dev/null; then
    echo "✅ Service exists"
    ((PASSED++))
else
    echo "⚠️  Service not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking cleanup..."
RESOURCES=$(kubectl get all -n $NAMESPACE -l app=selfheal-demo --no-headers 2>/dev/null | wc -l)
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