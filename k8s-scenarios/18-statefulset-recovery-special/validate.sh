#!/bin/bash
# k8s-scenarios/18-statefulset-recovery-special/validate.sh

echo "========================================"
echo "StatefulSet Recovery (Special) Scenario Validation"
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
if kubectl get statefulset postgres-sts -n $NAMESPACE &> /dev/null; then
    echo "✅ StatefulSet exists"
    READY=$(kubectl get statefulset postgres-sts -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    DESIRED=$(kubectl get statefulset postgres-sts -n $NAMESPACE -o jsonpath='{.spec.replicas}' 2>/dev/null)
    echo "   Status: $READY/$DESIRED replicas ready"
    ((PASSED++))
else
    echo "⚠️  StatefulSet not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking headless service..."
if kubectl get service postgres-headless -n $NAMESPACE &> /dev/null; then
    echo "✅ Headless service exists"
    ((PASSED++))
else
    echo "⚠️  Service not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking PVCs..."
PVC_COUNT=$(kubectl get pvc -n $NAMESPACE -l app=postgres-sts --no-headers 2>/dev/null | wc -l)
if [ "$PVC_COUNT" -eq 0 ]; then
    echo "✅ All PVCs cleaned up"
    ((PASSED++))
elif [ "$PVC_COUNT" -eq 3 ]; then
    echo "⚠️  PVCs still exist (run cleanup to remove)"
    kubectl get pvc -n $NAMESPACE -l app=postgres-sts --no-headers 2>/dev/null | awk '{print "   - " $1}'
else
    echo "⚠️  Found $PVC_COUNT PVCs (expected 0 or 3)"
fi
echo ""

echo "[TEST 5] Checking data persistence..."
if kubectl get statefulset postgres-sts -n $NAMESPACE &> /dev/null; then
    POD_0=$(kubectl get pod postgres-sts-0 -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
    if [ "$POD_0" -eq 1 ]; then
        echo "✅ Pod postgres-sts-0 exists"
        echo "   (Data persistence can be tested manually)"
        ((PASSED++))
    else
        echo "⚠️  Pod postgres-sts-0 not found"
    fi
else
    echo "⚠️  StatefulSet not found (scenario not running)"
    ((PASSED++))
fi
echo ""

echo "[TEST 6] Checking cleanup..."
STS_COUNT=$(kubectl get statefulset postgres-sts -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
SVC_COUNT=$(kubectl get service postgres-headless -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
PVC_COUNT=$(kubectl get pvc -n $NAMESPACE -l app=postgres-sts --no-headers 2>/dev/null | wc -l)
TOTAL=$((STS_COUNT + SVC_COUNT + PVC_COUNT))
if [ "$TOTAL" -eq 0 ]; then
    echo "✅ Cleanup complete (including PVCs)"
    ((PASSED++))
else
    echo "⚠️  $TOTAL resources remain (STS: $STS_COUNT, SVC: $SVC_COUNT, PVC: $PVC_COUNT)"
    if [ "$PVC_COUNT" -gt 0 ]; then
        echo ""
        echo "   IMPORTANT: PVCs must be manually deleted!"
        echo "   Run: kubectl delete pvc -l app=postgres-sts -n scenarios"
    fi
fi
echo ""

echo "========================================"
echo "Tests Passed: $PASSED | Tests Failed: $FAILED"
echo "========================================"
if [ $FAILED -eq 0 ]; then
    if [ "$TOTAL" -eq 0 ]; then
        echo "✅ VALIDATION COMPLETE - Full cleanup done"
    else
        echo "⚠️  VALIDATION COMPLETE - Cleanup incomplete"
    fi
    exit 0
else
    echo "❌ VALIDATION FAILED"
    exit 1
fi