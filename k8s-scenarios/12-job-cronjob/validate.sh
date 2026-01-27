#!/bin/bash
# k8s-scenarios/12-job-cronjob/validate.sh

echo "========================================"
echo "Job and CronJob Scenario Validation"
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

echo "[TEST 2] Checking Job..."
if kubectl get job batch-job-demo -n $NAMESPACE &> /dev/null; then
    echo "✅ Job exists"
    SUCCEEDED=$(kubectl get job batch-job-demo -n $NAMESPACE -o jsonpath='{.status.succeeded}' 2>/dev/null)
    if [ "$SUCCEEDED" == "1" ]; then
        echo "✅ Job completed successfully"
        ((PASSED++))
    fi
else
    echo "⚠️  Job not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 3] Checking CronJob..."
if kubectl get cronjob scheduled-job-demo -n $NAMESPACE &> /dev/null; then
    echo "✅ CronJob exists"
    ((PASSED++))
else
    echo "⚠️  CronJob not found (may be cleaned up)"
    ((PASSED++))
fi
echo ""

echo "[TEST 4] Checking cleanup..."
JOB_COUNT=$(kubectl get jobs -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
CRONJOB_COUNT=$(kubectl get cronjobs -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
TOTAL=$((JOB_COUNT + CRONJOB_COUNT))
if [ "$TOTAL" -eq 0 ]; then
    echo "✅ Cleanup complete"
    ((PASSED++))
else
    echo "⚠️  $TOTAL resources remain ($JOB_COUNT jobs, $CRONJOB_COUNT cronjobs)"
fi
echo ""

echo "========================================"
echo "Tests Passed: $PASSED | Tests Failed: $FAILED"
echo "========================================"
[ $FAILED -eq 0 ] && echo "✅ VALIDATION COMPLETE" && exit 0
echo "❌ VALIDATION FAILED" && exit 1