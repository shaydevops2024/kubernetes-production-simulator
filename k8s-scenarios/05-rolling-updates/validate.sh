#!/bin/bash
# k8s-scenarios/05-rolling-updates/validate.sh

echo "========================================"
echo "Rolling Updates Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

# Test 1: Check deployment exists
echo "[TEST 1] Checking if deployment exists..."
if kubectl get deployment k8s-demo-deployment -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: Deployment found"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not found"
    ((FAILED++))
fi
echo ""

# Test 2: Check all replicas are ready
echo "[TEST 2] Checking deployment replica status..."
DESIRED=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.spec.replicas}')
READY=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')

if [ "$READY" -eq "$DESIRED" ]; then
    echo "✅ PASSED: All replicas ready ($READY/$DESIRED)"
    ((PASSED++))
else
    echo "❌ FAILED: Not all replicas ready ($READY/$DESIRED)"
    ((FAILED++))
fi
echo ""

# Test 3: Check rollout history exists
echo "[TEST 3] Checking rollout history..."
REVISIONS=$(kubectl rollout history deployment/k8s-demo-deployment -n $NAMESPACE 2>/dev/null | grep -c "REVISION")
if [ "$REVISIONS" -gt 0 ]; then
    echo "✅ PASSED: Rollout history exists ($REVISIONS revisions)"
    ((PASSED++))
else
    echo "❌ FAILED: No rollout history found"
    ((FAILED++))
fi
echo ""

# Test 4: Check pods are running
echo "[TEST 4] Checking all pods are running..."
NOT_RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l)
if [ "$NOT_RUNNING" -eq 0 ]; then
    echo "✅ PASSED: All pods are Running"
    ((PASSED++))
else
    echo "❌ FAILED: Found $NOT_RUNNING pods not in Running state"
    ((FAILED++))
fi
echo ""

# Summary
echo "========================================"
echo "VALIDATION SUMMARY"
echo "========================================"
echo "Tests Passed: $PASSED"
echo "Tests Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ ALL TESTS PASSED! Scenario completed successfully!"
    exit 0
else
    echo "❌ SOME TESTS FAILED. Please review the output above."
    exit 1
fi