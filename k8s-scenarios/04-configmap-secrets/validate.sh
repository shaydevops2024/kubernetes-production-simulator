#!/bin/bash
# k8s-scenarios/04-configmap-secrets/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "ConfigMap & Secrets Validation"
echo "==============================="

if kubectl get configmap -n $NAMESPACE &>/dev/null; then
    echo "✅ PASSED: ConfigMaps exist"
    ((PASSED++))
else
    echo "❌ FAILED: No ConfigMaps found"
    ((FAILED++))
fi

if kubectl get secrets -n $NAMESPACE &>/dev/null; then
    echo "✅ PASSED: Secrets exist"
    ((PASSED++))
else
    echo "❌ FAILED: No Secrets found"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
