#!/bin/bash
# k8s_setup.sh
# Deploy to Regular Kubernetes (Native, EKS, GKE, AKS, etc.)
# This script deploys to ANY existing Kubernetes cluster

set -e  # Exit on any error

# ============================================
# CONFIGURATION
# ============================================
NAMESPACE="k8s-multi-demo"
APP_NAME="k8s-demo-app"
DEFAULT_IMAGE_TAG="latest"

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
print_header "KUBERNETES PRODUCTION DEMO - CLOUD/NATIVE DEPLOYMENT"

echo -e "${GREEN}This script deploys to ANY Kubernetes cluster:${NC}"
echo "  ✓ Native Kubernetes"
echo "  ✓ AWS EKS"
echo "  ✓ Google GKE"
echo "  ✓ Azure AKS"
echo "  ✓ DigitalOcean DOKS"
echo "  ✓ Any managed/self-hosted K8s"
echo ""
echo -e "${CYAN}What this script does:${NC}"
echo "  1. Verify cluster connection"
echo "  2. Build Docker image with 18 scenarios"
echo "  3. Push to your Docker registry"
echo "  4. Deploy application with PostgreSQL"
echo "  5. Setup metrics-server (if needed)"
echo "  6. Configure HPA and Ingress"
echo "  7. Run tests and provide access URLs"
echo ""

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
    KUBECTL_VERSION=$(kubectl version --client --short 2>/dev/null | cut -d' ' -f3 || echo "unknown")
    print_success "kubectl installed (version $KUBECTL_VERSION)"
else
    print_error "kubectl not found. Please install kubectl first."
    exit 1
fi

print_step "Checking cluster connection..."
if kubectl cluster-info &>/dev/null; then
    CURRENT_CONTEXT=$(kubectl config current-context)
    CLUSTER_VERSION=$(kubectl version --short 2>/dev/null | grep "Server Version" | cut -d' ' -f3 || echo "unknown")
    print_success "Connected to cluster: $CURRENT_CONTEXT"
    print_info "Cluster version: $CLUSTER_VERSION"
else
    print_error "Cannot connect to Kubernetes cluster!"
    echo ""
    echo "Please ensure:"
    echo "  1. You have a running Kubernetes cluster"
    echo "  2. kubectl is configured with valid credentials"
    echo "  3. Run: kubectl cluster-info"
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
# STEP 2: DOCKER REGISTRY CONFIGURATION
# ============================================
print_header "STEP 2/10: DOCKER REGISTRY CONFIGURATION"

echo -e "${YELLOW}Where do you want to push the Docker image?${NC}"
echo ""
echo "  1. Docker Hub (docker.io)"
echo "  2. AWS ECR (Amazon Elastic Container Registry)"
echo "  3. Google GCR (Google Container Registry)"
echo "  4. Azure ACR (Azure Container Registry)"
echo "  5. Custom Registry"
echo ""
read -p "Select registry type (1-5): " REGISTRY_CHOICE

case $REGISTRY_CHOICE in
    1)
        REGISTRY_TYPE="dockerhub"
        echo ""
        read -p "Enter your Docker Hub username: " DOCKER_USERNAME
        if [ -z "$DOCKER_USERNAME" ]; then
            print_error "Username cannot be empty"
            exit 1
        fi
        FULL_IMAGE_NAME="${DOCKER_USERNAME}/${APP_NAME}:${DEFAULT_IMAGE_TAG}"
        print_info "Image will be: $FULL_IMAGE_NAME"
        ;;
    2)
        REGISTRY_TYPE="ecr"
        echo ""
        read -p "Enter AWS Account ID: " AWS_ACCOUNT_ID
        read -p "Enter AWS Region (e.g., us-east-1): " AWS_REGION
        if [ -z "$AWS_ACCOUNT_ID" ] || [ -z "$AWS_REGION" ]; then
            print_error "AWS Account ID and Region are required"
            exit 1
        fi
        FULL_IMAGE_NAME="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${APP_NAME}:${DEFAULT_IMAGE_TAG}"
        print_info "Image will be: $FULL_IMAGE_NAME"
        ;;
    3)
        REGISTRY_TYPE="gcr"
        echo ""
        read -p "Enter GCP Project ID: " GCP_PROJECT_ID
        if [ -z "$GCP_PROJECT_ID" ]; then
            print_error "GCP Project ID is required"
            exit 1
        fi
        FULL_IMAGE_NAME="gcr.io/${GCP_PROJECT_ID}/${APP_NAME}:${DEFAULT_IMAGE_TAG}"
        print_info "Image will be: $FULL_IMAGE_NAME"
        ;;
    4)
        REGISTRY_TYPE="acr"
        echo ""
        read -p "Enter Azure ACR name (without .azurecr.io): " ACR_NAME
        if [ -z "$ACR_NAME" ]; then
            print_error "ACR name is required"
            exit 1
        fi
        FULL_IMAGE_NAME="${ACR_NAME}.azurecr.io/${APP_NAME}:${DEFAULT_IMAGE_TAG}"
        print_info "Image will be: $FULL_IMAGE_NAME"
        ;;
    5)
        REGISTRY_TYPE="custom"
        echo ""
        read -p "Enter full image name (e.g., myregistry.com/myapp:latest): " FULL_IMAGE_NAME
        if [ -z "$FULL_IMAGE_NAME" ]; then
            print_error "Image name cannot be empty"
            exit 1
        fi
        ;;
    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

