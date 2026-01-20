#!/bin/bash
# complete-setup.sh
# Complete automated setup - run this ONE command to get everything working!

set -e

echo "🚀 Complete Kubernetes Setup with Ingress"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
CLUSTER_NAME="k8s-demo"
NAMESPACE="k8s-multi-demo"
HOSTNAME="k8s-multi-demo.local"

echo -e "${BLUE}Step 1/10: Checking prerequisites...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

if ! command -v kind &> /dev/null; then
    echo -e "${RED}❌ kind not found. Installing kind...${NC}"
    curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
    chmod +x ./kind
    sudo mv ./kind /usr/local/bin/kind
fi

echo -e "${GREEN}✅ Prerequisites OK${NC}"

# Delete existing cluster if it exists
echo -e "${BLUE}Step 2/10: Checking for existing cluster...${NC}"
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo -e "${YELLOW}Deleting existing cluster...${NC}"
    kind delete cluster --name ${CLUSTER_NAME}
fi

# Create kind config
echo -e "${BLUE}Step 3/10: Creating kind cluster configuration...${NC}"
cat <<EOF > /tmp/kind-config.yaml
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
EOF

# Create cluster
echo -e "${BLUE}Step 4/10: Creating kind cluster (this takes ~60 seconds)...${NC}"
kind create cluster --name ${CLUSTER_NAME} --config /tmp/kind-config.yaml

# Wait for cluster
echo -e "${BLUE}Step 5/10: Waiting for cluster to be ready...${NC}"
kubectl wait --for=condition=ready node --all --timeout=120s

# Install ingress controller
echo -e "${BLUE}Step 6/10: Installing NGINX Ingress Controller...${NC}"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for ingress controller (this is the critical part!)
echo -e "${BLUE}Step 7/10: Waiting for Ingress Controller to be ready (this takes ~60 seconds)...${NC}"
echo -e "${YELLOW}Waiting for ingress-nginx namespace to be created...${NC}"
while ! kubectl get namespace ingress-nginx &> /dev/null; do
    sleep 2
done

echo -e "${YELLOW}Waiting for controller pod to be created...${NC}"
while ! kubectl get pods -n ingress-nginx -l app.kubernetes.io/component=controller &> /dev/null; do
    sleep 2
done

echo -e "${YELLOW}Waiting for controller pod to be ready...${NC}"
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s

echo -e "${GREEN}✅ Ingress Controller is ready!${NC}"

# Build Docker image
echo -e "${BLUE}Step 8/10: Building Docker image...${NC}"
docker build -t k8s-demo-app:latest ./app

# Load image into kind
echo -e "${BLUE}Step 9/10: Loading image into kind cluster...${NC}"
kind load docker-image k8s-demo-app:latest --name ${CLUSTER_NAME}

# Deploy application
echo -e "${BLUE}Step 10/10: Deploying application...${NC}"
kubectl apply -f k8s/base/namespace.yaml
sleep 2
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/secret.yaml
kubectl apply -f k8s/base/deployment.yaml
kubectl apply -f k8s/base/service.yaml
kubectl apply -f k8s/ingress/ingress.yaml

# Wait for pods
echo -e "${YELLOW}Waiting for application pods to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=k8s-demo-app -n ${NAMESPACE} --timeout=120s

# Update /etc/hosts
echo -e "${BLUE}Updating /etc/hosts...${NC}"
if ! grep -q "${HOSTNAME}" /etc/hosts; then
    echo "127.0.0.1 ${HOSTNAME}" | sudo tee -a /etc/hosts
    echo -e "${GREEN}✅ Added ${HOSTNAME} to /etc/hosts${NC}"
else
    echo -e "${YELLOW}${HOSTNAME} already in /etc/hosts${NC}"
fi

# Final verification
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 SETUP COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Test connection
echo -e "${BLUE}Testing connection...${NC}"
sleep 5

if curl -s -o /dev/null -w "%{http_code}" http://${HOSTNAME} | grep -q "200"; then
    echo -e "${GREEN}✅ Application is accessible!${NC}"
    echo ""
    echo -e "${GREEN}📱 Access your application:${NC}"
    echo "   🌐 Web UI:      http://${HOSTNAME}"
    echo "   📖 API Docs:    http://${HOSTNAME}/docs"
    echo "   📊 Metrics:     http://${HOSTNAME}/metrics"
    echo ""
    echo -e "${GREEN}🔍 Useful commands:${NC}"
    echo "   kubectl get pods -n ${NAMESPACE}"
    echo "   kubectl logs -f -l app=k8s-demo-app -n ${NAMESPACE}"
    echo "   kubectl get ingress -n ${NAMESPACE}"
    echo ""
    echo -e "${GREEN}🧪 Test the app:${NC}"
    echo "   curl http://${HOSTNAME}/health"
    echo "   curl http://${HOSTNAME}/ready"
    echo "   curl -X POST http://${HOSTNAME}/simulate/crash"
    echo ""
    
    # Show current status
    echo -e "${GREEN}📊 Current Status:${NC}"
    kubectl get pods -n ${NAMESPACE}
    echo ""
    kubectl get svc -n ${NAMESPACE}
    echo ""
    kubectl get ingress -n ${NAMESPACE}
    echo ""
    
    # Try to open browser
    echo -e "${BLUE}Opening browser...${NC}"
    if command -v google-chrome &> /dev/null; then
        nohup google-chrome http://${HOSTNAME} > /dev/null 2>&1 &
    elif command -v firefox &> /dev/null; then
        nohup firefox http://${HOSTNAME} > /dev/null 2>&1 &
    elif command -v chromium-browser &> /dev/null; then
        nohup chromium-browser http://${HOSTNAME} > /dev/null 2>&1 &
    else
        echo -e "${YELLOW}Please open http://${HOSTNAME} in your browser${NC}"
    fi
    
else
    echo -e "${RED}❌ Cannot reach application at http://${HOSTNAME}${NC}"
    echo ""
    echo -e "${YELLOW}🔍 Troubleshooting:${NC}"
    echo "1. Check pods:"
    kubectl get pods -n ${NAMESPACE}
    echo ""
    echo "2. Check ingress:"
    kubectl get ingress -n ${NAMESPACE}
    echo ""
    echo "3. Check ingress controller logs:"
    kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=20
    echo ""
    echo -e "${YELLOW}💡 Quick fix - use port-forward:${NC}"
    echo "   kubectl port-forward svc/k8s-demo-service 8080:80 -n ${NAMESPACE}"
    echo "   Then open: http://localhost:8080"
fi
