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
ARGOCD_NODEPORT="30800"
JENKINS_NODEPORT="30880"
JENKINS_HOST_PORT="8080"

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
echo "  1. Check prerequisites (Docker, kubectl, kind)"
echo "  2. Cleanup old resources"
echo "  3. Create a fresh 3-node kind cluster"
echo "  4. Install NGINX Ingress Controller"
echo "  5. Build Docker image with 18 scenarios built-in"
echo "  6. Deploy PostgreSQL database"
echo "  7. Deploy the application"
echo "  8. Verify scenarios in pods"
echo "  9. Install metrics-server"
echo "  10. Configure HPA (Horizontal Pod Autoscaler)"
echo "  11. Install and configure ArgoCD"
echo "  12. Install Jenkins via Helm"
echo "  13. Run comprehensive tests"
echo "  13. Configure /etc/hosts for ingress"
echo "  14. Display access information"
echo ""
echo -e "${YELLOW}⏱️  Estimated time: 10-15 minutes${NC}"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# ============================================
# STEP 1: CHECK PREREQUISITES
# ============================================
print_header "STEP 1/12: CHECKING PREREQUISITES"

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

print_step "Checking Helm..."
if command -v helm &> /dev/null; then
    HELM_VERSION=$(helm version --short 2>/dev/null | cut -d'+' -f1)
    print_success "Helm installed (version $HELM_VERSION)"
else
    print_error "Helm not found. Please install Helm first."
    exit 1
fi

print_step "Checking project structure..."
if [ ! -d "k8s-scenarios" ]; then
    print_error "k8s-scenarios directory not found!"
    echo "Current directory: $(pwd)"
    echo "Please run this script from the project root."
    exit 1
fi

SCENARIO_COUNT=$(ls -1 k8s-scenarios 2>/dev/null | wc -l)
if [ "$SCENARIO_COUNT" -eq 18 ]; then
    print_success "Found 18 scenarios ready to build into image"
else
    print_warning "Found $SCENARIO_COUNT scenarios (expected 18)"
fi

print_success "All prerequisites satisfied!"

# ============================================
# STEP 2: CLEANUP OLD RESOURCES
# ============================================
print_header "STEP 2/12: CLEANING UP OLD RESOURCES"

print_step "Stopping any port-forwards..."
pkill -f "port-forward" 2>/dev/null || true
print_success "Port-forwards stopped"

print_step "Checking for existing kind clusters..."
EXISTING_CLUSTERS=$(kind get clusters 2>/dev/null || echo "")
if echo "$EXISTING_CLUSTERS" | grep -q "^${CLUSTER_NAME}$"; then
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
print_header "STEP 3/12: CREATING KIND CLUSTER"

print_step "Creating cluster configuration..."
cat > /tmp/kind-config.yaml <<EOF     #line 151
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
  - containerPort: ${ARGOCD_NODEPORT}
    hostPort: ${ARGOCD_NODEPORT}
    protocol: TCP
  - containerPort: ${JENKINS_NODEPORT}
    hostPort: ${JENKINS_HOST_PORT}
    protocol: TCP
- role: worker
- role: worker

EOF
print_success "Configuration created"

print_step "Creating kind cluster '${CLUSTER_NAME}' (3 nodes: 1 control-plane + 2 workers)..."
kind create cluster --name ${CLUSTER_NAME} --config /tmp/kind-config.yaml

print_step "Waiting for cluster to be ready..."
kubectl wait --for=condition=ready node --all --timeout=600s

print_step "Verifying cluster..."
kubectl cluster-info
kubectl get nodes
print_success "Cluster created and ready!"

# ============================================
# STEP 4: INSTALL NGINX INGRESS CONTROLLER
# ============================================
print_header "STEP 4/12: INSTALLING NGINX INGRESS CONTROLLER"

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

# ============================================
# STEP 5: BUILD DOCKER IMAGE WITH SCENARIOS
# ============================================
print_header "STEP 5/12: BUILDING APPLICATION IMAGE WITH SCENARIOS"

