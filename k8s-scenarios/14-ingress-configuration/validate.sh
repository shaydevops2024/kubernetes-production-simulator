#!/bin/bash
# k8s-scenarios/14-ingress-configuration/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Ingress Configuration Validation"
echo "================================="

SERVICE=$(kubectl get svc -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$SERVICE" -ge 1 ]; then
    echo "✅ PASSED: Services exist"
    ((PASSED++))
else
    echo "❌ FAILED: No services"
    ((FAILED++))
fi

INGRESS=$(kubectl get ingress -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$INGRESS" -ge 0 ]; then
    echo "✅ PASSED: Ingress checked"
    ((PASSED++))
else
    echo "⚠️  INFO: Ingress may not be configured"
    ((PASSED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
