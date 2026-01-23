#!/bin/bash
# k8s-scenarios/11-daemonset-deployment/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "DaemonSet Deployment Validation"
echo "================================"

PODS=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$PODS" -ge 1 ]; then
    echo "✅ PASSED: Pods are running"
    ((PASSED++))
else
    echo "❌ FAILED: No pods"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