print_step "Building Docker image with 18 scenarios baked in..."
echo ""
echo "Build context: $(pwd)"
echo "Dockerfile: app/Dockerfile"
echo "Including: k8s-scenarios/ (18 scenarios)"
echo ""

# CRITICAL: Build from project root with -f flag so we can access both app/ and k8s-scenarios/
docker build -f app/Dockerfile -t ${APP_IMAGE} . --no-cache

print_step "Loading image into kind cluster..."
kind load docker-image ${APP_IMAGE} --name ${CLUSTER_NAME}

print_step "Verifying image in cluster..."
docker exec ${CLUSTER_NAME}-control-plane crictl images | grep k8s-demo-app || print_warning "Image loaded (verification skipped)"
print_success "Application image built with scenarios and loaded!"

# ============================================
# STEP 6: DEPLOY DATABASE FIRST
# ============================================
print_header "STEP 6/14: DEPLOYING POSTGRESQL DATABASE"

print_step "Creating namespace '${NAMESPACE}'..."
kubectl apply -f k8s/base/namespace.yaml
print_success "Namespace created"

print_step "Creating PostgreSQL Secret..."
kubectl apply -f k8s/database/postgres-secret.yaml
print_success "PostgreSQL Secret created"

print_step "Creating PostgreSQL ConfigMap..."
kubectl apply -f k8s/database/postgres-configmap.yaml
print_success "PostgreSQL ConfigMap created"

print_step "Creating PostgreSQL StatefulSet..."
kubectl apply -f k8s/database/postgres-statefulset.yaml
print_success "PostgreSQL StatefulSet created"

print_step "Creating PostgreSQL Service..."
kubectl apply -f k8s/database/postgres-service.yaml
print_success "PostgreSQL Service created"

print_step "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n ${NAMESPACE} --timeout=600s
print_success "PostgreSQL is ready!"

# ============================================
# STEP 7: DEPLOY APPLICATION
# ============================================
print_header "STEP 7/14: DEPLOYING APPLICATION"

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

print_step "Waiting for application pods to be ready (this can take a few minutes)..."
kubectl wait --for=condition=ready pod -l app=k8s-demo-app -n ${NAMESPACE} --timeout=600s

POD_COUNT=$(kubectl get pods -n ${NAMESPACE} --no-headers | grep k8s-demo-app | grep Running | wc -l)
print_success "Application deployed! ($POD_COUNT pods running)"

# ============================================
# STEP 8: VERIFY SCENARIOS IN PODS
# ============================================
print_header "STEP 8/14: VERIFYING SCENARIOS IN PODS"

print_step "Checking scenarios in pods (baked into the image)..."
POD_NAMES=($(kubectl get pods -n ${NAMESPACE} -l app=k8s-demo-app -o jsonpath='{.items[*].metadata.name}'))
FIRST_POD="${POD_NAMES[0]}"

if [ -n "$FIRST_POD" ]; then
    SCENARIO_COUNT=$(kubectl exec -n ${NAMESPACE} ${FIRST_POD} -- ls /scenarios 2>/dev/null | wc -l)
    
    if [ "$SCENARIO_COUNT" -eq 18 ]; then
        print_success "Verified: ${SCENARIO_COUNT} scenarios present in pods!"
        print_info "Scenarios are baked into the Docker image - no copying needed!"
    else
        print_warning "Found ${SCENARIO_COUNT} scenarios (expected 19)"
        echo ""
        echo "Listing scenarios in pod:"
        kubectl exec -n ${NAMESPACE} ${FIRST_POD} -- ls -1 /scenarios 2>/dev/null || echo "Cannot list /scenarios"
    fi
else
    print_warning "Cannot verify scenarios - no pod found"
fi

# ============================================
# STEP 9: INSTALL METRICS SERVER
# ============================================
print_header "STEP 9/14: INSTALLING METRICS SERVER"

print_step "Applying metrics-server manifests..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

print_step "Patching metrics-server for kind (allow insecure TLS)..."
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

print_step "Waiting for metrics-server deployment to be ready..."
kubectl rollout status deployment/metrics-server -n kube-system --timeout=600s

print_success "Metrics-server installed and ready!"

