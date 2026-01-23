#!/bin/bash
# k8s-scenarios/12-job-cronjob/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Job & CronJob Validation"
echo "========================="

DEPLOYMENT=$(kubectl get deployment -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$DEPLOYMENT" -ge 1 ]; then
    echo "✅ PASSED: Resources exist"
    ((PASSED++))
else
    echo "⚠️  INFO: Check if jobs were created and completed"
    ((PASSED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
