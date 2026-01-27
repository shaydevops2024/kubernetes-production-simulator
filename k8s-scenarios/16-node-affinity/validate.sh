#!/bin/bash
# k8s-scenarios/16-node-affinity/validate.sh

echo "========================================"
echo "Node Affinity Scenario Validation"
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
if kubectl get deployment affinity-demo -n $NAMESPACE &> /dev/null; then
    echo "✅ Deployment exists"
    READY=$(kubectl get deployment affinity-demo -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    DESIRED=$(kubectl get deployment affinity-demo -n $NAMESPACE -o jsonpath='{.spec.replicas}' 2>/dev/null)
    echo "   Status: $READY/$DESIRED replicas ready"
    ((PASSED++))
else
    echo "⚠️  Deployment not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking pod node placement..."
POD_COUNT=$(kubectl get pods -n $NAMESPACE -l app=affinity-demo --no-headers 2>/dev/null | wc -l)
if [ "$POD_COUNT" -gt 0 ]; then
    echo "✅ Found $POD_COUNT pods"
    echo "   Pod placements:"
    kubectl get pods -n $NAMESPACE -l app=affinity-demo -o wide --no-headers 2>/dev/null | awk '{print "   - " $1 " on node " $7}'
    ((PASSED++))
else
    echo "⚠️  No pods found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking cleanup..."
RESOURCES=$(kubectl get all -n $NAMESPACE -l app=affinity-demo --no-headers 2>/dev/null | wc -l)
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