#!/bin/bash
# scripts/load-test.sh
# Simple load testing script to trigger HPA

echo "🔥 Starting load test..."
echo "This will generate traffic to trigger auto-scaling"
echo "Watch pods scale: kubectl get hpa -n k8s-multi-demo -w"
echo ""

# Run 100 concurrent requests for 30 seconds
for i in {1..100}; do
  (while true; do 
    curl -s http://k8s-demo.local/ > /dev/null
    sleep 0.1
  done) &
done

echo "Load test running for 30 seconds..."
sleep 30

# Kill all background jobs
pkill -P $$

echo "✅ Load test complete!"
echo "Check HPA: kubectl get hpa -n k8s-demo"
