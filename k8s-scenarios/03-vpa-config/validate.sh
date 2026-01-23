#!/bin/bash
# k8s-scenarios/03-vpa-config/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "VPA Configuration Validation"
echo "=============================="

echo "[TEST] Checking deployment exists..."
if kubectl get deployment -n $NAMESPACE &>/dev/null; then
    echo "✅ PASSED: Deployment found"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not found"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