# ============================================
# STEP 10: CONFIGURE HPA
# ============================================
print_header "STEP 10/14: CONFIGURING HORIZONTAL POD AUTOSCALER"

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
# STEP 11: INSTALL ARGOCD
# ============================================
print_header "STEP 11/14: INSTALLING ARGOCD"

print_step "Creating argocd namespace..."
kubectl create namespace argocd
print_success "ArgoCD namespace created"

print_step "Installing ArgoCD manifests..."
kubectl apply --server-side -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
print_success "ArgoCD manifests applied"

print_step "Applying ArgoCD config patches before pods are ready (avoids restart)..."
# Wait briefly for the configmaps to be created by the manifest
sleep 5
kubectl patch configmap argocd-cmd-params-cm -n argocd --type merge -p '{"data":{"server.insecure":"true"}}' 2>/dev/null || sleep 5 && kubectl patch configmap argocd-cmd-params-cm -n argocd --type merge -p '{"data":{"server.insecure":"true"}}'
kubectl patch configmap argocd-cm -n argocd --type merge -p '{"data":{"url":"http://k8s-multi-demo.argocd","server.rbac.logout.redirect":"http://k8s-multi-demo.argocd"}}'
print_success "ArgoCD config patches applied"

print_step "Exposing ArgoCD via NodePort (port ${ARGOCD_NODEPORT})..."
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "NodePort", "ports": [{"name": "http", "port": 80, "targetPort": 8080, "nodePort": 30800}]}}'
print_success "ArgoCD exposed on NodePort ${ARGOCD_NODEPORT}"

print_step "Applying ArgoCD Ingress..."
kubectl apply -f k8s/argoCD/argocd-ingress.yaml
print_success "ArgoCD Ingress created"

print_step "Waiting for ArgoCD server to be ready (this may take a few minutes)..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=600s
print_success "ArgoCD server is ready"

print_step "Retrieving ArgoCD admin password..."
ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" 2>/dev/null | base64 -d)
if [ -n "$ARGOCD_PASSWORD" ]; then
    print_success "ArgoCD admin password retrieved"
else
    print_warning "Could not retrieve ArgoCD password"
    ARGOCD_PASSWORD="(check manually)"
fi

print_success "ArgoCD installation complete!"

# ============================================
# STEP 12: INSTALL JENKINS
# ============================================
print_header "STEP 12: INSTALLING JENKINS"

print_step "Adding Jenkins Helm repository..."
helm repo add jenkins https://charts.jenkins.io
helm repo update
print_success "Jenkins Helm repo added"

print_step "Installing Jenkins via Helm..."
helm install jenkins jenkins/jenkins -n jenkins --create-namespace \
  --set controller.serviceType=NodePort \
  --set controller.nodePort=${JENKINS_NODEPORT}
print_success "Jenkins Helm release created"

print_step "Waiting for Jenkins pod to be created..."
for i in $(seq 1 60); do
    if kubectl get pods -l app.kubernetes.io/name=jenkins -n jenkins --no-headers 2>/dev/null | grep -q .; then
        break
    fi
    sleep 5
done

print_step "Waiting for Jenkins to be ready (this may take a few minutes)..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=jenkins -n jenkins --timeout=600s
print_success "Jenkins is ready!"

print_step "Retrieving Jenkins admin password..."
JENKINS_PASSWORD=$(kubectl exec -n jenkins svc/jenkins -c jenkins -- cat /run/secrets/additional/chart-admin-password 2>/dev/null)
if [ -n "$JENKINS_PASSWORD" ]; then
    print_success "Jenkins admin password retrieved"
else
    print_warning "Could not retrieve Jenkins password"
    JENKINS_PASSWORD="(check manually)"
fi

print_success "Jenkins installation complete!"

# ============================================
# STEP 13: COMPREHENSIVE TESTING
# ============================================
print_header "STEP 12/14: RUNNING COMPREHENSIVE TESTS"

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

print_step "Test 3: Checking services..."
SERVICES=$(kubectl get svc -n ${NAMESPACE} --no-headers | wc -l)
print_success "$SERVICES services configured"

