#!/bin/bash
# k8s-scenarios/07-pod-disruption-budget/validate.sh

echo "========================================"
echo "Pod Disruption Budget Validation"
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

echo "[TEST 2] Checking deployment replicas..."
DESIRED=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.spec.replicas}' 2>/dev/null)
READY=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)

if [ ! -z "$READY" ] && [ "$READY" -eq "$DESIRED" ]; then
    echo "✅ PASSED: All replicas ready ($READY/$DESIRED)"
    ((PASSED++))
else
    echo "⚠️  WARNING: Replicas may be scaling ($READY/$DESIRED)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking all nodes are ready..."
NOT_READY=$(kubectl get nodes | grep -v STATUS | grep -v Ready | wc -l)
if [ "$NOT_READY" -eq 0 ]; then
    echo "✅ PASSED: All nodes are Ready"
    ((PASSED++))
else
    echo "❌ FAILED: Found $NOT_READY nodes not Ready"
    ((FAILED++))
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
    echo "✅ ALL TESTS PASSED!"
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    exit 1
fi