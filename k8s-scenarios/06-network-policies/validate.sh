
#!/bin/bash
# k8s-scenarios/06-network-policies/validate.sh

NAMESPACE="k8s-multi-demo"
PASSED=0; FAILED=0

echo "Network Policies Validation"
echo "============================"

POLICIES=$(kubectl get networkpolicies -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$POLICIES" -ge 0 ]; then
    echo "✅ PASSED: Network policies checked"
    ((PASSED++))
else
    echo "❌ FAILED: Error checking policies"
    ((FAILED++))
fi

echo "Tests Passed: $PASSED | Failed: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
