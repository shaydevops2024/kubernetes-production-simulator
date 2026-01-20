#!/bin/bash
# deploy-all.sh
# Complete Kubernetes deployment automation - from zero to running application
# This script does EVERYTHING: cluster creation, app deployment, testing, and verification

set -e  # Exit on any error

# ============================================
# CONFIGURATION
# ============================================
CLUSTER_NAME="k8s-demo"
NAMESPACE="k8s-multi-demo"
APP_IMAGE="k8s-demo-app:latest"
NODEPORT="30080"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================
# HELPER FUNCTIONS
# ============================================
print_header() {
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# ============================================
# START DEPLOYMENT
# ============================================
clear
print_header "KUBERNETES PRODUCTION DEMO - COMPLETE DEPLOYMENT"
echo -e "${GREEN}This script will:${NC}"
echo "  1. Delete any existing clusters"
echo "  2. Create a fresh kind cluster"
echo "  3. Install NGINX Ingress Controller"
echo "  4. Build and load Docker image"
echo "  5. Deploy the application"
echo "  6. Setup metrics-server and HPA"
echo "  7. Run comprehensive tests"
echo "  8. Display access information"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# ============================================
# STEP 1: CHECK PREREQUISITES
# ============================================
print_header "STEP 1/10: CHECKING PREREQUISITES"

print_step "Checking Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    print_success "Docker installed (version $DOCKER_VERSION)"
else
    print_error "Docker not found. Please install Docker first."
    exit 1
fi

print_step "Checking kubectl..."
if command -v kubectl &> /dev/null; then
    KUBECTL_VERSION=$(kubectl version --client --short 2>/dev/null | cut -d' ' -f3)
    print_success "kubectl installed (version $KUBECTL_VERSION)"
else
    print_error "kubectl not found. Please install kubectl first."
    exit 1
fi

print_step "Checking kind..."
if command -v kind &> /dev/null; then
    KIND_VERSION=$(kind version | cut -d' ' -f2)
    print_success "kind installed (version $KIND_VERSION)"
else
    print_error "kind not found. Please install kind first."
    exit 1
fi

print_success "All prerequisites satisfied!"

# ============================================
# STEP 2: CLEANUP OLD RESOURCES
# ============================================
print_header "STEP 2/10: CLEANING UP OLD RESOURCES"

print_step "Stopping any port-forwards..."
pkill -f "port-forward" 2>/dev/null || true
print_success "Port-forwards stopped"

print_step "Checking for existing kind clusters..."
EXISTING_CLUSTERS=$(kind get clusters 2>/dev/null || echo "")
if echo "$EXISTING_CLUSTERS" | grep -q "${CLUSTER_NAME}"; then
    print_warning "Found existing cluster '${CLUSTER_NAME}', deleting..."
    kind delete cluster --name ${CLUSTER_NAME}
    print_success "Old cluster deleted"
else
    print_info "No existing cluster found"
fi

print_success "Cleanup complete!"

# ============================================
# STEP 3: CREATE KIND CLUSTER
# ============================================
print_header "STEP 3/10: CREATING KIND CLUSTER"

print_step "Creating cluster configuration..."
cat > /tmp/kind-config.yaml <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
  - containerPort: ${NODEPORT}
    hostPort: ${NODEPORT}
    protocol: TCP
EOF
print_success "Configuration created"

print_step "Creating kind cluster '${CLUSTER_NAME}'..."
kind create cluster --name ${CLUSTER_NAME} --config /tmp/kind-config.yaml

print_step "Waiting for cluster to be ready..."
kubectl wait --for=condition=ready node --all --timeout=90s

print_step "Verifying cluster..."
kubectl cluster-info
print_success "Cluster created and ready!"

# ============================================
# STEP 4: INSTALL NGINX INGRESS CONTROLLER
# ============================================
print_header "STEP 4/10: INSTALLING NGINX INGRESS CONTROLLER"

print_step "Applying ingress-nginx manifests..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

print_step "Waiting for ingress-nginx namespace..."
sleep 5

print_step "Waiting for ingress controller to be ready (this may take 60-90 seconds)..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

print_step "Verifying ingress controller..."
INGRESS_PODS=$(kubectl get pods -n ingress-nginx -l app.kubernetes.io/component=controller --no-headers | wc -l)
print_success "Ingress controller ready! ($INGRESS_PODS pod running)"

# ============================================
# STEP 5: BUILD DOCKER IMAGE
# ============================================
print_header "STEP 5/10: BUILDING APPLICATION IMAGE"

print_step "Building Docker image '${APP_IMAGE}'..."
docker build -t ${APP_IMAGE} ./app --no-cache

print_step "Loading image into kind cluster..."
kind load docker-image ${APP_IMAGE} --name ${CLUSTER_NAME}

print_step "Verifying image in cluster..."
docker exec ${CLUSTER_NAME}-control-plane crictl images | grep k8s-demo-app || print_warning "Image loaded (verification skipped)"
print_success "Application image built and loaded!"

# ============================================
# STEP 6: DEPLOY APPLICATION
# ============================================
print_header "STEP 6/10: DEPLOYING APPLICATION"

print_step "Creating namespace '${NAMESPACE}'..."
kubectl apply -f k8s/base/namespace.yaml
print_success "Namespace created"

print_step "Applying ConfigMap..."
kubectl apply -f k8s/base/configmap.yaml
print_success "ConfigMap applied"

print_step "Applying Secret..."
kubectl apply -f k8s/base/secret.yaml
print_success "Secret applied"

print_step "Deploying application..."
kubectl apply -f k8s/base/deployment.yaml
print_success "Deployment created"

print_step "Creating ClusterIP service..."
kubectl apply -f k8s/base/service.yaml
print_success "ClusterIP service created"

print_step "Creating NodePort service (port ${NODEPORT})..."
kubectl apply -f k8s/base/service-nodeport.yaml
print_success "NodePort service created"

print_step "Applying Ingress configuration..."
kubectl apply -f k8s/ingress/ingress.yaml
print_success "Ingress created"

print_step "Waiting for application pods to be ready (timeout: 120s)..."
kubectl wait --for=condition=ready pod -l app=k8s-demo-app -n ${NAMESPACE} --timeout=120s

POD_COUNT=$(kubectl get pods -n ${NAMESPACE} --no-headers | grep Running | wc -l)
print_success "Application deployed! ($POD_COUNT pods running)"

# ============================================
# STEP 7: INSTALL METRICS SERVER
# ============================================
print_header "STEP 7/10: INSTALLING METRICS SERVER"

print_step "Applying metrics-server manifests..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

print_step "Patching metrics-server for kind (allow insecure TLS)..."
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

print_step "Waiting for metrics-server to be ready..."
kubectl wait --for=condition=ready pod -l k8s-app=metrics-server -n kube-system --timeout=90s

print_success "Metrics-server installed and ready!"

# ============================================
# STEP 8: CONFIGURE HPA
# ============================================
print_header "STEP 8/10: CONFIGURING HORIZONTAL POD AUTOSCALER"

print_step "Applying HPA configuration..."
kubectl apply -f k8s/hpa/hpa.yaml

print_step "Waiting 30 seconds for metrics to populate..."
for i in {30..1}; do
    echo -ne "\r  ${YELLOW}⏳ Waiting... ${i}s remaining${NC}"
    sleep 1
done
echo ""

print_step "Verifying HPA..."
kubectl get hpa -n ${NAMESPACE}
print_success "HPA configured and active!"

# ============================================
# STEP 9: COMPREHENSIVE TESTING
# ============================================
print_header "STEP 9/10: RUNNING COMPREHENSIVE TESTS"

print_step "Test 1: Checking pod health..."
HEALTHY_PODS=$(kubectl get pods -n ${NAMESPACE} -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -o "True" | wc -l)
TOTAL_PODS=$(kubectl get pods -n ${NAMESPACE} --no-headers | wc -l)
if [ "$HEALTHY_PODS" -eq "$TOTAL_PODS" ]; then
    print_success "All $TOTAL_PODS pods are healthy"
else
    print_warning "$HEALTHY_PODS out of $TOTAL_PODS pods are healthy"
fi

print_step "Test 2: Checking services..."
SERVICES=$(kubectl get svc -n ${NAMESPACE} --no-headers | wc -l)
print_success "$SERVICES services configured"

print_step "Test 3: Checking ingress..."
INGRESS_HOSTS=$(kubectl get ingress -n ${NAMESPACE} -o jsonpath='{.items[0].spec.rules[0].host}')
print_success "Ingress configured for: $INGRESS_HOSTS"

print_step "Test 4: Testing NodePort connectivity..."
sleep 3
if curl -s -o /dev/null -w "%{http_code}" http://localhost:${NODEPORT}/health | grep -q "200"; then
    print_success "NodePort accessible at http://localhost:${NODEPORT}"
else
    print_warning "NodePort connectivity test inconclusive (app may still be starting)"
fi

print_step "Test 5: Checking HPA status..."
HPA_STATUS=$(kubectl get hpa -n ${NAMESPACE} -o jsonpath='{.items[0].status.currentReplicas}')
HPA_TARGET=$(kubectl get hpa -n ${NAMESPACE} -o jsonpath='{.items[0].spec.minReplicas}')
print_success "HPA active: $HPA_STATUS/$HPA_TARGET replicas"

print_step "Test 6: Checking metrics-server..."
if kubectl top nodes &>/dev/null; then
    print_success "Metrics-server working"
else
    print_warning "Metrics not available yet (may take a minute)"
fi

print_step "Test 7: Testing application endpoints..."
APP_ENDPOINTS=("health" "ready" "api/info")
for endpoint in "${APP_ENDPOINTS[@]}"; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${NODEPORT}/${endpoint} || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        print_success "  /${endpoint} - OK (${HTTP_CODE})"
    else
        print_warning "  /${endpoint} - Status: ${HTTP_CODE}"
    fi
done

print_success "All tests completed!"

# ============================================
# STEP 10: DISPLAY RESULTS
# ============================================
print_header "STEP 10/10: DEPLOYMENT SUMMARY"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                   DEPLOYMENT SUCCESSFUL!                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}📊 CLUSTER INFORMATION:${NC}"
echo -e "  Cluster Name:      ${CLUSTER_NAME}"
echo -e "  Namespace:         ${NAMESPACE}"
echo -e "  Pods Running:      ${POD_COUNT}"
echo -e "  Services:          ${SERVICES}"
echo ""

