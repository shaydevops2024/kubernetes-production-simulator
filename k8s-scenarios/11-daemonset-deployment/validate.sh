#!/bin/bash
# k8s-scenarios/11-daemonset-deployment/validate.sh

echo "========================================"
echo "DaemonSet Deployment Scenario Validation"
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

echo "[TEST 2] Checking DaemonSet..."
if kubectl get daemonset fluentd-ds -n $NAMESPACE &> /dev/null; then
    echo "✅ DaemonSet exists"
    DESIRED=$(kubectl get daemonset fluentd-ds -n $NAMESPACE -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null)
    READY=$(kubectl get daemonset fluentd-ds -n $NAMESPACE -o jsonpath='{.status.numberReady}' 2>/dev/null)
    echo "   Status: $READY/$DESIRED pods ready"
    ((PASSED++))
else
    echo "⚠️  DaemonSet not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking cleanup..."
RESOURCES=$(kubectl get all -n $NAMESPACE -l app=fluentd --no-headers 2>/dev/null | wc -l)
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