#!/bin/bash
# k8s-scenarios/15-rbac-setup/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "RBAC Setup Validation"
echo "====================="

SA=$(kubectl get serviceaccount -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$SA" -ge 1 ]; then
    echo "✅ PASSED: ServiceAccounts exist"
    ((PASSED++))
else
    echo "❌ FAILED: No ServiceAccounts"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