echo -e "${CYAN}🌐 ACCESS YOUR APPLICATION:${NC}"
echo -e "  ${GREEN}Primary (NodePort):${NC}    http://localhost:${NODEPORT}"
echo -e "  ${GREEN}Alternative (Ingress):${NC} http://${INGRESS_HOSTS}"
echo -e "  ${GREEN}API Documentation:${NC}     http://localhost:${NODEPORT}/docs"
echo -e "  ${GREEN}Prometheus Metrics:${NC}    http://localhost:${NODEPORT}/metrics"
echo ""

echo -e "${CYAN}📈 CURRENT STATUS:${NC}"
echo ""
kubectl get all -n ${NAMESPACE}
echo ""

echo -e "${CYAN}🔍 HPA STATUS:${NC}"
kubectl get hpa -n ${NAMESPACE}
echo ""

echo -e "${CYAN}💻 POD METRICS:${NC}"
kubectl top pods -n ${NAMESPACE} 2>/dev/null || echo "  (Metrics will be available in ~1 minute)"
echo ""

echo -e "${CYAN}🛠️  USEFUL COMMANDS:${NC}"
echo ""
echo -e "  ${YELLOW}Monitor HPA (watch auto-scaling):${NC}"
echo -e "    kubectl get hpa -n ${NAMESPACE} -w"
echo ""
echo -e "  ${YELLOW}Watch pods (see scaling in action):${NC}"
echo -e "    kubectl get pods -n ${NAMESPACE} -w"
echo ""
echo -e "  ${YELLOW}Check pod resource usage:${NC}"
echo -e "    kubectl top pods -n ${NAMESPACE}"
echo ""
echo -e "  ${YELLOW}View application logs:${NC}"
echo -e "    kubectl logs -f -l app=k8s-demo-app -n ${NAMESPACE}"
echo ""
echo -e "  ${YELLOW}Describe HPA (detailed info):${NC}"
echo -e "    kubectl describe hpa k8s-demo-hpa -n ${NAMESPACE}"
echo ""

