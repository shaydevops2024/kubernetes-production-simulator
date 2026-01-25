#!/bin/bash
# k8s-scenarios/02-node-failure/validate.sh

echo "========================================" 
echo "Node Failure Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

# Test 1: Check all nodes are in Ready state
echo "[TEST 1] Checking if all nodes are Ready..."
NOT_READY=$(kubectl get nodes | grep -v STATUS | grep -v Ready | wc -l)
if [ "$NOT_READY" -eq 0 ]; then
    echo "✅ PASSED: All nodes are Ready"
    ((PASSED++))
else
    echo "❌ FAILED: Found $NOT_READY nodes not in Ready state"
    ((FAILED++))
fi
echo ""

# Test 2: Check that deployment has desired replicas running
echo "[TEST 2] Checking deployment replica count..."
DESIRED=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.spec.replicas}')
READY=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')

if [ "$READY" -eq "$DESIRED" ]; then
    echo "✅ PASSED: Deployment has $READY/$DESIRED replicas ready"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment has $READY/$DESIRED replicas (not all ready)"
    ((FAILED++))
fi
echo ""

# Test 3: Check no nodes are cordoned
echo "[TEST 3] Checking for cordoned nodes..."
CORDONED=$(kubectl get nodes | grep SchedulingDisabled | wc -l)
if [ "$CORDONED" -eq 0 ]; then
    echo "✅ PASSED: No nodes are cordoned"
    ((PASSED++))
else
    echo "❌ FAILED: Found $CORDONED cordoned nodes (should be 0 after uncordon)"
    ((FAILED++))
fi
echo ""

# Test 4: Check all pods are running
echo "[TEST 4] Checking all pods are running..."
NOT_RUNNING=$(kubectl get pods -n $NAMESPACE | grep -v STATUS | grep -v Running | wc -l)
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