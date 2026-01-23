#!/bin/bash
# k8s-scenarios/01-hpa-autoscaling/validate.sh

echo "========================================"
echo "HPA Auto-Scaling Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

# Test 1: Check if HPA exists
echo "[TEST 1] Checking if HPA exists..."
if kubectl get hpa -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: HPA found"
    ((PASSED++))
else
    echo "❌ FAILED: HPA not found"
    ((FAILED++))
fi
echo ""

# Test 2: Verify HPA has scaled up at least once
echo "[TEST 2] Checking HPA scaling history..."
CURRENT_REPLICAS=$(kubectl get hpa -n $NAMESPACE -o jsonpath='{.items[0].status.currentReplicas}' 2>/dev/null)
DESIRED_REPLICAS=$(kubectl get hpa -n $NAMESPACE -o jsonpath='{.items[0].status.desiredReplicas}' 2>/dev/null)

if [ ! -z "$CURRENT_REPLICAS" ] && [ "$CURRENT_REPLICAS" -ge 2 ]; then
    echo "✅ PASSED: HPA has scaled (Current: $CURRENT_REPLICAS replicas)"
    ((PASSED++))
else
    echo "❌ FAILED: HPA has not scaled properly"
    ((FAILED++))
fi
echo ""

# Test 3: Check if deployment exists and is running
echo "[TEST 3] Checking deployment status..."
READY_REPLICAS=$(kubectl get deployment k8s-demo-deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)

if [ ! -z "$READY_REPLICAS" ] && [ "$READY_REPLICAS" -ge 1 ]; then
    echo "✅ PASSED: Deployment is running with $READY_REPLICAS ready pods"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not ready"
    ((FAILED++))
fi
echo ""

# Test 4: Verify HPA configuration
echo "[TEST 4] Verifying HPA configuration..."
TARGET_CPU=$(kubectl get hpa -n $NAMESPACE -o jsonpath='{.items[0].spec.targetCPUUtilizationPercentage}' 2>/dev/null)

if [ ! -z "$TARGET_CPU" ]; then
    echo "✅ PASSED: HPA is configured with target CPU: ${TARGET_CPU}%"
    ((PASSED++))
else
    echo "❌ FAILED: HPA target CPU not configured"
    ((FAILED++))
fi
echo ""

# Test 5: Check for no failed pods
echo "[TEST 5] Checking for pod failures..."
FAILED_PODS=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Failed --no-headers 2>/dev/null | wc -l)

if [ "$FAILED_PODS" -eq 0 ]; then
    echo "✅ PASSED: No failed pods"
    ((PASSED++))
else
    echo "❌ FAILED: Found $FAILED_PODS failed pods"
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