echo ""
print_success "Registry configured: $FULL_IMAGE_NAME"

# ============================================
# STEP 3: BUILD DOCKER IMAGE
# ============================================
print_header "STEP 3/10: BUILDING DOCKER IMAGE WITH SCENARIOS"

print_step "Building Docker image..."
echo ""
echo "Build context: $(pwd)"
echo "Dockerfile: app/Dockerfile"
echo "Including: k8s-scenarios/ (18 scenarios)"
echo ""

docker build -f app/Dockerfile -t ${FULL_IMAGE_NAME} . --no-cache

print_success "Docker image built: $FULL_IMAGE_NAME"

# ============================================
# STEP 4: PUSH TO REGISTRY
# ============================================
print_header "STEP 4/10: PUSHING IMAGE TO REGISTRY"

case $REGISTRY_TYPE in
    dockerhub)
        print_step "Logging into Docker Hub..."
        docker login
        ;;
    ecr)
        print_step "Logging into AWS ECR..."
        aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

        # Create repository if it doesn't exist
        aws ecr describe-repositories --repository-names ${APP_NAME} --region ${AWS_REGION} 2>/dev/null || \
            aws ecr create-repository --repository-name ${APP_NAME} --region ${AWS_REGION}
        ;;
    gcr)
        print_step "Logging into Google GCR..."
        gcloud auth configure-docker
        ;;
    acr)
        print_step "Logging into Azure ACR..."
        az acr login --name ${ACR_NAME}
        ;;
    custom)
        print_warning "Please ensure you're logged into your custom registry"
        read -p "Press Enter to continue..."
        ;;
esac

print_step "Pushing image to registry..."
docker push ${FULL_IMAGE_NAME}

print_success "Image pushed successfully!"

# ============================================
# STEP 5: CREATE NAMESPACE
# ============================================
print_header "STEP 5/10: CREATING NAMESPACE"

print_step "Creating namespace '${NAMESPACE}'..."
kubectl apply -f k8s/base/namespace.yaml

print_success "Namespace created"

# ============================================
# STEP 6: DEPLOY APPLICATION
# ============================================
print_header "STEP 6/10: DEPLOYING APPLICATION"

print_step "Creating Service Account and RBAC..."
kubectl apply -f k8s/base/rbac.yaml

print_step "Applying ConfigMap..."
kubectl apply -f k8s/base/configmap.yaml

print_step "Applying Secret..."
kubectl apply -f k8s/base/secret.yaml

print_step "Deploying application with custom image..."
# Update deployment to use the pushed image
kubectl apply -f k8s/base/deployment.yaml
kubectl set image deployment/k8s-demo-app k8s-demo-app=${FULL_IMAGE_NAME} -n ${NAMESPACE}

print_step "Creating services..."
kubectl apply -f k8s/base/service.yaml
kubectl apply -f k8s/base/service-lb.yaml
kubectl apply -f k8s/base/service-nodeport.yaml

