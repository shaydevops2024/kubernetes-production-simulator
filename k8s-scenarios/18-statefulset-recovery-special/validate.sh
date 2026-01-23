#!/bin/bash
# k8s-scenarios/18-statefulset-recovery-special/validate.sh

echo "========================================"
echo "StatefulSet Recovery Multi-Scenario Validation"
echo "========================================"
echo ""

NAMESPACE="k8s-multi-demo"
PASSED=0
FAILED=0

echo "[TEST 1] Checking StatefulSet exists..."
STS=$(kubectl get statefulset -n $NAMESPACE --no-headers 2>/dev/null | wc -l)

if [ "$STS" -ge 1 ]; then
    echo "✅ PASSED: StatefulSet found"
    ((PASSED++))
else
    echo "❌ FAILED: StatefulSet not found"
    ((FAILED++))
fi
echo ""

echo "[TEST 2] Verifying PVCs are bound..."
BOUND_PVC=$(kubectl get pvc -n $NAMESPACE -o jsonpath='{.items[?(@.status.phase=="Bound")].metadata.name}' | wc -w)
TOTAL_PVC=$(kubectl get pvc -n $NAMESPACE --no-headers | wc -l)

if [ "$BOUND_PVC" -eq "$TOTAL_PVC" ] && [ "$TOTAL_PVC" -gt 0 ]; then
    echo "✅ PASSED: All $TOTAL_PVC PVCs are bound"
    ((PASSED++))
else
    echo "❌ FAILED: Only $BOUND_PVC/$TOTAL_PVC PVCs bound"
    ((FAILED++))
fi
echo ""

echo "[TEST 3] Checking StatefulSet pod status..."
READY=$(kubectl get statefulset -n $NAMESPACE -o jsonpath='{.items[0].status.readyReplicas}' 2>/dev/null)
DESIRED=$(kubectl get statefulset -n $NAMESPACE -o jsonpath='{.items[0].spec.replicas}' 2>/dev/null)

if [ ! -z "$READY" ] && [ "$READY" -eq "$DESIRED" ]; then
    echo "✅ PASSED: StatefulSet ready ($READY/$DESIRED replicas)"
    ((PASSED++))
else
    echo "❌ FAILED: StatefulSet not fully ready"
    ((FAILED++))
fi
echo ""

echo "[TEST 4] Verifying ordered pod names..."
PODS=$(kubectl get pods -n $NAMESPACE -l app=postgres -o name 2>/dev/null | sort)

if [ ! -z "$PODS" ]; then
    echo "✅ PASSED: StatefulSet pods have stable identities"
    echo "   Pods: $(echo $PODS | tr '\n' ' ')"
    ((PASSED++))
else
    echo "❌ FAILED: No StatefulSet pods found"
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
    echo "✅ ALL TESTS PASSED! StatefulSet recovery successful!"
    echo "🎉 You've mastered StatefulSet data persistence and recovery!"
    exit 0
else
    echo "❌ SOME TESTS FAILED. Review output above."
    exit 1
fi