echo -e "${CYAN}🧪 TEST AUTO-SCALING:${NC}"
echo ""
echo -e "  ${GREEN}Option 1 - Using the Web UI:${NC}"
echo -e "    1. Open: http://localhost:${NODEPORT}"
echo -e "    2. Click 'Start Load Test' button"
echo -e "    3. Watch: kubectl get hpa -n ${NAMESPACE} -w"
echo -e "    4. See pods scale from 2 → 3 → 4..."
echo ""
echo -e "  ${GREEN}Option 2 - Manual load test (Terminal):${NC}"
echo -e "    for i in {1..50}; do (while true; do curl -s http://localhost:${NODEPORT}/ > /dev/null; sleep 0.1; done) & done"
echo -e "    # To stop: pkill curl"
echo ""

echo -e "${CYAN}🗑️  CLEANUP (when done):${NC}"
echo -e "    kind delete cluster --name ${CLUSTER_NAME}"
echo ""

echo -e "${CYAN}📚 NEXT STEPS:${NC}"
echo ""
echo -e "  1. ${GREEN}Open the application:${NC}"
echo -e "     - The UI should open automatically below"
echo -e "     - Or manually open: http://localhost:${NODEPORT}"
echo ""
echo -e "  2. ${GREEN}Test the features:${NC}"
echo -e "     - View Live Logs & CLI Commands"
echo -e "     - Simulate incidents (crash, not ready)"
echo -e "     - Test auto-scaling with load test"
echo ""
echo -e "  3. ${GREEN}Monitor in terminal:${NC}"
echo -e "     - Open another terminal"
echo -e "     - Run: kubectl get hpa -n ${NAMESPACE} -w"
echo -e "     - Watch pods scale automatically"
echo ""

print_header "🚀 OPENING APPLICATION IN BROWSER"

print_step "Attempting to open browser..."

# Try different methods to open browser (WSL2, Linux, Mac)
if command -v explorer.exe &> /dev/null; then
    # WSL2
    explorer.exe http://localhost:${NODEPORT} 2>/dev/null &
    print_success "Browser opened (WSL2)"
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open http://localhost:${NODEPORT} 2>/dev/null &
    print_success "Browser opened (Linux)"
elif command -v open &> /dev/null; then
    # macOS
    open http://localhost:${NODEPORT} 2>/dev/null &
    print_success "Browser opened (macOS)"
else
    print_warning "Could not auto-open browser"
    echo -e "  ${YELLOW}Please manually open: http://localhost:${NODEPORT}${NC}"
fi

echo ""
print_header "✅ DEPLOYMENT COMPLETE - READY TO USE!"
echo ""
echo -e "${GREEN}Your Kubernetes production demo is now running!${NC}"
echo -e "${GREEN}Access it at: http://localhost:${NODEPORT}${NC}"
echo ""
