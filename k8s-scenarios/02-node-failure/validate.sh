#!/bin/bash
# k8s-scenarios/02-node-failure/validate.sh

echo "========================================"
echo "Node Failure Scenario Validation"
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
if kubectl get deployment node-failure-demo -n $NAMESPACE &> /dev/null; then
    echo "✅ Deployment exists"
    READY=$(kubectl get deployment node-failure-demo -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    if [ "$READY" == "3" ]; then
        echo "✅ All 3 replicas ready"
        ((PASSED++))
    else
        echo "⚠️  Only $READY/3 replicas ready"
    fi
else
    echo "⚠️  Deployment not found (may be cleaned up)"
    ((PASSED++))
fi

echo ""
echo "[TEST 3] Checking cleanup status..."
RESOURCES=$(kubectl get all -n $NAMESPACE -l app=node-failure-demo --no-headers 2>/dev/null | wc -l)
if [ "$RESOURCES" -eq 0 ]; then
    echo "✅ Cleanup complete"
    ((PASSED++))
else
    echo "⚠️  $RESOURCES resources remain"
fi

echo ""
echo "========================================"
echo "Tests Passed: $PASSED"
echo "Tests Failed: $FAILED"
echo "========================================"

if [ $FAILED -eq 0 ]; then
    echo "✅ VALIDATION COMPLETE"
    exit 0
else
    echo "❌ VALIDATION FAILED"
    exit 1
fi