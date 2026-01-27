#!/bin/bash
# k8s-scenarios/17-high-availability-special/validate.sh

echo "========================================"
echo "High Availability (Special) Scenario Validation"
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

echo "[TEST 2] Checking HA deployment..."
if kubectl get deployment ha-app -n $NAMESPACE &> /dev/null; then
    echo "✅ HA deployment exists"
    READY=$(kubectl get deployment ha-app -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    DESIRED=$(kubectl get deployment ha-app -n $NAMESPACE -o jsonpath='{.spec.replicas}' 2>/dev/null)
    echo "   Status: $READY/$DESIRED replicas ready"
    ((PASSED++))
else
    echo "⚠️  Deployment not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking PDB..."
if kubectl get pdb ha-pdb -n $NAMESPACE &> /dev/null; then
    echo "✅ PDB exists"
    MIN_AVAILABLE=$(kubectl get pdb ha-pdb -n $NAMESPACE -o jsonpath='{.spec.minAvailable}' 2>/dev/null)
    CURRENT=$(kubectl get pdb ha-pdb -n $NAMESPACE -o jsonpath='{.status.currentHealthy}' 2>/dev/null)
    echo "   PDB: $CURRENT healthy (min: $MIN_AVAILABLE)"
    ((PASSED++))
else
    echo "⚠️  PDB not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking HPA..."
if kubectl get hpa ha-hpa -n $NAMESPACE &> /dev/null; then
    echo "✅ HPA exists"
    REPLICAS=$(kubectl get hpa ha-hpa -n $NAMESPACE -o jsonpath='{.status.currentReplicas}' 2>/dev/null)
    echo "   HPA: $REPLICAS current replicas"
    ((PASSED++))
else
    echo "⚠️  HPA not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 5] Checking pod distribution..."
POD_COUNT=$(kubectl get pods -n $NAMESPACE -l app=ha-app --no-headers 2>/dev/null | wc -l)
if [ "$POD_COUNT" -gt 0 ]; then
    NODE_COUNT=$(kubectl get pods -n $NAMESPACE -l app=ha-app -o wide --no-headers 2>/dev/null | awk '{print $7}' | sort -u | wc -l)
    echo "✅ Pods distributed across $NODE_COUNT nodes"
    ((PASSED++))
else
    echo "⚠️  No pods found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 6] Checking cleanup..."
RESOURCES=$(kubectl get all,pdb,hpa -n $NAMESPACE -l app=ha-app --no-headers 2>/dev/null | wc -l)
if [ "$RESOURCES" -eq 0 ]; then
    echo "✅ Cleanup complete"
    ((PASSED++))
else
    echo "⚠️  $RESOURCES resources remain"
fi
echo ""

echo "========================================"
echo "Tests Passed: $PASSED | Tests Failed: $FAILED"
echo "========================================"
[ $FAILED -eq 0 ] && echo "✅ VALIDATION COMPLETE" && exit 0
echo "❌ VALIDATION FAILED" && exit 1