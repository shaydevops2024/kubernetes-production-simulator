#!/bin/bash
# Simple load test to trigger HPA

echo "🔥 Starting load test..."
echo "Press Ctrl+C to stop"
echo ""

# Run 50 parallel requests continuously
for i in {1..50}; do
  (while true; do 
    curl -s http://localhost:8080/ > /dev/null
    sleep 0.05
  done) &
done

echo "Load test running with 50 parallel workers..."
echo ""
echo "In another terminal, watch scaling with:"
echo "  kubectl get hpa -n k8s-multi-demo -w"
echo "  kubectl get pods -n k8s-multi-demo -w"

# Wait for Ctrl+C
wait