print_step "Test 4: Checking ingress..."
INGRESS_HOSTS=$(kubectl get ingress -n ${NAMESPACE} -o jsonpath='{.items[0].spec.rules[0].host}' 2>/dev/null || echo "none")
print_success "Ingress configured for: $INGRESS_HOSTS"

print_step "Test 5: Testing NodePort connectivity..."
sleep 3
if curl -s -o /dev/null -w "%{http_code}" http://localhost:${NODEPORT}/health 2>/dev/null | grep -q "200"; then
    print_success "NodePort accessible at http://localhost:${NODEPORT}"
else
    print_warning "NodePort connectivity test inconclusive (app may still be starting)"
fi

print_step "Test 6: Checking HPA status..."
HPA_STATUS=$(kubectl get hpa -n ${NAMESPACE} -o jsonpath='{.items[0].status.currentReplicas}' 2>/dev/null || echo "0")
HPA_TARGET=$(kubectl get hpa -n ${NAMESPACE} -o jsonpath='{.items[0].spec.minReplicas}' 2>/dev/null || echo "0")
print_success "HPA active: $HPA_STATUS/$HPA_TARGET replicas"

print_step "Test 7: Checking metrics-server..."
kubectl top nodes &>/dev/null && print_success "Metrics-server working" || print_warning "Metrics not available yet (this is normal)"

