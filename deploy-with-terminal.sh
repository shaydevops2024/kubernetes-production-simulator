#!/bin/bash
# Complete deployment script for K8s Production Simulator with Play Kubernetes

set -e

echo "=========================================="
echo "K8s Production Simulator Deployment"
echo "with Play Kubernetes Feature"
echo "=========================================="
echo ""

# Configuration
NAMESPACE="k8s-multi-demo"
IMAGE_NAME="k8s-demo-app"
IMAGE_TAG="v2.0-with-terminal"

# Step 1: Build Docker Image
echo "Step 1: Building Docker image..."
cd app
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
echo "✅ Docker image built successfully!"
echo ""

# Step 2: Load image into Kind
echo "Step 2: Loading image into Kind cluster..."
kind load docker-image ${IMAGE_NAME}:${IMAGE_TAG} --name k8s-demo
echo "✅ Image loaded into Kind!"
echo ""

# Step 3: Deploy base infrastructure
echo "Step 3: Deploying base infrastructure..."
cd ..
kubectl apply -f k8s/base/
kubectl apply -f k8s/database/
kubectl apply -f k8s/hpa/
kubectl apply -f k8s/ingress/
echo "✅ Base infrastructure deployed!"
echo ""

# Step 4: Wait for database to be ready
echo "Step 4: Waiting for database to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n ${NAMESPACE} --timeout=120s
echo "✅ Database is ready!"
echo ""

# Step 5: Update deployment to use new image
echo "Step 5: Updating application deployment..."
kubectl set image deployment/k8s-demo-deployment \
  k8s-demo-app=${IMAGE_NAME}:${IMAGE_TAG} \
  -n ${NAMESPACE}
  
kubectl rollout status deployment/k8s-demo-deployment -n ${NAMESPACE}
echo "✅ Application updated!"
echo ""

# Step 6: Copy scenarios into running pod
echo "Step 6: Copying scenarios into pod..."
POD_NAME=$(kubectl get pod -n ${NAMESPACE} -l app=k8s-demo-app -o jsonpath='{.items[0].metadata.name}')

if [ ! -z "$POD_NAME" ]; then
    echo "Copying scenarios to pod: $POD_NAME"
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- mkdir -p /scenarios
    
    # Copy each scenario directory
    for scenario_dir in k8s-scenarios/*/; do
        scenario_name=$(basename "$scenario_dir")
        echo "  → Copying ${scenario_name}..."
        kubectl cp "${scenario_dir}" ${NAMESPACE}/${POD_NAME}:/scenarios/${scenario_name}
    done
    
    # Make validation scripts executable
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- chmod +x /scenarios/*/validate.sh
    
    echo "✅ Scenarios copied successfully!"
else
    echo "⚠️  Warning: Could not find pod to copy scenarios"
fi
echo ""

# Step 7: Verify deployment
echo "Step 7: Verifying deployment..."
echo ""
echo "Pods:"
kubectl get pods -n ${NAMESPACE}
echo ""
echo "Services:"
kubectl get svc -n ${NAMESPACE}
echo ""
echo "Ingress:"
kubectl get ingress -n ${NAMESPACE}
echo ""

# Step 8: Get access information
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Access the application:"
echo "  • Dashboard: http://localhost (or your ingress address)"
echo "  • NodePort: http://localhost:30080"
echo ""
echo "Play Kubernetes Features:"
echo "  1. Click '🎮 Play Kubernetes' in the sidebar"
echo "  2. Browse 18 interactive scenarios"
echo "  3. Practice real Kubernetes operations"
echo ""
echo "Verify scenarios are loaded:"
echo "  kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ls -la /scenarios"
echo ""
echo "View application logs:"
echo "  kubectl logs -n ${NAMESPACE} -l app=k8s-demo-app -f"
echo ""
echo "Happy Learning! 🚀"
