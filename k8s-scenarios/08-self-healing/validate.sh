#!/bin/bash
# k8s-scenarios/08-self-healing/validate.sh

echo "========================================"
echo "Self-Healing Scenario Validation"
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

# Test 2: Check desired replicas match ready replicas
echo "[TEST 2] Checking self-healing restored pod count..."
DESIRED=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.spec.replicas}')
READY=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')

if [ "$READY" -eq "$DESIRED" ]; then
    echo "✅ PASSED: Self-healing maintained $READY/$DESIRED replicas"
    ((PASSED++))
else
    echo "❌ FAILED: Self-healing incomplete ($READY/$DESIRED replicas)"
    ((FAILED++))
fi
echo ""

# Test 3: Check all pods are running
echo "[TEST 3] Checking all pods are running..."
NOT_RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l)
if [ "$NOT_RUNNING" -eq 0 ]; then
    echo "✅ PASSED: All pods are Running"
    ((PASSED++))
else
    echo "❌ FAILED: Found $NOT_RUNNING pods not in Running state"
    ((FAILED++))
fi
echo ""

# Test 4: Check service endpoints are updated
echo "[TEST 4] Checking service endpoints..."
ENDPOINTS=$(kubectl get endpoints k8s-demo-service -n $NAMESPACE -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null | wc -w)
if [ "$ENDPOINTS" -ge 1 ]; then
    echo "✅ PASSED: Service has $ENDPOINTS active endpoints"
    ((PASSED++))
else
    echo "❌ FAILED: No service endpoints found"
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