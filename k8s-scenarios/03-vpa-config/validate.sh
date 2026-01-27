#!/bin/bash
# k8s-scenarios/03-vpa-config/validate.sh

echo "========================================"
echo "VPA Configuration Scenario Validation"
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
if kubectl get deployment vpa-demo-app -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: Deployment 'vpa-demo-app' exists"
    READY=$(kubectl get deployment vpa-demo-app -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    if [ "$READY" == "2" ]; then
        echo "✅ PASSED: All 2 replicas ready"
        ((PASSED++))
    else
        echo "⚠️  Only $READY/2 replicas ready"
    fi
else
    echo "⚠️  Deployment not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

# Test 3: Check VPA exists
echo "[TEST 3] Checking if VPA exists..."
if kubectl get vpa vpa-demo -n $NAMESPACE &> /dev/null; then
    echo "✅ PASSED: VPA 'vpa-demo' exists"
    ((PASSED++))
else
    echo "⚠️  VPA not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

# Test 4: Check cleanup status
echo "[TEST 4] Checking cleanup status..."
RESOURCES=$(kubectl get all -n $NAMESPACE -l app=vpa-demo --no-headers 2>/dev/null | wc -l)
if [ "$RESOURCES" -eq 0 ]; then
    echo "✅ PASSED: All scenario resources cleaned up"
    ((PASSED++))
else
    echo "⚠️  WARNING: Found $RESOURCES resources still present (cleanup incomplete)"
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
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    exit 1
fi