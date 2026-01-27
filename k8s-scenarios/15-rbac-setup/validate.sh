#!/bin/bash
# k8s-scenarios/15-rbac-setup/validate.sh

echo "========================================"
echo "RBAC Setup Scenario Validation"
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

echo "[TEST 2] Checking ServiceAccount..."
if kubectl get serviceaccount demo-sa -n $NAMESPACE &> /dev/null; then
    echo "✅ ServiceAccount exists"
    ((PASSED++))
else
    echo "⚠️  ServiceAccount not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking Role..."
if kubectl get role demo-role -n $NAMESPACE &> /dev/null; then
    echo "✅ Role exists"
    ((PASSED++))
else
    echo "⚠️  Role not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking RoleBinding..."
if kubectl get rolebinding demo-binding -n $NAMESPACE &> /dev/null; then
    echo "✅ RoleBinding exists"
    ((PASSED++))
else
    echo "⚠️  RoleBinding not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 5] Checking test deployment..."
if kubectl get deployment rbac-test-pod -n $NAMESPACE &> /dev/null; then
    echo "✅ Test pod deployment exists"
    ((PASSED++))
else
    echo "⚠️  Test deployment not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 6] Checking cleanup..."
SA_COUNT=$(kubectl get sa -n $NAMESPACE -l app=rbac-test --no-headers 2>/dev/null | wc -l)
ROLE_COUNT=$(kubectl get role,rolebinding -n $NAMESPACE --no-headers 2>/dev/null | grep demo | wc -l)
DEPLOY_COUNT=$(kubectl get deployment rbac-test-pod -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
TOTAL=$((SA_COUNT + ROLE_COUNT + DEPLOY_COUNT))
if [ "$TOTAL" -eq 0 ]; then
    echo "✅ Cleanup complete"
    ((PASSED++))
else
    echo "⚠️  $TOTAL RBAC resources remain"
fi
echo ""

echo "========================================"
echo "Tests Passed: $PASSED | Tests Failed: $FAILED"
echo "========================================"
[ $FAILED -eq 0 ] && echo "✅ VALIDATION COMPLETE" && exit 0
echo "❌ VALIDATION FAILED" && exit 1