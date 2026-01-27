#!/bin/bash

echo "==================================="
echo "SCENARIOS PAGE DEBUG"
echo "==================================="

# Get pod name
POD_NAME=$(kubectl get pods -n k8s-multi-demo -l app=k8s-demo-app -o jsonpath='{.items[0].metadata.name}')
echo "Pod Name: $POD_NAME"

# Check pod status
echo -e "\n[1] Pod Status:"
kubectl get pods -n k8s-multi-demo -l app=k8s-demo-app

# Check if scenarios exist in pod
echo -e "\n[2] Scenarios in Pod:"
kubectl exec -n k8s-multi-demo $POD_NAME -- ls /scenarios/ 2>/dev/null
SCENARIO_COUNT=$(kubectl exec -n k8s-multi-demo $POD_NAME -- ls /scenarios/ 2>/dev/null | wc -l)
echo "Found $SCENARIO_COUNT scenarios"

# Check API endpoint
echo -e "\n[3] Testing API Endpoint:"
NODEPORT=$(kubectl get svc k8s-demo-nodeport -n k8s-multi-demo -o jsonpath='{.spec.ports[0].nodePort}')
curl -s http://localhost:$NODEPORT/api/scenarios | head -50

# Check recent logs
echo -e "\n[4] Recent Logs:"
kubectl logs -n k8s-multi-demo $POD_NAME --tail=20

echo -e "\n==================================="
echo "Access URL: http://localhost:$NODEPORT"
echo "==================================="


echo "####################################################################"

#!/bin/bash
# debug-scenarios.sh
# Comprehensive debugging for scenarios issue

NAMESPACE="k8s-multi-demo"
NODEPORT=30080

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=========================================="
echo "SCENARIOS DEBUGGING TOOL"
echo "=========================================="
echo ""

# ============================================
# TEST 1: Check if k8s-scenarios directory exists locally
# ============================================
echo -e "${CYAN}[TEST 1] Checking local k8s-scenarios directory...${NC}"
if [ -d "k8s-scenarios" ]; then
    SCENARIO_DIRS=$(ls -1 k8s-scenarios | wc -l)
    echo -e "${GREEN}✅ k8s-scenarios directory exists${NC}"
    echo "   Found $SCENARIO_DIRS directories"

    echo ""
    echo "Contents:"
    ls -1 k8s-scenarios/

    # Check if README.md exists in first scenario
    if [ -f "k8s-scenarios/01-hpa-autoscaling/README.md" ]; then
        echo -e "${GREEN}✅ Scenario files exist (verified README.md)${NC}"
    else
        echo -e "${RED}❌ Scenario files missing!${NC}"
    fi
else
    echo -e "${RED}❌ k8s-scenarios directory NOT FOUND in current directory!${NC}"
    echo ""
    echo "Current directory: $(pwd)"
    echo ""
    echo "SOLUTION: You must run this script from project root where k8s-scenarios/ exists"
    exit 1
fi

echo ""

