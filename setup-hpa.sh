#!/bin/bash
# setup-hpa.sh
# Complete HPA setup

NAMESPACE="k8s-multi-demo"

echo "🚀 Setting up Horizontal Pod Autoscaler"
echo "========================================"
echo ""

# Create HPA directory
mkdir -p k8s/hpa

# Create HPA file
echo "📝 Creating HPA configuration..."
cat > k8s/hpa/hpa.yaml << 'EOF'
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: k8s-demo-hpa
  namespace: k8s-multi-demo
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: k8s-demo-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
EOF

# Apply HPA
echo "✅ Applying HPA..."
kubectl apply -f k8s/hpa/hpa.yaml

# Check if metrics-server exists
if ! kubectl get deployment metrics-server -n kube-system &>/dev/null; then
    echo ""
    echo "📥 Installing metrics-server..."
    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
    
    echo "⚙️  Patching metrics-server for kind..."
    kubectl patch -n kube-system deployment metrics-server --type=json \
      -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
    
    echo "⏳ Waiting for metrics-server to be ready..."
    kubectl wait --for=condition=ready pod -l k8s-app=metrics-server -n kube-system --timeout=90s
else
    echo "✅ metrics-server already installed"
fi

# Wait for metrics
echo ""
echo "⏳ Waiting 30 seconds for metrics to be collected..."
sleep 30

# Show status
echo ""
echo "📊 Current Status:"
echo "=================="
echo ""
echo "HPA:"
kubectl get hpa -n ${NAMESPACE}
echo ""
echo "Pods:"
kubectl get pods -n ${NAMESPACE}
echo ""
echo "Pod Metrics:"
kubectl top pods -n ${NAMESPACE} 2>/dev/null || echo "Metrics not ready yet (wait a bit longer)"

echo ""
echo "✅ HPA Setup Complete!"
echo ""
echo "🧪 Test auto-scaling:"
echo "  1. Watch HPA: kubectl get hpa -n ${NAMESPACE} -w"
echo "  2. Generate load: for i in {1..50}; do (while true; do curl -s http://localhost:8080/ > /dev/null; sleep 0.05; done) & done"
echo "  3. Watch pods scale up!"
