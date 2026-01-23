#!/bin/bash
# k8s-scenarios/05-rolling-updates/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Rolling Updates Validation"
echo "==========================="

DEPLOYMENT=$(kubectl get deployment -n $NAMESPACE -o name | head -1)
if [ ! -z "$DEPLOYMENT" ]; then
    echo "✅ PASSED: Deployment found"
    ((PASSED++))
else
    echo "❌ FAILED: No deployment"
    ((FAILED++))
fi

READY=$(kubectl get deployment -n $NAMESPACE -o jsonpath='{.items[0].status.readyReplicas}')
if [ "$READY" -ge 1 ]; then
    echo "✅ PASSED: Deployment ready"
    ((PASSED++))
else
    echo "❌ FAILED: Deployment not ready"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
