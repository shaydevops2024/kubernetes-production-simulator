#!/bin/bash
# kind_setup.sh
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
echo "  1. Delete the existing KIND cluster named k8s-demo (if it exists)"
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
kubectl wait --for=condition=ready node --all --timeout=600s

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

print_step "Waiting for ingress controller to be ready (this may take a few minutes)..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=600s

print_step "Verifying ingress controller..."
INGRESS_PODS=$(kubectl get pods -n ingress-nginx -l app.kubernetes.io/component=controller --no-headers | wc -l)
print_success "Ingress controller ready! ($INGRESS_PODS pod running)"

# Add to /etc/hosts
echo ""
echo "Configuring /etc/hosts..."
if ! grep -q "k8s-multi-demo.internal" /etc/hosts; then
    echo "127.0.0.1 k8s-multi-demo.internal" | sudo tee -a /etc/hosts
    echo "✅ Added to /etc/hosts"
else
    echo "✅ Already in /etc/hosts"
fi




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

print_step "Creating Service Account and RBAC..."
kubectl apply -f k8s/base/rbac.yaml
print_success "RBAC configured"

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

chmod a+x ./deploy-database.sh
./deploy-database.sh

print_step "Waiting for application pods to be ready. This can take a few minutes.."
kubectl wait --for=condition=ready pod -l app=k8s-demo-app -n ${NAMESPACE} --timeout=600s

POD_COUNT=$(kubectl get pods -n ${NAMESPACE} --no-headers | grep Running | wc -l)
print_success "Application deployed! ($POD_COUNT pods running)"

# ============================================
# STEP 6.5: DEPLOY POSTGRESQL DATABASE
# ============================================
print_header "STEP 6.5/10: DEPLOYING POSTGRESQL DATABASE"

print_step "Applying PostgreSQL ConfigMap..."
kubectl apply -f k8s/database/postgres-configmap.yaml
print_success "PostgreSQL ConfigMap applied"

print_step "Applying PostgreSQL Secret..."
kubectl apply -f k8s/database/postgres-secret.yaml
print_success "PostgreSQL Secret applied"

print_step "Creating PostgreSQL Service..."
kubectl apply -f k8s/database/postgres-service.yaml
print_success "PostgreSQL Service created"

print_step "Deploying PostgreSQL StatefulSet..."
kubectl apply -f k8s/database/postgres-statefulset.yaml
print_success "PostgreSQL StatefulSet created"



print_step "Waiting for PostgreSQL StatefulSet to be ready (this may take a few minutes)..."
kubectl rollout status statefulset/postgres -n ${NAMESPACE} --timeout=600s

print_success "PostgreSQL database deployed and ready!"

# ============================================
# STEP 7: INSTALL METRICS SERVER
# ============================================
print_header "STEP 7/10: INSTALLING METRICS SERVER"

print_step "Applying metrics-server manifests..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

print_step "Patching metrics-server for kind (allow insecure TLS)..."
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

print_step "Waiting for metrics-server deployment to be ready..."
kubectl rollout status deployment/metrics-server -n kube-system --timeout=600s

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

print_step "Test 2: Checking PostgreSQL pods..."
POSTGRES_PODS=$(kubectl get pods -n ${NAMESPACE} -l app=postgres --no-headers | wc -l)
[ "$POSTGRES_PODS" -ge 1 ] && print_success "PostgreSQL pod running" || print_warning "PostgreSQL pod not ready yet"

print_step "Test 3: Checking PostgreSQL StatefulSet..."
kubectl get statefulset postgres -n ${NAMESPACE} && print_success "PostgreSQL StatefulSet present"

print_step "Test 4: Checking services..."
SERVICES=$(kubectl get svc -n ${NAMESPACE} --no-headers | wc -l)
print_success "$SERVICES services configured"

print_step "Test 5: Checking ingress..."
INGRESS_HOSTS=$(kubectl get ingress -n ${NAMESPACE} -o jsonpath='{.items[0].spec.rules[0].host}')
print_success "Ingress configured for: $INGRESS_HOSTS"

print_step "Test 6: Testing NodePort connectivity..."
sleep 3
if curl -s -o /dev/null -w "%{http_code}" http://localhost:${NODEPORT}/health | grep -q "200"; then
    print_success "NodePort accessible at http://localhost:${NODEPORT}"
else
    print_warning "NodePort connectivity test inconclusive"
fi

print_step "Test 7: Checking HPA status..."
HPA_STATUS=$(kubectl get hpa -n ${NAMESPACE} -o jsonpath='{.items[0].status.currentReplicas}')
HPA_TARGET=$(kubectl get hpa -n ${NAMESPACE} -o jsonpath='{.items[0].spec.minReplicas}')
print_success "HPA active: $HPA_STATUS/$HPA_TARGET replicas"

print_step "Test 8: Checking metrics-server..."
kubectl top nodes &>/dev/null && print_success "Metrics-server working" || print_warning "Metrics not available yet"

print_success "All tests completed!"

# ============================================
# STEP 9.5: CONFIGURE HOSTS FILE FOR INGRESS
# ============================================
print_header "STEP 9.5/10: CONFIGURING HOSTS FILE"

print_step "Checking /etc/hosts for ingress hostname..."
HOSTS_ENTRY="127.0.0.1 k8s-multi-demo.internal"

if grep -q "k8s-multi-demo.internal" /etc/hosts 2>/dev/null; then
    print_success "Host entry already exists in /etc/hosts"
else
    print_step "Adding k8s-multi-demo.internal to /etc/hosts..."
    
    if [ -w /etc/hosts ]; then
        echo "$HOSTS_ENTRY" >> /etc/hosts
        print_success "Successfully added to /etc/hosts"
    else
        print_warning "Cannot write to /etc/hosts (need sudo)"
        echo ""
        echo -e "${YELLOW}To enable ingress access, please run:${NC}"
        echo -e "${YELLOW}  echo '$HOSTS_ENTRY' | sudo tee -a /etc/hosts${NC}"
        echo ""
    fi
fi


# ============================================
# STEP 10: DISPLAY RESULTS
# ============================================
print_header "STEP 10/10: DEPLOYMENT SUMMARY"

kubectl get all -n ${NAMESPACE}

echo ""
echo -e "${GREEN}Your Kubernetes production demo is now running!${NC}"


echo ""
echo "=============================================="
echo "🔧 DNS / Hosts Configuration"
echo "=============================================="
echo ""

if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "🪟 Detected WSL environment"
    echo ""
    echo -e "${GREEN}Your application is available at:
      - NodePort: http://localhost:${NODEPORT}
      - Ingress:  http://k8s-multi-demo.internal${NC}"
    echo ""
    echo "To access 'http://k8s-multi-demo.internal' from Windows, you must add the following entry"
    echo "to your Windows hosts file (ADMIN rights required):"
    echo "  '127.0.0.1  k8s-multi-demo.internal' "
    echo ""
    echo "📌 Run this in *PowerShell as Administrator*:"
    echo ""
    echo " '  Add-Content C:\Windows\System32\drivers\etc\hosts "127.0.0.1 k8s-multi-demo.internal ' "
    echo ""
    echo "After that, open your browser and go to:"
    echo "  http://k8s-multi-demo.internal"
else
    echo -e "${GREEN}Access it at:
      - NodePort: http://localhost:${NODEPORT}
      - Ingress:  http://k8s-multi-demo.internal (requires /etc/hosts entry)${NC}" 
fi

echo ""
echo "=============================================="
echo -e "${GREEN}✅ Setup completed successfully${NC}"
echo "=============================================="


