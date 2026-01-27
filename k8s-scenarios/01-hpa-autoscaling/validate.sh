#!/bin/bash
# k8s-scenarios/01-hpa-autoscaling/validate.sh

echo "========================================"
echo "HPA Autoscaling Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="scenarios"
PASSED=0
FAILED=0

# Test 1: Check namespace exists
echo "[TEST 1] Checking if scenarios namespace exists..."
if kubectl get namespace $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: Namespace 'scenarios' exists"
    ((PASSED++))
else
    echo "❌ FAILED: Namespace 'scenarios' not found"
    ((FAILED++))
fi
echo ""

# Test 2: Check deployment exists
echo "[TEST 2] Checking if deployment exists..."
if kubectl get deployment hpa-demo-app -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: Deployment 'hpa-demo-app' exists"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not found"
    ((FAILED++))
fi
echo ""

# Test 3: Check pods are running
echo "[TEST 3] Checking if pods are running..."
RUNNING=$(kubectl get pods -n $NAMESPACE -l app=hpa-demo --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$RUNNING" -ge 1 ]; then
    echo "✅ PASSED: Found $RUNNING running pods"
    ((PASSED++))
else
    echo "❌ FAILED: No running pods"
    ((FAILED++))
fi
echo ""

# Test 4: Check HPA was created
echo "[TEST 4] Checking if HPA exists..."
if kubectl get hpa hpa-demo -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: HPA 'hpa-demo' exists"
    ((PASSED++))
else
    echo "⚠️  INFO: HPA not found (may have been cleaned up)"
    ((PASSED++))
fi
echo ""

# Test 5: Check cleanup status
echo "[TEST 5] Checking cleanup status..."
RESOURCES=$(kubectl get all -n $NAMESPACE -l app=hpa-demo --no-headers 2>/dev/null | wc -l)
if [ "$RESOURCES" -eq 0 ]; then
    echo "✅ PASSED: All scenario resources cleaned up"
    ((PASSED++))
else
    echo "⚠️  WARNING: Found $RESOURCES resources still present (cleanup incomplete)"
    echo "   Run cleanup commands to remove all scenario resources"
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
    echo "✅ SCENARIO VALIDATION COMPLETE!"
    if [ "$RESOURCES" -gt 0 ]; then
        echo ""
        echo "⚠️  REMINDER: Run cleanup commands to remove scenario resources"
    fi
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    exit 1
fi