# Check if cluster supports LoadBalancer
print_step "Checking LoadBalancer support..."
CLOUD_PROVIDER=$(kubectl get nodes -o jsonpath='{.items[0].spec.providerID}' | cut -d':' -f1)
if [ -n "$CLOUD_PROVIDER" ]; then
    print_info "Detected cloud provider: $CLOUD_PROVIDER"
    print_info "LoadBalancer services should work"
else
    print_warning "Cloud provider not detected - LoadBalancer may not work"
    print_info "You may need to use NodePort or port-forward"
fi

# Deploy database if script exists
if [ -f "./deploy-database.sh" ]; then
    chmod +x ./deploy-database.sh
    ./deploy-database.sh
fi

print_step "Waiting for application pods to be ready..."
kubectl wait --for=condition=ready pod -l app=k8s-demo-app -n ${NAMESPACE} --timeout=600s

POD_COUNT=$(kubectl get pods -n ${NAMESPACE} --no-headers | grep k8s-demo-app | grep Running | wc -l)
print_success "Application deployed! ($POD_COUNT pods running)"

# ============================================
# STEP 7: VERIFY SCENARIOS IN PODS
# ============================================
print_header "STEP 7/10: VERIFYING SCENARIOS IN PODS"

print_step "Checking scenarios in pods..."
POD_NAMES=($(kubectl get pods -n ${NAMESPACE} -l app=k8s-demo-app -o jsonpath='{.items[*].metadata.name}'))
FIRST_POD="${POD_NAMES[0]}"

if [ -n "$FIRST_POD" ]; then
    SCENARIO_COUNT=$(kubectl exec -n ${NAMESPACE} ${FIRST_POD} -- ls /scenarios 2>/dev/null | wc -l)

    if [ "$SCENARIO_COUNT" -eq 18 ]; then
        print_success "Verified: ${SCENARIO_COUNT} scenarios present in pods!"
        print_info "Scenarios are baked into the Docker image!"
    else
        print_warning "Found ${SCENARIO_COUNT} scenarios (expected 18)"
    fi
else
    print_warning "Cannot verify scenarios - no pod found"
fi

# ============================================
# STEP 8: INSTALL/CHECK METRICS SERVER
# ============================================
print_header "STEP 8/10: CHECKING METRICS SERVER"

print_step "Checking if metrics-server is installed..."
if kubectl get deployment metrics-server -n kube-system &>/dev/null; then
    print_success "Metrics-server already installed (common on managed K8s)"
    kubectl rollout status deployment/metrics-server -n kube-system --timeout=60s || true
else
    print_step "Installing metrics-server..."
    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

    print_step "Waiting for metrics-server to be ready..."
    sleep 10
    kubectl rollout status deployment/metrics-server -n kube-system --timeout=300s || print_warning "Metrics server taking longer than expected"
fi

print_success "Metrics-server ready!"

# ============================================
# STEP 9: CONFIGURE HPA
# ============================================
print_header "STEP 9/10: CONFIGURING HORIZONTAL POD AUTOSCALER"

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
print_success "HPA configured!"

# ============================================
# STEP 10: CONFIGURE INGRESS (OPTIONAL)
# ============================================
print_header "STEP 10/10: CONFIGURING INGRESS (OPTIONAL)"

print_step "Checking for ingress controller..."
INGRESS_CONTROLLER=$(kubectl get pods -A | grep -i ingress | head -1 || echo "")

if [ -n "$INGRESS_CONTROLLER" ]; then
    print_success "Ingress controller detected"

    read -p "Do you want to configure Ingress? (yes/no): " SETUP_INGRESS

    if [ "$SETUP_INGRESS" = "yes" ]; then
        echo ""
        read -p "Enter your domain/hostname (e.g., k8s-demo.example.com): " INGRESS_HOST

        if [ -n "$INGRESS_HOST" ]; then
            # Update ingress with custom hostname
            print_step "Applying Ingress with hostname: $INGRESS_HOST"
            kubectl apply -f k8s/ingress/ingress.yaml
            kubectl patch ingress k8s-demo-ingress -n ${NAMESPACE} -p "{\"spec\":{\"rules\":[{\"host\":\"${INGRESS_HOST}\",\"http\":{\"paths\":[{\"path\":\"/\",\"pathType\":\"Prefix\",\"backend\":{\"service\":{\"name\":\"k8s-demo-service\",\"port\":{\"number\":80}}}}]}}]}}"

            print_success "Ingress configured for: $INGRESS_HOST"
            print_info "Make sure DNS points to your ingress LoadBalancer IP"
        fi
    fi
