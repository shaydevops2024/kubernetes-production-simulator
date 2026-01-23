# HPA Auto-Scaling Demo

## Objective
Learn how Horizontal Pod Autoscaler (HPA) automatically scales pods based on CPU usage and resource metrics.

## What You'll Learn
- Configure HPA with CPU and memory thresholds
- Generate artificial load to trigger scaling
- Monitor scaling behavior in real-time
- Understand scale-up and scale-down policies
- Verify autoscaling metrics and events

## Prerequisites
- Basic kubectl knowledge
- Understanding of Kubernetes Deployments
- Familiarity with resource requests/limits

## Duration
15 minutes

## Steps Overview
1. Check current HPA configuration
2. Verify deployment baseline
3. Generate CPU load
4. Watch automatic pod scaling
5. Stop load and observe scale-down
6. Review HPA events and metrics

## Success Criteria
- HPA successfully scales pods from 2 to at least 5
- Pods scale back down after load stops
- No pod failures during scaling
- HPA reports correct CPU utilization

## Tips
- Use `kubectl get hpa -w` for live monitoring
- Check pod resource consumption with `kubectl top pods`
- View HPA details with `kubectl describe hpa`
