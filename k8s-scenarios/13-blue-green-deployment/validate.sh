#!/bin/bash
# k8s-scenarios/13-blue-green-deployment/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Blue-Green Deployment Validation"
echo "================================="

SERVICE=$(kubectl get service -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$SERVICE" -ge 1 ]; then
    echo "✅ PASSED: Service exists"
    ((PASSED++))
else
    echo "❌ FAILED: No service"
    ((FAILED++))
fi

RUNNING=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$RUNNING" -ge 1 ]; then
    echo "✅ PASSED: Pods running"
    ((PASSED++))
else
    echo "❌ FAILED: No running pods"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
