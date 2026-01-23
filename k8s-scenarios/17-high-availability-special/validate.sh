#!/bin/bash
# k8s-scenarios/17-high-availability-special/validate.sh

echo "========================================"
echo "High Availability Multi-Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

echo "[TEST 1] Checking PDB configuration..."
PDB_EXISTS=$(kubectl get pdb -n $NAMESPACE --no-headers 2>/dev/null | wc -l)

if [ "$PDB_EXISTS" -ge 1 ]; then
    PDB_MIN=$(kubectl get pdb -n $NAMESPACE -o jsonpath='{.items[0].spec.minAvailable}' 2>/dev/null)
    echo "✅ PASSED: PDB exists with minAvailable=$PDB_MIN"
    ((PASSED++))
else
    echo "❌ FAILED: PDB not found"
    ((FAILED++))
fi
echo ""

echo "[TEST 2] Checking node schedulability..."
CORDONED=$(kubectl get nodes -o json | jq -r '.items[] | select(.spec.unschedulable==true) | .metadata.name' | wc -l)

if [ "$CORDONED" -eq 0 ]; then
    echo "✅ PASSED: All nodes schedulable"
    ((PASSED++))
else
    echo "❌ FAILED: $CORDONED cordoned nodes"
    ((FAILED++))
fi
echo ""

echo "[TEST 3] Verifying pod health..."
RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers | wc -l)
TOTAL=$(kubectl get pods -n $NAMESPACE --no-headers | wc -l)

if [ "$RUNNING" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "✅ PASSED: All $TOTAL pods running"
    ((PASSED++))
else
    echo "❌ FAILED: Only $RUNNING/$TOTAL pods running"
    ((FAILED++))
fi
echo ""

echo "[TEST 4] Checking PDB disruption status..."
DISRUPTIONS=$(kubectl get pdb -n $NAMESPACE -o jsonpath='{.items[0].status.disruptionsAllowed}' 2>/dev/null)
HEALTHY=$(kubectl get pdb -n $NAMESPACE -o jsonpath='{.items[0].status.currentHealthy}' 2>/dev/null)

if [ ! -z "$DISRUPTIONS" ] && [ ! -z "$HEALTHY" ]; then
    echo "✅ PASSED: PDB status - $HEALTHY healthy, $DISRUPTIONS disruptions allowed"
    ((PASSED++))
else
    echo "❌ FAILED: Unable to verify PDB status"
    ((FAILED++))
fi
echo ""

echo "[TEST 5] Checking for failed pods..."
FAILED_PODS=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Failed --no-headers | wc -l)

if [ "$FAILED_PODS" -eq 0 ]; then
    echo "✅ PASSED: No failed pods"
    ((PASSED++))
else
    echo "❌ FAILED: $FAILED_PODS failed pods"
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
    echo "✅ ALL TESTS PASSED! Multi-scenario completed!"
    echo "🎉 You've demonstrated mastery of High Availability concepts!"
    exit 0
else
    echo "❌ SOME TESTS FAILED. Review output above."
    exit 1
fi