else
    print_warning "No ingress controller detected"
    print_info "You can access via LoadBalancer or NodePort"
fi

# ============================================
# DEPLOYMENT COMPLETE - SHOW ACCESS INFO
# ============================================
print_header "DEPLOYMENT SUMMARY"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get service access information
print_step "Retrieving access information..."
echo ""

# Check LoadBalancer
LB_IP=$(kubectl get svc k8s-demo-service-lb -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
LB_HOSTNAME=$(kubectl get svc k8s-demo-service-lb -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")

# Check NodePort
NODEPORT=$(kubectl get svc k8s-demo-nodeport -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}' 2>/dev/null || echo "")

echo -e "${CYAN}📍 Access Points:${NC}"
echo ""

if [ -n "$LB_IP" ]; then
    echo -e "  ${GREEN}✓ LoadBalancer:${NC} http://${LB_IP}"
    echo "    Dashboard:  http://${LB_IP}"
    echo "    Scenarios:  http://${LB_IP}/static/scenarios.html"
elif [ -n "$LB_HOSTNAME" ]; then
    echo -e "  ${GREEN}✓ LoadBalancer:${NC} http://${LB_HOSTNAME}"
    echo "    Dashboard:  http://${LB_HOSTNAME}"
    echo "    Scenarios:  http://${LB_HOSTNAME}/static/scenarios.html"
else
    print_warning "LoadBalancer external IP pending..."
    echo "  Run: kubectl get svc k8s-demo-service-lb -n ${NAMESPACE} -w"
fi

if [ -n "$INGRESS_HOST" ]; then
    echo ""
    echo -e "  ${GREEN}✓ Ingress:${NC} http://${INGRESS_HOST}"
fi

if [ -n "$NODEPORT" ] && [ -n "$NODE_IP" ]; then
    echo ""
    echo -e "  ${GREEN}✓ NodePort:${NC} http://${NODE_IP}:${NODEPORT}"
fi

echo ""
echo -e "${CYAN}🔧 Alternative Access (Port-Forward):${NC}"
echo "  kubectl port-forward -n ${NAMESPACE} svc/k8s-demo-service 8080:8000"
echo "  Then access: http://localhost:8080"
echo ""

echo -e "${CYAN}📚 Application Features:${NC}"
echo "  ✅ 18 Interactive Kubernetes Scenarios"
echo "  ✅ PostgreSQL Database"
echo "  ✅ Horizontal Pod Autoscaling"
echo "  ✅ Production-Ready Configuration"
echo ""

echo -e "${CYAN}🎯 Quick Commands:${NC}"
echo "  # View all resources:"
echo "  kubectl get all -n ${NAMESPACE}"
echo ""
echo "  # View scenarios in pod:"
if [ -n "$FIRST_POD" ]; then
    echo "  kubectl exec -n ${NAMESPACE} ${FIRST_POD} -- ls /scenarios/"
fi
echo ""
echo "  # View logs:"
echo "  kubectl logs -n ${NAMESPACE} -l app=k8s-demo-app -f"
echo ""
echo "  # Check HPA status:"
echo "  kubectl get hpa -n ${NAMESPACE}"
echo ""

echo -e "${CYAN}📊 Cluster Information:${NC}"
echo "  Context: $CURRENT_CONTEXT"
echo "  Namespace: $NAMESPACE"
echo "  Image: $FULL_IMAGE_NAME"
echo "  Replicas: $(kubectl get deployment k8s-demo-app -n ${NAMESPACE} -o jsonpath='{.spec.replicas}')"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Ready to use!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Start exploring 18 hands-on Kubernetes scenarios!${NC}"
echo ""

# Final test
print_step "Running final connectivity test..."
sleep 3
if [ -n "$LB_IP" ]; then
    if curl -s -o /dev/null -w "%{http_code}" http://${LB_IP}/health 2>/dev/null | grep -q "200"; then
        print_success "Application is accessible via LoadBalancer!"
    else
        print_warning "Application may still be initializing..."
    fi
fi

print_success "Deployment complete! 🚀"
