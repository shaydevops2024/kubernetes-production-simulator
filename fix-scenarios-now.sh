#!/bin/bash
# fix-scenarios-now.sh
# WORKING FIX - Creates directory first, then copies

NAMESPACE="k8s-multi-demo"

echo "=========================================="
echo "FIXING SCENARIOS - The Right Way"
echo "=========================================="
echo ""

# Check we're in the right directory
if [ ! -d "k8s-scenarios" ]; then
    echo "❌ ERROR: k8s-scenarios directory not found"
    echo "Current directory: $(pwd)"
    exit 1
fi

# Get pod names
POD_NAMES=($(kubectl get pods -n ${NAMESPACE} -l app=k8s-demo-app -o jsonpath='{.items[*].metadata.name}' 2>/dev/null))
POD_COUNT=${#POD_NAMES[@]}

if [ ${POD_COUNT} -eq 0 ]; then
    echo "❌ ERROR: No application pods found"
    exit 1
fi

echo "Found ${POD_COUNT} pod(s)"
echo ""

# Process each pod
for i in "${!POD_NAMES[@]}"; do
    POD_NAME="${POD_NAMES[$i]}"
    POD_NUM=$((i + 1))
    
    echo "=========================================="
    echo "Pod ${POD_NUM}/${POD_COUNT}: ${POD_NAME}"
    echo "=========================================="
    
    # STEP 1: Create /scenarios directory in pod
    echo "[1/4] Creating /scenarios directory..."
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- mkdir -p /scenarios 2>/dev/null
    
    if kubectl exec -n ${NAMESPACE} ${POD_NAME} -- test -d /scenarios 2>/dev/null; then
        echo "   ✅ Directory created"
    else
        echo "   ❌ Failed to create directory"
        continue
    fi
    
    # STEP 2: Copy each scenario directory individually
    echo "[2/4] Copying scenario directories..."
    
    SUCCESS_COUNT=0
    FAIL_COUNT=0
    
    for SCENARIO_DIR in k8s-scenarios/*/; do
        SCENARIO_NAME=$(basename "$SCENARIO_DIR")
        
        # Copy this scenario
        if kubectl cp "${SCENARIO_DIR}" "${NAMESPACE}/${POD_NAME}:/scenarios/${SCENARIO_NAME}" 2>&1 | grep -v "Defaulted" | grep -v "tar:" >/dev/null; then
            # Copy failed
            FAIL_COUNT=$((FAIL_COUNT + 1))
        else
            # Copy succeeded or harmless warnings
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        fi
    done
    
    echo "   ✅ Copied ${SUCCESS_COUNT} scenarios (${FAIL_COUNT} failed)"
    
    # STEP 3: Make validate scripts executable
    echo "[3/4] Making validate scripts executable..."
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- sh -c 'chmod +x /scenarios/*/validate.sh 2>/dev/null' || true
    echo "   ✅ Permissions set"
    
    # STEP 4: Verify
    echo "[4/4] Verifying..."
    FINAL_COUNT=$(kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ls /scenarios 2>/dev/null | wc -l)
    
    if [ "${FINAL_COUNT}" -eq 18 ]; then
        echo "   ✅ SUCCESS! ${FINAL_COUNT} scenarios present"
    else
        echo "   ⚠️  ${FINAL_COUNT} scenarios (expected 18)"
    fi
    
    echo ""
done

# Final verification
echo "=========================================="
echo "FINAL VERIFICATION"
echo "=========================================="
echo ""

# Test API
sleep 2
NODEPORT=$(kubectl get svc k8s-demo-nodeport -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].nodePort}')

echo "Testing API endpoint..."
API_COUNT=$(curl -s http://localhost:${NODEPORT}/api/scenarios 2>/dev/null | grep -o '"id":' | wc -l)

if [ "${API_COUNT}" -eq 18 ]; then
    echo -e "\n✅ SUCCESS! API returning ${API_COUNT} scenarios"
    echo ""
    echo "==========================================="
    echo "🎉 ALL FIXED! Open your browser:"
    echo "   http://localhost:${NODEPORT}/static/scenarios.html"
    echo "==========================================="
else
    echo -e "\n⚠️  API returning ${API_COUNT} scenarios"
    echo ""
    echo "The scenarios are in the pods, but backend may need restart:"
    echo "  kubectl rollout restart deployment/k8s-demo-deployment -n ${NAMESPACE}"
fi

echo ""
