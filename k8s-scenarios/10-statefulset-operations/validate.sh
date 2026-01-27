#!/bin/bash
# k8s-scenarios/10-statefulset-operations/validate.sh

echo "========================================"
echo "StatefulSet Operations Scenario Validation"
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

echo "[TEST 2] Checking StatefulSet..."
if kubectl get statefulset nginx-sts -n $NAMESPACE &> /dev/null; then
    echo "✅ StatefulSet exists"
    READY=$(kubectl get statefulset nginx-sts -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    if [ "$READY" == "3" ]; then
        echo "✅ All 3 replicas ready"
        ((PASSED++))
    fi
else
    echo "⚠️  StatefulSet not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking headless service..."
if kubectl get service nginx-headless -n $NAMESPACE &> /dev/null; then
    echo "✅ Headless service exists"
    ((PASSED++))
else
    echo "⚠️  Service not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking PVCs..."
PVC_COUNT=$(kubectl get pvc -n $NAMESPACE -l app=nginx-sts --no-headers 2>/dev/null | wc -l)
if [ "$PVC_COUNT" -eq 0 ]; then
    echo "✅ All PVCs cleaned up"
    ((PASSED++))
elif [ "$PVC_COUNT" -eq 3 ]; then
    echo "⚠️  PVCs still exist (run cleanup to remove)"
else
    echo "⚠️  Found $PVC_COUNT PVCs"
fi
echo ""

echo "[TEST 5] Checking cleanup..."
RESOURCES=$(kubectl get all -n $NAMESPACE -l app=nginx-sts --no-headers 2>/dev/null | wc -l)
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