# ============================================
# TEST 2: Check pods are running
# ============================================
echo -e "${CYAN}[TEST 2] Checking application pods...${NC}"
POD_NAMES=($(kubectl get pods -n ${NAMESPACE} -l app=k8s-demo-app -o jsonpath='{.items[*].metadata.name}' 2>/dev/null))
POD_COUNT=${#POD_NAMES[@]}

if [ ${POD_COUNT} -eq 0 ]; then
    echo -e "${RED}❌ No application pods found!${NC}"
    echo ""
    echo "Checking all pods in namespace:"
    kubectl get pods -n ${NAMESPACE}
    echo ""
    echo "SOLUTION: Run ./kind_setup.sh to deploy the application"
    exit 1
else
    echo -e "${GREEN}✅ Found ${POD_COUNT} pod(s)${NC}"
    for POD in "${POD_NAMES[@]}"; do
        POD_STATUS=$(kubectl get pod ${POD} -n ${NAMESPACE} -o jsonpath='{.status.phase}')
        echo "   - ${POD}: ${POD_STATUS}"
    done
fi

echo ""

# ============================================
# TEST 3: Check scenarios in EACH pod
# ============================================
echo -e "${CYAN}[TEST 3] Checking scenarios in each pod...${NC}"

for i in "${!POD_NAMES[@]}"; do
    POD_NAME="${POD_NAMES[$i]}"
    POD_NUM=$((i + 1))

    echo ""
    echo "Pod ${POD_NUM}/${POD_COUNT}: ${POD_NAME}"
    echo "---"

    # Check if /scenarios directory exists
    if kubectl exec -n ${NAMESPACE} ${POD_NAME} -- test -d /scenarios 2>/dev/null; then
        echo -e "${GREEN}✅ /scenarios directory exists${NC}"

        # Count scenarios
        SCENARIO_COUNT=$(kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ls /scenarios 2>/dev/null | wc -l)
        echo "   Scenarios found: ${SCENARIO_COUNT}"

        if [ "${SCENARIO_COUNT}" -eq 18 ]; then
            echo -e "${GREEN}✅ All 18 scenarios present${NC}"
        else
            echo -e "${RED}❌ Expected 18, found ${SCENARIO_COUNT}${NC}"

            # List what's there
            echo ""
            echo "What's in /scenarios:"
            kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ls -1 /scenarios 2>/dev/null || echo "Error listing"
        fi

        # Check permissions on validate.sh
        echo ""
        echo "Checking validate.sh permissions:"
        kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ls -la /scenarios/01-hpa-autoscaling/validate.sh 2>/dev/null || echo "File not found"

        # Check README.md exists
        if kubectl exec -n ${NAMESPACE} ${POD_NAME} -- test -f /scenarios/01-hpa-autoscaling/README.md 2>/dev/null; then
            echo -e "${GREEN}✅ README.md files exist${NC}"
        else
            echo -e "${RED}❌ README.md files missing${NC}"
        fi

    else
        echo -e "${RED}❌ /scenarios directory DOES NOT EXIST in pod${NC}"
        echo ""
        echo "Listing root directory of pod:"
        kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ls -la / 2>/dev/null | grep scenarios || echo "No scenarios directory found"
    fi
done

echo ""
echo ""

# ============================================
# TEST 4: Check backend API endpoint
# ============================================
echo -e "${CYAN}[TEST 4] Testing backend API endpoint...${NC}"

# Get NodePort
ACTUAL_NODEPORT=$(kubectl get svc k8s-demo-nodeport -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)

if [ -z "$ACTUAL_NODEPORT" ]; then
    echo -e "${RED}❌ Cannot get NodePort service${NC}"
    echo ""
    echo "Services in namespace:"
    kubectl get svc -n ${NAMESPACE}
else
    echo "NodePort: ${ACTUAL_NODEPORT}"

    # Test /health endpoint
    echo ""
    echo "Testing /health endpoint..."
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${ACTUAL_NODEPORT}/health 2>/dev/null)
    if [ "${HEALTH_RESPONSE}" = "200" ]; then
        echo -e "${GREEN}✅ Health endpoint responding (200)${NC}"
    else
        echo -e "${RED}❌ Health endpoint returned: ${HEALTH_RESPONSE}${NC}"
    fi

    # Test /api/scenarios endpoint
    echo ""
    echo "Testing /api/scenarios endpoint..."
    SCENARIOS_RESPONSE=$(curl -s http://localhost:${ACTUAL_NODEPORT}/api/scenarios 2>/dev/null)

    if [ -z "$SCENARIOS_RESPONSE" ]; then
        echo -e "${RED}❌ No response from /api/scenarios${NC}"
    else
        echo "Response received (first 200 chars):"
        echo "${SCENARIOS_RESPONSE}" | head -c 200
        echo ""

        # Count scenarios in response
        SCENARIO_API_COUNT=$(echo "${SCENARIOS_RESPONSE}" | grep -o '"id":' | wc -l)
        echo ""
        echo "Scenarios in API response: ${SCENARIO_API_COUNT}"

        if [ "${SCENARIO_API_COUNT}" -eq 18 ]; then
            echo -e "${GREEN}✅ API returning all 18 scenarios${NC}"
        elif [ "${SCENARIO_API_COUNT}" -eq 0 ]; then
            echo -e "${RED}❌ API returning 0 scenarios (empty array)${NC}"
            echo ""
            echo "Full API response:"
            echo "${SCENARIOS_RESPONSE}"
        else
            echo -e "${YELLOW}⚠️  API returning ${SCENARIO_API_COUNT} scenarios (expected 18)${NC}"
        fi
    fi
fi

echo ""
echo ""

# ============================================
# TEST 5: Check backend logs
# ============================================
echo -e "${CYAN}[TEST 5] Checking backend logs for errors...${NC}"

FIRST_POD="${POD_NAMES[0]}"
echo "Logs from ${FIRST_POD} (last 30 lines):"
echo "---"
kubectl logs -n ${NAMESPACE} ${FIRST_POD} --tail=30 2>/dev/null | grep -E "(ERROR|error|scenarios|/api/scenarios)" || echo "No relevant log entries found"

echo ""
echo ""

# ============================================
# TEST 6: Check Python code for scenarios loading
# ============================================
echo -e "${CYAN}[TEST 6] Checking how backend loads scenarios...${NC}"

echo "Checking main.py in pod..."
kubectl exec -n ${NAMESPACE} ${FIRST_POD} -- cat /app/src/main.py 2>/dev/null | grep -A 10 "def get_scenarios" || echo "Cannot find get_scenarios function"

echo ""
echo ""

# ============================================
# TEST 7: Test from inside pod
# ============================================
echo -e "${CYAN}[TEST 7] Testing scenarios access from inside pod...${NC}"

echo "Trying to list scenarios from inside pod:"
kubectl exec -n ${NAMESPACE} ${FIRST_POD} -- ls -la /scenarios 2>/dev/null || echo "Failed to list /scenarios"

echo ""

echo "Trying to read first README.md:"
kubectl exec -n ${NAMESPACE} ${FIRST_POD} -- head -20 /scenarios/01-hpa-autoscaling/README.md 2>/dev/null || echo "Failed to read README.md"

echo ""
echo ""

# ============================================
# TEST 8: Manual copy test
# ============================================
echo -e "${CYAN}[TEST 8] Manual copy test...${NC}"

echo "Would you like to manually copy scenarios to pods now? (yes/no)"
read -p "> " MANUAL_COPY

if [ "$MANUAL_COPY" = "yes" ]; then
    echo ""
    echo "Copying scenarios to all pods..."

    for i in "${!POD_NAMES[@]}"; do
        POD_NAME="${POD_NAMES[$i]}"
        POD_NUM=$((i + 1))

        echo ""
        echo "[$POD_NUM/${POD_COUNT}] Copying to ${POD_NAME}..."

        # Copy
        kubectl cp k8s-scenarios/ ${NAMESPACE}/${POD_NAME}:/scenarios/ 2>&1 | grep -v "tar:" || true

        # Make executable
        kubectl exec -n ${NAMESPACE} ${POD_NAME} -- chmod +x /scenarios/*/validate.sh 2>/dev/null || true

        # Verify
        NEW_COUNT=$(kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ls /scenarios 2>/dev/null | wc -l)
        echo "   Scenarios now in pod: ${NEW_COUNT}"
    done

    echo ""
    echo -e "${GREEN}Manual copy complete!${NC}"
    echo ""
    echo "Testing API again..."
    sleep 2

    SCENARIOS_RESPONSE=$(curl -s http://localhost:${ACTUAL_NODEPORT}/api/scenarios 2>/dev/null)
    SCENARIO_API_COUNT=$(echo "${SCENARIOS_RESPONSE}" | grep -o '"id":' | wc -l)

    if [ "${SCENARIO_API_COUNT}" -eq 18 ]; then
        echo -e "${GREEN}✅ SUCCESS! API now returning ${SCENARIO_API_COUNT} scenarios${NC}"
        echo ""
        echo "Open your browser: http://localhost:${ACTUAL_NODEPORT}/static/scenarios.html"
    else
        echo -e "${RED}❌ Still showing ${SCENARIO_API_COUNT} scenarios${NC}"
    fi
fi

echo ""
echo ""

# ============================================
# SUMMARY & RECOMMENDATIONS
# ============================================
echo "=========================================="
echo "SUMMARY & RECOMMENDATIONS"
echo "=========================================="
echo ""

# Determine the issue
if [ ! -d "k8s-scenarios" ]; then
    echo -e "${RED}ISSUE: k8s-scenarios directory not found${NC}"
    echo "SOLUTION: Ensure you're in the project root directory"

elif [ ${POD_COUNT} -eq 0 ]; then
    echo -e "${RED}ISSUE: No application pods running${NC}"
    echo "SOLUTION: Run ./kind_setup.sh to deploy"

elif [ "${SCENARIO_COUNT:-0}" -eq 0 ]; then
    echo -e "${RED}ISSUE: Scenarios not copied to pods${NC}"
    echo ""
    echo "SOLUTION: Run this to copy scenarios:"
    echo ""
    echo "  POD=\$(kubectl get pods -n ${NAMESPACE} -l app=k8s-demo-app -o jsonpath='{.items[0].metadata.name}')"
    echo "  kubectl cp k8s-scenarios/ ${NAMESPACE}/\$POD:/scenarios/"
    echo "  kubectl exec -n ${NAMESPACE} \$POD -- chmod +x /scenarios/*/validate.sh"
    echo ""

elif [ "${SCENARIO_API_COUNT:-0}" -eq 0 ]; then
    echo -e "${RED}ISSUE: Scenarios in pods but API returns empty${NC}"
    echo ""
    echo "This suggests a backend code issue. Check:"
    echo "  1. How main.py loads scenarios"
    echo "  2. The SCENARIOS_DIR path in main.py"
    echo "  3. Backend logs for errors"
    echo ""
    echo "Check with:"
    echo "  kubectl logs -n ${NAMESPACE} ${FIRST_POD}"

else
    echo -e "${GREEN}Everything looks good!${NC}"
    echo ""
    echo "Access scenarios at:"
    echo "  http://localhost:${ACTUAL_NODEPORT}/static/scenarios.html"
fi

echo ""
echo "=========================================="
echo "END OF DEBUG"
echo "=========================================="