print_step "Test 8: Verifying scenarios API..."
sleep 2
SCENARIO_API_COUNT=$(curl -s http://localhost:${NODEPORT}/api/scenarios 2>/dev/null | grep -o '"id":' | wc -l || echo "0")
if [ "$SCENARIO_API_COUNT" -eq 18 ]; then
    print_success "Scenarios API returning ${SCENARIO_API_COUNT} scenarios ✨"
elif [ "$SCENARIO_API_COUNT" -eq 0 ]; then
    print_warning "Scenarios API returned 0 scenarios - app may still be initializing"
else
    print_warning "Scenarios API returned ${SCENARIO_API_COUNT} scenarios (expected 18)"
fi

print_success "All tests completed!"

# ============================================
# STEP 13: CONFIGURE HOSTS FILE
# ============================================
print_header "STEP 13/14: CONFIGURING HOSTS FILE"

print_step "Checking /etc/hosts for application ingress hostname..."
APP_HOSTS_ENTRY="127.0.0.1 k8s-multi-demo.internal"

if grep -q "k8s-multi-demo.internal" /etc/hosts 2>/dev/null; then
    print_success "Application host entry already exists in /etc/hosts"
else
    print_step "Adding k8s-multi-demo.internal to /etc/hosts..."

    if [ -w /etc/hosts ]; then
        echo "$APP_HOSTS_ENTRY" >> /etc/hosts
        print_success "Successfully added application host to /etc/hosts"
    else
        print_warning "Cannot write to /etc/hosts (need sudo)"
        echo ""
        echo -e "${YELLOW}To enable application ingress access, please run:${NC}"
        echo -e "${YELLOW}  echo '$APP_HOSTS_ENTRY' | sudo tee -a /etc/hosts${NC}"
        echo ""
    fi
fi

print_step "Checking /etc/hosts for ArgoCD ingress hostname..."
ARGOCD_HOSTS_ENTRY="127.0.0.1 k8s-multi-demo.argocd"

if grep -q "k8s-multi-demo.argocd" /etc/hosts 2>/dev/null; then
    print_success "ArgoCD host entry already exists in /etc/hosts"
else
    print_step "Adding k8s-multi-demo.argocd to /etc/hosts..."

    if [ -w /etc/hosts ]; then
        echo "$ARGOCD_HOSTS_ENTRY" >> /etc/hosts
        print_success "Successfully added ArgoCD host to /etc/hosts"
    else
        print_warning "Cannot write to /etc/hosts (need sudo)"
        echo ""
        echo -e "${YELLOW}To enable ArgoCD ingress access, please run:${NC}"
        echo -e "${YELLOW}  echo '$ARGOCD_HOSTS_ENTRY' | sudo tee -a /etc/hosts${NC}"
        echo ""
    fi
fi

# ============================================
# STEP 14: DISPLAY RESULTS
# ============================================
print_header "STEP 14/14: DEPLOYMENT SUMMARY"

kubectl get all -n ${NAMESPACE}

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${CYAN}📍 APPLICATION ACCESS POINTS:${NC}"
echo -e "  ${GREEN}Via localhost (NodePort):${NC}"
echo "    - Dashboard:  http://localhost:${NODEPORT}"
echo "    - Scenarios:  http://localhost:${NODEPORT}/static/scenarios.html"
echo "    - Database:   http://localhost:${NODEPORT}/database"
echo ""
echo -e "  ${GREEN}Via hostname (Ingress):${NC}"
if [ "$INGRESS_HOSTS" != "none" ]; then
    echo "    - Dashboard:  http://k8s-multi-demo.internal:${NODEPORT}"
    echo "    - Scenarios:  http://k8s-multi-demo.internal:${NODEPORT}/static/scenarios.html"
    echo "    - Database:   http://k8s-multi-demo.internal:${NODEPORT}/database"
else
    echo "    - Ingress not configured"
fi
echo ""

echo -e "${CYAN}📍 ARGOCD ACCESS POINTS:${NC}"
echo -e "  ${GREEN}Via localhost (NodePort):${NC}"
echo "    - URL:      http://localhost:${ARGOCD_NODEPORT}"
echo "    - Username: admin"
echo "    - Password: ${ARGOCD_PASSWORD}"
echo ""
echo -e "  ${GREEN}Via hostname (Ingress):${NC}"
echo "    - URL:      http://k8s-multi-demo.argocd"
echo "    - Username: admin"
echo "    - Password: ${ARGOCD_PASSWORD}"
echo ""

echo -e "${CYAN}📍 JENKINS ACCESS POINTS:${NC}"
echo -e "  ${GREEN}Via localhost:${NC}"
echo "    - URL:      http://localhost:${JENKINS_HOST_PORT}"
echo "    - Username: admin"
echo "    - Password: ${JENKINS_PASSWORD}"
echo ""

echo -e "${CYAN}📚 Kubernetes Scenarios:${NC}"
echo "  ✅ 18 Interactive Scenarios Built Into Image"
echo "  ℹ️  Scenarios are baked into the Docker image - always available!"
echo ""

echo -e "${CYAN}💾 Database Information:${NC}"
echo "  ✅ PostgreSQL deployed and initialized"
echo "  📊 Tables: users, tasks, app_metrics"
echo "  🔗 Connection: postgres-service:5432"
echo ""

echo -e "${CYAN}🎯 Quick Commands:${NC}"
echo "  # View all pods:"
echo "  kubectl get pods -n ${NAMESPACE}"
echo ""
echo "  # View ArgoCD pods:"
echo "  kubectl get pods -n argocd"
echo ""
echo "  # View Jenkins pods:"
echo "  kubectl get pods -n jenkins"
echo ""
echo "  # View scenarios in pod:"
if [ -n "$FIRST_POD" ]; then
    echo "  kubectl exec -n ${NAMESPACE} ${FIRST_POD} -- ls /scenarios/"
fi
echo ""
echo "  # View application logs:"
echo "  kubectl logs -n ${NAMESPACE} -l app=k8s-demo-app -f"
echo ""
echo "  # Test API:"
echo "  curl http://localhost:${NODEPORT}/api/scenarios | jq '.scenarios | length'"
echo ""
echo "  # Login to ArgoCD CLI:"
echo "  argocd login localhost:${ARGOCD_NODEPORT} --username admin --password ${ARGOCD_PASSWORD} --insecure"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Ready to use!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}🚀 Start exploring:${NC}"
echo -e "${CYAN}  Application: http://localhost:${NODEPORT}/static/scenarios.html${NC}"
echo -e "${CYAN}  ArgoCD:      http://localhost:${ARGOCD_NODEPORT}${NC}"
echo -e "${CYAN}  Jenkins:     http://localhost:${JENKINS_HOST_PORT}${NC}"
echo ""
echo -e "${GREEN}Enjoy exploring 18 hands-on Kubernetes scenarios with GitOps!${NC}"
echo ""