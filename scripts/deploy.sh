#!/bin/bash
# scripts/deploy.sh
# Complete deployment script - runs everything in correct order

set -e  # Exit on error

echo "🚀 Starting Kubernetes Deployment..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Step 1: Building Docker image...${NC}"
cd app
docker build -t k8s-demo-app:latest .
cd ..

echo -e "${BLUE}Step 2: Loading image into kind cluster...${NC}"
kind load docker-image k8s-demo-app:latest --name k8s-multi-demo

echo -e "${BLUE}Step 3: Creating namespace...${NC}"
kubectl apply -f k8s/base/namespace.yaml

echo -e "${BLUE}Step 4: Applying ConfigMap and Secret...${NC}"
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/secret.yaml

echo -e "${BLUE}Step 5: Deploying application...${NC}"
kubectl apply -f k8s/base/deployment.yaml
kubectl apply -f k8s/base/service.yaml

echo -e "${BLUE}Step 6: Waiting for pods to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=k8s-demo-app -n k8s-multi-demo --timeout=60s

echo -e "${BLUE}Step 7: Installing NGINX Ingress Controller...${NC}"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s

echo -e "${BLUE}Step 8: Applying Ingress...${NC}"
kubectl apply -f k8s/ingress/ingress.yaml

echo -e "${BLUE}Step 9: Applying HPA (requires metrics-server)...${NC}"
kubectl apply -f k8s/hpa/hpa.yaml || echo -e "${YELLOW}Note: HPA requires metrics-server (install later)${NC}"

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo -e "${GREEN}📝 Next steps:${NC}"
echo "1. Add to /etc/hosts: echo '127.0.0.1 k8s-demo.local' | sudo tee -a /etc/hosts"
echo "2. Open browser: http://k8s-demo.local"
echo "3. Check pods: kubectl get pods -n k8s-multi-demo"
echo "4. Check logs: kubectl logs -f -l app=k8s-demo-app -n k8s-multi-demo"
